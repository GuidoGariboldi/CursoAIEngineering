"""Configuración compartida por todos los scripts."""
import logging
import os

from dotenv import load_dotenv

load_dotenv()

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_NAME = os.getenv("INDEX_NAME", "curso-ai-engineering")
NAMESPACE = os.getenv("NAMESPACE", "fastapi-docs")   # separa este dataset dentro del índice
CLOUD = "aws"
REGION = "us-east-1"                                 # región del plan gratuito

EMBEDDINGS_MODEL = "intfloat/multilingual-e5-small"  # el mismo para indexar y consultar

DATA_DIR = "data"
GOLDEN_SET_PATH = "golden_set.json"
CHUNK_SIZE = 600      # tokens (entre 500 y 800)
CHUNK_OVERLAP = 60    # tokens
TOP_K = 5


def configurar_logs():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    for ruidoso in ("httpx", "urllib3", "sentence_transformers", "pinecone"):
        logging.getLogger(ruidoso).setLevel(logging.WARNING)


def crear_embeddings():
    """Modelo de embeddings local y gratuito (384 dimensiones)."""
    from langchain_huggingface import HuggingFaceEmbeddings
    return HuggingFaceEmbeddings(
        model_name=EMBEDDINGS_MODEL,
        encode_kwargs={"normalize_embeddings": True},
    )