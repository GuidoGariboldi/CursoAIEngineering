"""Cliente de Anthropic (Messages API) sobre AsyncAnthropic."""

from collections.abc import AsyncIterator
from typing import Any

import anthropic
from anthropic import AsyncAnthropic

from .base import BaseLLMClient, Clasificacion, clasificar_estilo_openai
from .schemas import ChatMessage, GenerationConfig, ModelResponse, Provider, Usage


class AnthropicClient(BaseLLMClient):
    provider = Provider.ANTHROPIC

    def __init__(
        self,
        api_key: str,
        default_model: str = "claude-haiku-4-5-20251001",
        timeout: float = 30.0,
        max_retries: int = 2,
    ) -> None:
        super().__init__(default_model)
        self._client = AsyncAnthropic(api_key=api_key, timeout=timeout, max_retries=max_retries)

    @staticmethod
    def _params(messages: list[ChatMessage], config: GenerationConfig, model: str) -> dict[str, Any]:
        """Adapta el formato común a las particularidades de la API de Anthropic."""
        # 1) El "system" no va en la lista de mensajes sino en un parámetro aparte.
        system = "\n\n".join(m.content for m in messages if m.role == "system")
        chat = [{"role": m.role, "content": m.content} for m in messages if m.role != "system"]

        params: dict[str, Any] = {"model": model, "messages": chat, "max_tokens": config.max_tokens}
        if system:
            params["system"] = system
        # 2) Anthropic acepta temperatura de 0 a 1 (OpenAI de 0 a 2): la recortamos.
        if config.temperature is not None:
            params["temperature"] = min(config.temperature, 1.0)
        return params

    async def _generate(
        self, messages: list[ChatMessage], config: GenerationConfig, model: str
    ) -> ModelResponse:
        resp = await self._client.messages.create(**self._params(messages, config, model))
        return ModelResponse(
            provider=self.provider,
            model=resp.model,
            content="".join(block.text for block in resp.content if block.type == "text"),
            finish_reason=resp.stop_reason,
            usage=Usage(
                input_tokens=resp.usage.input_tokens,
                output_tokens=resp.usage.output_tokens,
            ),
        )

    async def _stream(
        self, messages: list[ChatMessage], config: GenerationConfig, model: str
    ) -> AsyncIterator[str]:
        async with self._client.messages.stream(**self._params(messages, config, model)) as stream:
            async for text in stream.text_stream:
                yield text

    def _clasificar(self, exc: Exception) -> Clasificacion:
        return clasificar_estilo_openai(anthropic, exc)
