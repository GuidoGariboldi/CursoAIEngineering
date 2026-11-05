"""Configuración compartida del agente."""
import logging
import os

from dotenv import load_dotenv

load_dotenv()

GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
DB_CHECKPOINTS: str = os.getenv("DB_CHECKPOINTS", "checkpoints.db")
RECURSION_LIMIT: int = 10        # techo de pasos por consulta (evita bucles infinitos)
MAX_MENSAJES: int = 20           # máximo de mensajes que se le pasan al modelo
PAUSA_ENTRE_PREGUNTAS: int = int(os.getenv("PAUSA_ENTRE_PREGUNTAS", "20"))  # segundos (plan gratuito)
TRAZA_PATH: str = "traza_react.json"


def configurar_logs() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    for ruidoso in ("httpx", "google_genai", "aiosqlite"):
        logging.getLogger(ruidoso).setLevel(logging.WARNING)