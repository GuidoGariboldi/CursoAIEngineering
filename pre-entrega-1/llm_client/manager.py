"""AsyncLLMManager: elige el proveedor según la configuración y delega en él."""

import os
from collections.abc import AsyncIterator, Sequence
from typing import Self

from .anthropic_client import AnthropicClient
from .base import BaseLLMClient
from .gemini_client import GeminiClient
from .openai_client import OpenAIClient
from .schemas import ChatMessage, GenerationConfig, ModelResponse, Provider, StreamChunk


class ConfigurationError(Exception):
    """Configuración inválida al arrancar (proveedor desconocido o falta la API key)."""


# proveedor -> (clase, variable de la API key, variable del modelo)
_REGISTRY: dict[Provider, tuple[type[BaseLLMClient], str, str]] = {
    Provider.OPENAI: (OpenAIClient, "OPENAI_API_KEY", "OPENAI_MODEL"),
    Provider.ANTHROPIC: (AnthropicClient, "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL"),
    Provider.GEMINI: (GeminiClient, "GOOGLE_API_KEY", "GEMINI_MODEL"),
}


class AsyncLLMManager:
    """Punto de entrada único. El código que lo usa no sabe qué proveedor hay detrás.

    Uso:
        async with AsyncLLMManager() as llm:          # lee LLM_PROVIDER del entorno
            resp = await llm.generate(messages)
            async for chunk in llm.stream(messages):
                print(chunk.content, end="")
    """

    def __init__(self, provider: Provider | str | None = None, *, api_key: str | None = None) -> None:
        name = (provider or os.getenv("LLM_PROVIDER") or "gemini").strip().lower()
        try:
            self.provider = Provider(name)
        except ValueError:
            valid = ", ".join(p.value for p in Provider)
            raise ConfigurationError(f"Proveedor desconocido: '{name}'. Opciones: {valid}.") from None

        client_cls, key_var, model_var = _REGISTRY[self.provider]

        api_key = api_key or os.getenv(key_var)
        if not api_key:
            raise ConfigurationError(f"Falta la variable de entorno {key_var}.")

        try:
            timeout = float(os.getenv("LLM_TIMEOUT", "30"))
            max_retries = int(os.getenv("LLM_MAX_RETRIES", "2"))
        except ValueError:
            raise ConfigurationError("LLM_TIMEOUT y LLM_MAX_RETRIES deben ser numéricos.") from None

        kwargs: dict = {"api_key": api_key, "timeout": timeout, "max_retries": max_retries}
        if model := os.getenv(model_var):
            kwargs["default_model"] = model

        self._client: BaseLLMClient = client_cls(**kwargs)

    @property
    def model(self) -> str:
        return self._client.default_model

    async def generate(
        self,
        messages: Sequence[ChatMessage | dict],
        config: GenerationConfig | None = None,
    ) -> ModelResponse:
        return await self._client.generate(messages, config)

    async def stream(
        self,
        messages: Sequence[ChatMessage | dict],
        config: GenerationConfig | None = None,
    ) -> AsyncIterator[StreamChunk]:
        async for chunk in self._client.stream(messages, config):
            yield chunk

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()
