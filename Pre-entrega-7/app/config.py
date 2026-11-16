"""Configuración compartida y utilidades."""
import logging
import os
import unicodedata

from dotenv import load_dotenv
from langchain_core.messages import BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()


def _lista(variable: str, por_defecto: str) -> list[str]:
    return [m.strip() for m in os.getenv(variable, por_defecto).split(",") if m.strip()]


REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
PHOENIX_COLLECTOR_ENDPOINT: str = os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006/v1/traces")
PHOENIX_PROJECT_NAME: str = os.getenv("PHOENIX_PROJECT_NAME", "orquestador-api")

# Cada lista es un modelo principal y sus respaldos (si uno falla, se usa el siguiente)
MODELOS_SUPERVISOR: list[str] = _lista(
    "MODELOS_SUPERVISOR", "gemini-3.1-flash-lite,gemini-3.5-flash-lite,gemini-flash-lite-latest")
MODELOS_ESPECIALISTAS: list[str] = _lista(
    "MODELOS_ESPECIALISTAS", "gemini-3.5-flash,gemini-3.1-flash-lite,gemini-3.5-flash-lite")

MAX_PASOS_SUPERVISOR: int = 6          # condición de parada del supervisor
RECURSION_LIMIT_ESPECIALISTA: int = 8
RECURSION_LIMIT_GRAFO: int = 25
PAUSA_ENTRE_NODOS: int = int(os.getenv("PAUSA_ENTRE_NODOS", "5"))   # segundos (plan gratuito)
WORKERS: int = int(os.getenv("WORKERS", "2"))                       # trabajos procesados en paralelo
JOB_TTL_SEGUNDOS: int = 60 * 60 * 24                                # los trabajos se guardan 24 horas


def configurar_logs() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    for ruidoso in ("httpx", "google_genai", "opentelemetry"):
        logging.getLogger(ruidoso).setLevel(logging.WARNING)


def crear_llm(modelo: str, reintentos: int = 1) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(model=modelo, temperature=0, max_retries=reintentos)


def texto_de(mensaje: BaseMessage) -> str:
    """Extrae el texto de un mensaje (Gemini a veces devuelve el contenido en bloques)."""
    contenido = mensaje.content
    if isinstance(contenido, str):
        return contenido
    return "".join(b.get("text", "") for b in contenido if isinstance(b, dict) and b.get("type") == "text")


def normalizar(texto: str) -> str:
    """Minúsculas y sin tildes, para comparar textos."""
    sin_tildes = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in sin_tildes if unicodedata.category(c) != "Mn")
