"""Configuración compartida y utilidades."""
import logging
import os
import unicodedata

from dotenv import load_dotenv
from langchain_core.messages import BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

MODELO_SUPERVISOR: str = os.getenv("MODELO_SUPERVISOR", "gemini-3.1-flash-lite")
MODELOS_SUPERVISOR_RESPALDO: list[str] = [
    m.strip() for m in os.getenv("MODELOS_SUPERVISOR_RESPALDO",
                                 "gemini-3.5-flash-lite,gemini-flash-lite-latest").split(",")
    if m.strip()
]
MODELO_ESPECIALISTAS: str = os.getenv("MODELO_ESPECIALISTAS", "gemini-3.5-flash")

MAX_PASOS_SUPERVISOR: int = 6        # condición de parada: evita el "supervisor infinito"
RECURSION_LIMIT_ESPECIALISTA: int = 8
RECURSION_LIMIT_GRAFO: int = 25
PAUSA_ENTRE_NODOS: int = int(os.getenv("PAUSA_ENTRE_NODOS", "10"))  # segundos (plan gratuito)

TRAZA_PATH: str = "traza_orquestador.json"
DIAGRAMA_PATH: str = "grafo.png"


def configurar_logs() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    for ruidoso in ("httpx", "google_genai"):
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