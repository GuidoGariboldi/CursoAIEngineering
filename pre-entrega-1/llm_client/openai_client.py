"""Cliente de OpenAI (Chat Completions) sobre AsyncOpenAI."""

from collections.abc import AsyncIterator
from typing import Any

import openai
from openai import AsyncOpenAI

from .base import BaseLLMClient, Clasificacion, clasificar_estilo_openai
from .schemas import ChatMessage, GenerationConfig, ModelResponse, Provider, Usage


class OpenAIClient(BaseLLMClient):
    provider = Provider.OPENAI

    def __init__(
        self,
        api_key: str,
        default_model: str = "gpt-4.1-mini",
        timeout: float = 30.0,
        max_retries: int = 2,
    ) -> None:
        super().__init__(default_model)
        # max_retries: el SDK reintenta solo (con backoff exponencial) ante
        # errores de red, 429 y 5xx antes de darse por vencido.
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout, max_retries=max_retries)

    @staticmethod
    def _params(messages: list[ChatMessage], config: GenerationConfig, model: str) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": model,
            "messages": [m.model_dump() for m in messages],
            "max_completion_tokens": config.max_tokens,
        }
        if config.temperature is not None:
            params["temperature"] = config.temperature
        return params

    async def _generate(
        self, messages: list[ChatMessage], config: GenerationConfig, model: str
    ) -> ModelResponse:
        resp = await self._client.chat.completions.create(**self._params(messages, config, model))
        choice = resp.choices[0]
        usage = None
        if resp.usage:
            usage = Usage(
                input_tokens=resp.usage.prompt_tokens,
                output_tokens=resp.usage.completion_tokens,
            )
        return ModelResponse(
            provider=self.provider,
            model=resp.model,
            content=choice.message.content or "",
            finish_reason=choice.finish_reason,
            usage=usage,
        )

    async def _stream(
        self, messages: list[ChatMessage], config: GenerationConfig, model: str
    ) -> AsyncIterator[str]:
        stream = await self._client.chat.completions.create(
            **self._params(messages, config, model), stream=True
        )
        async for chunk in stream:
            if chunk.choices and (delta := chunk.choices[0].delta.content):
                yield delta

    def _clasificar(self, exc: Exception) -> Clasificacion:
        return clasificar_estilo_openai(openai, exc)
