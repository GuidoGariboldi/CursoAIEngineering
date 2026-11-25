"""Ingesta: lee los Markdown de la base de conocimiento, los fragmenta por secciones y los guarda en ChromaDB."""
import argparse
import asyncio
import logging
import os

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from app.config import configurar_logs, obtener_config

logger = logging.getLogger("rag")


def cargar_documentos(carpeta: str) -> list[Document]:
    """Cada archivo .md empieza con una línea 'categoria: ...' que se guarda como metadato."""
    documentos = []
    for archivo in sorted(os.listdir(carpeta)):
        if not archivo.endswith(".md"):
            continue
        with open(os.path.join(carpeta, archivo), encoding="utf-8") as f:
            lineas = f.read().strip().splitlines()
        categoria = lineas[0].split(":", 1)[1].strip() if lineas[0].startswith("categoria:") else "general"
        documentos.append(Document(page_content="\n".join(lineas[1:]).strip(),
                                   metadata={"fuente": archivo, "categoria": categoria}))
    logger.info("Documentos de conocimiento cargados: %d", len(documentos))
    return documentos


def fragmentar(documentos: list[Document]) -> list[Document]:
    """Primero por títulos del Markdown (una sección = un tema) y después por tamaño."""
    cfg = obtener_config()
    por_titulos = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "titulo"), ("##", "seccion")], strip_headers=False)
    por_tamano = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base", chunk_size=cfg.rag_chunk_size, chunk_overlap=cfg.rag_chunk_overlap)

    chunks: list[Document] = []
    for doc in documentos:
        secciones = por_titulos.split_text(doc.page_content)
        for numero, chunk in enumerate(por_tamano.split_documents(secciones), start=1):
            chunk.metadata = {
                **doc.metadata,
                "titulo": chunk.metadata.get("titulo", doc.metadata["fuente"]),
                "seccion": chunk.metadata.get("seccion", ""),
                "chunk_id": f"{doc.metadata['fuente']}#{numero}",
            }
            chunks.append(chunk)
    logger.info("Fragmentos generados: %d", len(chunks))
    return chunks


async def crear_vectorstore(embeddings) -> Chroma:
    cfg = obtener_config()
    return await asyncio.to_thread(
        Chroma,
        collection_name=cfg.chroma_collection,
        embedding_function=embeddings,
        persist_directory=cfg.chroma_dir,
        collection_metadata={"hnsw:space": "cosine"},
    )


async def ingestar(vectorstore: Chroma, chunks: list[Document], forzar: bool = False) -> int:
    """Guarda los fragmentos solo si la colección está vacía (o si se fuerza la reindexación)."""
    existentes = await asyncio.to_thread(vectorstore._collection.count)
    if existentes and not forzar:
        logger.info("La colección ya tiene %d fragmentos -> se omite la ingesta", existentes)
        return existentes
    if existentes and forzar:
        logger.info("Reindexando: se vacía la colección")
        await asyncio.to_thread(vectorstore.reset_collection)
    await vectorstore.aadd_documents(chunks, ids=[c.metadata["chunk_id"] for c in chunks])
    logger.info("Ingesta completa: %d fragmentos en ChromaDB", len(chunks))
    return len(chunks)


async def _main(forzar: bool) -> None:
    from app.rag.retriever import base_conocimiento
    await base_conocimiento.inicializar(forzar=forzar)


if __name__ == "__main__":
    configurar_logs()
    parser = argparse.ArgumentParser(description="Ingesta de la base de conocimiento en ChromaDB")
    parser.add_argument("--forzar", action="store_true", help="Reindexa aunque ya haya datos")
    asyncio.run(_main(parser.parse_args().forzar))
