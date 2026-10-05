"""Esquemas Pydantic: todo lo que entra y sale del cliente está tipado y validado."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Provider(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"


class ChatMessage(BaseModel):
    """Un mensaje de la conversación."""

    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1)


class GenerationConfig(BaseModel):
    """Parámetros de entrada del modelo. Pydantic rechaza valores fuera de rango."""

    model_config = ConfigDict(extra="forbid")  # un parámetro mal escrito es un error, no se ignora

    # None = usar el modelo por defecto del cliente
    model: str | None = None
    # None = no enviar temperatura (algunos modelos de razonamiento no la aceptan)
    temperature: float | None = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, gt=0, le=8192)


class ErrorType(StrEnum):
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    API_ERROR = "api_error"
    UNKNOWN = "unknown"


class ErrorInfo(BaseModel):
    """Error controlado: lo que devolvemos en lugar de dejar escapar una excepción."""

    type: ErrorType
    message: str
    provider: Provider
    status_code: int | None = None
    retryable: bool = False


class Usage(BaseModel):
    input_tokens: int
    output_tokens: int


class ModelResponse(BaseModel):
    """Respuesta unificada del modo normal. Si falló, `error` viene completo."""

    provider: Provider
    model: str
    content: str = ""
    finish_reason: str | None = None
    usage: Usage | None = None
    error: ErrorInfo | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


class StreamChunk(BaseModel):
    """Un fragmento del stream. Si algo falla a mitad de camino, llega un chunk con `error`."""

    content: str = ""
    error: ErrorInfo | None = None

    @property
    def ok(self) -> bool:
        return self.error is None
