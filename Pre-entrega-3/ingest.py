"""Script de ingesta: carga los documentos de /data, los fragmenta y los guarda en ChromaDB."""
import argparse
import logging
import os

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger("rag")

DATA_DIR = "data"
VECTORSTORE_DIR = "vectorstore"
COLLECTION_NAME = "apuntes_curso"
EMBEDDINGS_MODEL = "intfloat/multilingual-e5-small"  # el mismo para indexar y consultar

CHUNK_SIZE = 500      # tokens
CHUNK_OVERLAP = 50    # tokens


def crear_embeddings() -> HuggingFaceEmbeddings:
    """Modelo de embeddings local (gratis, corre en la propia máquina)."""
    return HuggingFaceEmbeddings(
        model_name=EMBEDDINGS_MODEL,
        encode_kwargs={"normalize_embeddings": True},
    )


def cargar_documentos(carpeta: str = DATA_DIR) -> list[Document]:
    """Lee los archivos .txt y .md de la carpeta y los convierte en Documents."""
    documentos = []
    for archivo in sorted(os.listdir(carpeta)):
        if archivo.endswith((".txt", ".md")):
            with open(os.path.join(carpeta, archivo), encoding="utf-8") as f:
                documentos.append(Document(page_content=f.read(), metadata={"fuente": archivo}))
    logger.info("Documentos cargados: %d", len(documentos))
    return documentos


def fragmentar(documentos: list[Document]) -> list[Document]:
    """Divide los documentos en chunks de 500 tokens con 50 de overlap."""
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    chunks = splitter.split_documents(documentos)
    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_id"] = i
    logger.info("Chunks generados: %d", len(chunks))
    return chunks


def ingestar(embeddings: HuggingFaceEmbeddings | None = None, forzar: bool = False) -> Chroma:
    """Crea o abre la colección persistente y la puebla solo si está vacía."""
    embeddings = embeddings or crear_embeddings()
    vectorstore = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=VECTORSTORE_DIR,
        collection_metadata={"hnsw:space": "cosine"},
    )

    existentes = vectorstore._collection.count()
    if existentes > 0 and not forzar:
        logger.info("La colección '%s' ya existe con %d chunks -> se omite la ingesta",
                    COLLECTION_NAME, existentes)
        return vectorstore

    if forzar and existentes > 0:
        logger.info("Reindexando: se borra la colección anterior")
        vectorstore.reset_collection()

    chunks = fragmentar(cargar_documentos())
    ids = [f"{c.metadata['fuente']}-{c.metadata['chunk_id']}" for c in chunks]
    vectorstore.add_documents(chunks, ids=ids)
    logger.info("Ingesta completa: %d chunks guardados en ./%s", len(chunks), VECTORSTORE_DIR)
    return vectorstore


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
                        datefmt="%H:%M:%S")
    parser = argparse.ArgumentParser(description="Ingesta de documentos en ChromaDB")
    parser.add_argument("--forzar", action="store_true", help="Reindexa aunque la base ya exista")
    ingestar(forzar=parser.parse_args().forzar)