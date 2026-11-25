"""Configuración del sistema: se lee de variables de entorno y se valida con Pydantic."""
import logging
import os
import unicodedata
from functools import lru_cache

from dotenv import load_dotenv
from langchain_core.messages import BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field, field_validator

load_dotenv()


class Configuracion(BaseModel):
    """Todos los parámetros vienen del entorno: no hay modelos ni nombres de índices en el código."""

    redis_url: str = Field(min_length=1)
    phoenix_collector_endpoint: str = Field(min_length=1)
    phoenix_project_name: str = Field(min_length=1)

    modelos_supervisor: list[str] = Field(min_length=1)    # principal + respaldos
    modelos_especialistas: list[str] = Field(min_length=1)
    llm_timeout: float = Field(gt=0, le=600)               # segundos máximos por llamada al modelo

    embeddings_model: str = Field(min_length=1)
    conocimiento_dir: str = "conocimiento"
    chroma_dir: str = "vectorstore"
    chroma_collection: str = Field(min_length=1)
    rag_top_k: int = Field(ge=1, le=10)
    rag_chunk_size: int = Field(ge=100, le=2000)
    rag_chunk_overlap: int = Field(ge=0, le=500)
    rag_peso_bm25: float = Field(ge=0, le=1)               # el resto es para la búsqueda vectorial

    max_pasos_supervisor: int = Field(ge=1, le=20)
    recursion_limit_especialista: int = Field(ge=2, le=50)
    recursion_limit_grafo: int = Field(ge=5, le=100)
    max_mensajes_historial: int = Field(ge=2, le=50)
    pausa_entre_nodos: float = Field(ge=0, le=60)          # respeta el límite por minuto del plan gratuito
    workers: int = Field(ge=1, le=16)
    job_ttl_segundos: int = Field(ge=60)

    @field_validator("modelos_supervisor", "modelos_especialistas", mode="before")
    @classmethod
    def separar_lista(cls, valor: str | list[str]) -> list[str]:
        if isinstance(valor, str):
            return [m.strip() for m in valor.split(",") if m.strip()]
        return valor


@lru_cache
def obtener_config() -> Configuracion:
    e = os.environ.get
    return Configuracion(
        redis_url=e("REDIS_URL", "redis://localhost:6379"),
        phoenix_collector_endpoint=e("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006/v1/traces"),
        phoenix_project_name=e("PHOENIX_PROJECT_NAME", "intelligence-system"),
        modelos_supervisor=e("MODELOS_SUPERVISOR", "gemini-3.5-flash-lite"),
        modelos_especialistas=e("MODELOS_ESPECIALISTAS", "gemini-3.5-flash"),
        llm_timeout=e("LLM_TIMEOUT", "60"),
        embeddings_model=e("EMBEDDINGS_MODEL", "intfloat/multilingual-e5-small"),
        conocimiento_dir=e("CONOCIMIENTO_DIR", "conocimiento"),
        chroma_dir=e("CHROMA_DIR", "vectorstore"),
        chroma_collection=e("CHROMA_COLLECTION", "conocimiento_tienda"),
        rag_top_k=e("RAG_TOP_K", "4"),
        rag_chunk_size=e("RAG_CHUNK_SIZE", "500"),
        rag_chunk_overlap=e("RAG_CHUNK_OVERLAP", "50"),
        rag_peso_bm25=e("RAG_PESO_BM25", "0.5"),
        max_pasos_supervisor=e("MAX_PASOS_SUPERVISOR", "8"),
        recursion_limit_especialista=e("RECURSION_LIMIT_ESPECIALISTA", "10"),
        recursion_limit_grafo=e("RECURSION_LIMIT_GRAFO", "30"),
        max_mensajes_historial=e("MAX_MENSAJES_HISTORIAL", "10"),
        pausa_entre_nodos=e("PAUSA_ENTRE_NODOS", "4"),
        workers=e("WORKERS", "2"),
        job_ttl_segundos=e("JOB_TTL_SEGUNDOS", "86400"),
    )


def configurar_logs() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    for ruidoso in ("httpx", "google_genai", "opentelemetry", "chromadb", "sentence_transformers"):
        logging.getLogger(ruidoso).setLevel(logging.WARNING)


def crear_llm(modelo: str, reintentos: int = 1) -> ChatGoogleGenerativeAI:
    """Cliente asíncrono de Gemini con un tiempo máximo por llamada."""
    return ChatGoogleGenerativeAI(model=modelo, temperature=0, max_retries=reintentos,
                                  timeout=obtener_config().llm_timeout)


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
