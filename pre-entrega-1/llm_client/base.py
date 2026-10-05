"""Clase base abstracta: interfaz común + manejo de errores compartido."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Sequence
from typing import Any, ClassVar

from pydantic import TypeAdapter

from .schemas import (
    ChatMessage,
    ErrorInfo,
    ErrorType,
    GenerationConfig,
    ModelResponse,
    Provider,
    StreamChunk,
)

_MESSAGES = TypeAdapter(list[ChatMessage])

# (tipo de error, mensaje, ¿tiene sentido reintentar?)
Clasificacion = tuple[ErrorType, str, bool]


class BaseLLMClient(ABC):
    """Contrato que todo proveedor debe cumplir.

    Los métodos públicos (`generate` y `stream`) viven acá y nunca lanzan
    excepciones por fallas de la API: las convierten en un `ErrorInfo`.
    Cada proveedor solo implementa `_generate`, `_stream` y `_clasificar`.
    """

    provider: ClassVar[Provider]
    _client: Any

    def __init__(self, default_model: str) -> None:
        self.default_model = default_model

    # ---------- API pública ----------

    async def generate(
        self,
        messages: Sequence[ChatMessage | dict],
        config: GenerationConfig | None = None,
    ) -> ModelResponse:
        """Modo normal: espera la respuesta completa."""
        config = config or GenerationConfig()
        model = config.model or self.default_model
        try:
            validated = self._validate(messages)
            return await self._generate(validated, config, model)
        except Exception as exc:  # CancelledError no es Exception: la cancelación sigue funcionando
            return ModelResponse(provider=self.provider, model=model, error=self._to_error(exc))

    async def stream(
        self,
        messages: Sequence[ChatMessage | dict],
        config: GenerationConfig | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Modo streaming: generador asíncrono que entrega el texto a medida que llega."""
        config = config or GenerationConfig()
        model = config.model or self.default_model
        try:
            validated = self._validate(messages)
            async for text in self._stream(validated, config, model):
                yield StreamChunk(content=text)
        except Exception as exc:
            yield StreamChunk(error=self._to_error(exc))

    async def aclose(self) -> None:
        """Cierra las conexiones HTTP del SDK (si el SDK lo permite)."""
        cerrar = getattr(self._client, "close", None)
        if cerrar is not None:
            await cerrar()

    # ---------- A implementar por cada proveedor ----------

    @abstractmethod
    async def _generate(
        self, messages: list[ChatMessage], config: GenerationConfig, model: str
    ) -> ModelResponse: ...

    @abstractmethod
    def _stream(
        self, messages: list[ChatMessage], config: GenerationConfig, model: str
    ) -> AsyncIterator[str]: ...

    @abstractmethod
    def _clasificar(self, exc: Exception) -> Clasificacion: ...

    # ---------- Helpers compartidos ----------

    @staticmethod
    def _validate(messages: Sequence[ChatMessage | dict]) -> list[ChatMessage]:
        validated = _MESSAGES.validate_python(list(messages))
        if not validated:
            raise ValueError("La lista de mensajes está vacía.")
        return validated

    def _to_error(self, exc: Exception) -> ErrorInfo:
        """Traduce cualquier excepción a un error estructurado."""
        if isinstance(exc, ValueError):  # incluye el ValidationError de Pydantic
            tipo, mensaje, retryable = ErrorType.VALIDATION, f"Entrada inválida: {exc}", False
        else:
            tipo, mensaje, retryable = self._clasificar(exc)
        codigo = getattr(exc, "status_code", None) or getattr(exc, "code", None)
        return ErrorInfo(
            type=tipo,
            message=mensaje,
            provider=self.provider,
            status_code=codigo if isinstance(codigo, int) else None,
            retryable=retryable,
        )


def clasificar_estilo_openai(sdk: Any, exc: Exception) -> Clasificacion:
    """Los SDK de OpenAI y Anthropic nombran igual sus excepciones: se mapean una sola vez.

    El orden importa: APITimeoutError hereda de APIConnectionError,
    y RateLimitError / AuthenticationError heredan de APIStatusError.
    """
    if isinstance(exc, sdk.APITimeoutError):
        return ErrorType.TIMEOUT, "La API tardó demasiado en responder.", True
    if isinstance(exc, sdk.APIConnectionError):
        return ErrorType.CONNECTION, "No se pudo conectar con la API (error de red).", True
    if isinstance(exc, sdk.RateLimitError):
        return ErrorType.RATE_LIMIT, "Límite de tasa o cuota alcanzado.", True
    if isinstance(exc, (sdk.AuthenticationError, sdk.PermissionDeniedError)):
        return ErrorType.AUTHENTICATION, "API key inválida o sin permisos.", False
    if isinstance(exc, sdk.APIStatusError):
        return (
            ErrorType.API_ERROR,
            f"La API respondió con error {exc.status_code}: {exc.message}",
            exc.status_code >= 500,
        )
    return ErrorType.UNKNOWN, f"Error inesperado: {exc!r}", False
