"""Pipeline de ingesta: carga los .md de /data, los fragmenta y los sube a Pinecone."""
import argparse
import logging
import os
import time

from langchain_core.documents import Document
from langchain_pinecone import PineconeVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import (CHUNK_OVERLAP, CHUNK_SIZE, DATA_DIR, NAMESPACE,
                    configurar_logs, crear_embeddings)
from setup_index import inicializar_indice

logger = logging.getLogger("rag")


def cargar_documentos(carpeta: str = DATA_DIR) -> list[Document]:
    """Lee los .md de la carpeta. La primera línea indica la categoría."""
    documentos = []
    for archivo in sorted(os.listdir(carpeta)):
        if not archivo.endswith(".md"):
            continue
        with open(os.path.join(carpeta, archivo), encoding="utf-8") as f:
            lineas = f.read().strip().splitlines()

        categoria = lineas[0].split(":", 1)[1].strip() if lineas[0].startswith("categoria:") else "general"
        contenido = "\n".join(lineas[1:]).strip()
        titulo = next((l.lstrip("# ").strip() for l in lineas if l.startswith("# ")), archivo)

        documentos.append(Document(
            page_content=contenido,
            metadata={"fuente": archivo, "titulo": titulo, "categoria": categoria},
        ))
    logger.info("Documentos cargados: %d", len(documentos))
    return documentos


def fragmentar(documentos: list[Document]) -> list[Document]:
    """Divide cada documento en chunks y los numera como páginas."""
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    chunks = []
    for doc in documentos:
        for pagina, texto in enumerate(splitter.split_text(doc.page_content), start=1):
            metadata = {**doc.metadata, "pagina": pagina,
                        "chunk_id": f"{doc.metadata['fuente']}#{pagina}"}
            chunks.append(Document(page_content=texto, metadata=metadata))
    logger.info("Chunks generados: %d", len(chunks))
    return chunks


def contar_vectores(index) -> int:
    stats = index.describe_index_stats()
    ns = (stats.namespaces or {}).get(NAMESPACE)
    return ns.vector_count if ns else 0


def crear_vectorstore(index, embeddings) -> PineconeVectorStore:
    return PineconeVectorStore(
        index=index,
        embedding=embeddings,
        namespace=NAMESPACE,
        text_key="texto",   # el texto original se guarda en la metadata
    )


def ingestar(index, embeddings, forzar: bool = False) -> PineconeVectorStore:
    """Sube los chunks al namespace solo si está vacío (o si se fuerza)."""
    vectorstore = crear_vectorstore(index, embeddings)
    existentes = contar_vectores(index)

    if existentes > 0 and not forzar:
        logger.info("El namespace '%s' ya tiene %d vectores -> se omite la ingesta",
                    NAMESPACE, existentes)
        return vectorstore

    if forzar and existentes > 0:
        logger.info("Reindexando: se borran los vectores del namespace '%s'", NAMESPACE)
        index.delete(delete_all=True, namespace=NAMESPACE)

    chunks = fragmentar(cargar_documentos())
    ids = [c.metadata["chunk_id"] for c in chunks]
    vectorstore.add_documents(chunks, ids=ids)
    logger.info("Subidos %d chunks a Pinecone (namespace '%s')", len(chunks), NAMESPACE)

    # Pinecone tarda unos segundos en reflejar los vectores nuevos
    for _ in range(30):
        if contar_vectores(index) >= len(chunks):
            break
        time.sleep(2)
    logger.info("Vectores disponibles en el namespace: %d", contar_vectores(index))
    return vectorstore


if __name__ == "__main__":
    configurar_logs()
    parser = argparse.ArgumentParser(description="Ingesta de documentos en Pinecone")
    parser.add_argument("--forzar", action="store_true", help="Reindexa aunque ya haya datos")
    args = parser.parse_args()

    embeddings = crear_embeddings()
    index = inicializar_indice(len(embeddings.embed_query("prueba")))
    ingestar(index, embeddings, forzar=args.forzar)