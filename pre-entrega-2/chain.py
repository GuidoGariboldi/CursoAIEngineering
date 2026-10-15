"""Pipeline LCEL: prompt | modelo con salida estructurada | validación, con reintentos."""
import logging
import os

from dotenv import load_dotenv
from langchain_core.exceptions import OutputParserException
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from pydantic import ValidationError

from schemas import ExtraccionTecnica

load_dotenv()
logger = logging.getLogger("pipeline")


# ---------- Errores propios ----------
class RespuestaIncompletaError(Exception):
    """El modelo cortó la respuesta por límite de tokens."""


class SalidaInvalidaError(Exception):
    """El modelo devolvió JSON mal formado o que no cumple el esquema."""


# ---------- Modelo (reutiliza LLM_PROVIDER del Módulo 1) ----------
def crear_modelo():
    proveedor = os.getenv("LLM_PROVIDER", "gemini").lower()
    temperatura = float(os.getenv("LLM_TEMPERATURE", "0"))
    max_tokens = int(os.getenv("LLM_MAX_TOKENS", "2048"))

    if proveedor == "openai":
        from langchain_openai import ChatOpenAI
        nombre = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        modelo = ChatOpenAI(model=nombre, temperature=temperatura,
                            max_tokens=max_tokens, max_retries=2)
    elif proveedor == "anthropic":
        from langchain_anthropic import ChatAnthropic
        nombre = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")
        # Anthropic solo acepta temperatura entre 0 y 1
        modelo = ChatAnthropic(model=nombre, temperature=min(temperatura, 1.0),
                               max_tokens=max_tokens, max_retries=2)
    elif proveedor == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        nombre = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
        modelo = ChatGoogleGenerativeAI(model=nombre, temperature=temperatura,
                                        max_output_tokens=max_tokens, max_retries=5)
    else:
        raise ValueError(f"LLM_PROVIDER no soportado: {proveedor!r}")

    logger.info("Modelo configurado: %s / %s (max_tokens=%d)", proveedor, nombre, max_tokens)
    return modelo


# ---------- Prompt template (sin f-strings) ----------
INSTRUCCIONES_FORMATO = """\
- tecnologias: solo las mencionadas explícitamente en el texto, con su nombre oficial \
(por ejemplo "PostgreSQL", no "postgres"). No inventes tecnologías.
- nivel_de_criticidad: "alta" si hay caída del servicio, pérdida de datos o riesgo de seguridad; \
"media" si hay degradación de rendimiento o errores intermitentes; \
"baja" si es una descripción sin problemas o una mejora menor.
- resumen_tecnico: una o dos oraciones en español, como máximo 300 caracteres."""

PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "Sos un analista técnico de software. Tu tarea es extraer entidades técnicas "
     "del texto que te pasa el usuario.\n\nReglas de formato:\n{instrucciones_formato}"),
    ("human", "Texto a analizar:\n<<<\n{texto}\n>>>"),
]).partial(instrucciones_formato=INSTRUCCIONES_FORMATO)


# ---------- Validación de la salida (finish_reason + parsing) ----------
def _finish_reason(mensaje) -> str:
    meta = getattr(mensaje, "response_metadata", None) or {}
    return str(meta.get("finish_reason") or meta.get("stop_reason") or "desconocido")


def validar_salida(resultado: dict) -> ExtraccionTecnica:
    """Recibe {'raw', 'parsed', 'parsing_error'} y devuelve el objeto validado o lanza error."""
    motivo = _finish_reason(resultado["raw"])
    logger.info("finish_reason del modelo: %s", motivo)

    # 1) Respuesta cortada por tokens: el objeto puede estar incompleto
    if any(m in motivo.upper() for m in ("LENGTH", "MAX_TOKENS")):
        logger.warning("Respuesta cortada por límite de tokens -> se reintentará")
        raise RespuestaIncompletaError(f"finish_reason={motivo}")

    # 2) JSON mal formado o que no cumple el esquema
    if resultado["parsing_error"] is not None:
        logger.warning("Salida inválida: %s -> se reintentará", resultado["parsing_error"])
        raise SalidaInvalidaError(str(resultado["parsing_error"]))

    parsed = resultado["parsed"]
    if parsed is None:
        logger.warning("El modelo no devolvió datos estructurados -> se reintentará")
        raise SalidaInvalidaError("Respuesta sin datos estructurados")
    if isinstance(parsed, dict):
        parsed = ExtraccionTecnica.model_validate(parsed)

    logger.info("Validación OK: %d tecnologías, criticidad=%s",
                len(parsed.tecnologias), parsed.nivel_de_criticidad.value)
    return parsed


# ---------- Cadena LCEL con reintentos ----------
def construir_cadena():
    modelo = crear_modelo()
    cadena = (
        PROMPT
        | modelo.with_structured_output(ExtraccionTecnica, include_raw=True)
        | RunnableLambda(validar_salida)
    )
    return cadena.with_retry(
        retry_if_exception_type=(
            SalidaInvalidaError,
            RespuestaIncompletaError,
            OutputParserException,
            ValidationError,
        ),
        wait_exponential_jitter=True,
        stop_after_attempt=3,  # 1 intento + 2 reintentos
    )


_cadena = None


def obtener_cadena():
    """Construye la cadena la primera vez que se usa."""
    global _cadena
    if _cadena is None:
        _cadena = construir_cadena()
    return _cadena


async def process_text(text: str) -> ExtraccionTecnica:
    """Ejecuta el pipeline de forma asíncrona y devuelve un objeto validado."""
    if not text or not text.strip():
        raise ValueError("El texto de entrada está vacío")

    logger.info("Procesando texto (%d caracteres)", len(text))
    try:
        resultado = await obtener_cadena().ainvoke({"texto": text})
    except Exception as error:
        logger.error("Falló después de los reintentos: %s: %s", type(error).__name__, error)
        raise
    logger.info("Pipeline terminado correctamente")
    return resultado