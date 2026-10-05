"""Cliente de Gemini sobre el SDK google-genai (parte asíncrona: client.aio)."""

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from .base import BaseLLMClient, Clasificacion
from .schemas import ChatMessage, ErrorType, GenerationConfig, ModelResponse, Provider, Usage


class GeminiClient(BaseLLMClient):
    provider = Provider.GEMINI

    def __init__(
        self,
        api_key: str,
        default_model: str = "gemini-flash-lite-latest",
        timeout: float = 30.0,
        max_retries: int = 2,
    ) -> None:
        super().__init__(default_model)
        self._max_retries = max_retries
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=int(timeout * 1000)),  # en milisegundos
        )

    @staticmethod
    def _params(messages: list[ChatMessage], config: GenerationConfig, model: str) -> dict[str, Any]:
        """Gemini separa el system prompt y llama 'model' al rol del asistente."""
        system = "\n\n".join(m.content for m in messages if m.role == "system")
        contents = [
            types.Content(
                role="model" if m.role == "assistant" else "user",
                parts=[types.Part(text=m.content)],
            )
            for m in messages
            if m.role != "system"
        ]
        return {
            "model": model,
            "contents": contents,
            "config": types.GenerateContentConfig(
                temperature=config.temperature,
                max_output_tokens=config.max_tokens,
                system_instruction=system or None,
            ),
        }

    async def _generate(
        self, messages: list[ChatMessage], config: GenerationConfig, model: str
    ) -> ModelResponse:
        params = self._params(messages, config, model)
        # Este SDK no reintenta por su cuenta: el reintento con backoff se hace acá.
        for intento in range(self._max_retries + 1):
            try:
                resp = await self._client.aio.models.generate_content(**params)
                break
            except Exception as exc:
                reintentable = self._clasificar(exc)[2]
                if intento == self._max_retries or not reintentable:
                    raise
                await asyncio.sleep(2**intento)  # backoff: 1s, 2s, 4s...

        usage = None
        meta = resp.usage_metadata
        if meta and meta.prompt_token_count is not None:
            usage = Usage(
                input_tokens=meta.prompt_token_count,
                output_tokens=meta.candidates_token_count or 0,
            )
        finish = resp.candidates[0].finish_reason if resp.candidates else None
        return ModelResponse(
            provider=self.provider,
            model=model,
            content=resp.text or "",
            finish_reason=getattr(finish, "name", None),
            usage=usage,
        )

    async def _stream(
        self, messages: list[ChatMessage], config: GenerationConfig, model: str
    ) -> AsyncIterator[str]:
        stream = await self._client.aio.models.generate_content_stream(
            **self._params(messages, config, model)
        )
        async for chunk in stream:
            if chunk.text:
                yield chunk.text

    def _clasificar(self, exc: Exception) -> Clasificacion:
        if isinstance(exc, genai_errors.APIError):
            codigo = exc.code if isinstance(exc.code, int) else 0
            if codigo == 429:
                return ErrorType.RATE_LIMIT, "Límite de tasa o cuota alcanzado.", True
            if codigo in (401, 403) or "API key" in str(exc):
                return ErrorType.AUTHENTICATION, "API key inválida o sin permisos.", False
            if codigo >= 500:
                return ErrorType.API_ERROR, f"El servicio de Gemini no está disponible (error {codigo}).", True
            detalle = getattr(exc, "message", None) or str(exc)
            return ErrorType.API_ERROR, f"La API respondió con error {codigo}: {detalle}", False
        if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
            return ErrorType.TIMEOUT, "La API tardó demasiado en responder.", True
        if isinstance(exc, (httpx.TransportError, OSError)):
            return ErrorType.CONNECTION, "No se pudo conectar con la API (error de red).", True
        return ErrorType.UNKNOWN, f"Error inesperado: {exc!r}", False

    async def aclose(self) -> None:
        cerrar = getattr(self._client.aio, "aclose", None)
        if cerrar is not None:
            await cerrar()
