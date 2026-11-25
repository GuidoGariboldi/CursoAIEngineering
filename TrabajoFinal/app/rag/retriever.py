"""Recuperador híbrido sobre la base de conocimiento: BM25 (palabras exactas) + ChromaDB (significado)."""
import asyncio
import logging
import re

from langchain_community.retrievers import BM25Retriever
from langchain_huggingface import HuggingFaceEmbeddings

try:
    from langchain_classic.retrievers import EnsembleRetriever
except ImportError:
    from langchain.retrievers import EnsembleRetriever

from app.config import obtener_config
from app.rag.ingest import cargar_documentos, crear_vectorstore, fragmentar, ingestar
from app.schemas import BuscarConocimientoOut, FragmentoOut

logger = logging.getLogger("rag")


def tokenizar(texto: str) -> list[str]:
    """Minúsculas y sin signos, para que BM25 encuentre los términos aunque cambie la escritura."""
    return re.findall(r"\w+", texto.lower())


class BaseConocimiento:
    def __init__(self) -> None:
        self._retriever: EnsembleRetriever | None = None
        self.cantidad_fragmentos = 0

    async def inicializar(self, forzar: bool = False) -> None:
        cfg = obtener_config()
        # Cargar el modelo de embeddings es pesado y sincrónico: se hace en otro hilo
        embeddings = await asyncio.to_thread(
            HuggingFaceEmbeddings, model_name=cfg.embeddings_model,
            encode_kwargs={"normalize_embeddings": True})
        vectorstore = await crear_vectorstore(embeddings)

        chunks = fragmentar(cargar_documentos(cfg.conocimiento_dir))
        self.cantidad_fragmentos = await ingestar(vectorstore, chunks, forzar)

        bm25 = BM25Retriever.from_documents(chunks, preprocess_func=tokenizar)
        bm25.k = cfg.rag_top_k
        vectorial = vectorstore.as_retriever(search_kwargs={"k": cfg.rag_top_k})
        self._retriever = EnsembleRetriever(retrievers=[bm25, vectorial],
                                            weights=[cfg.rag_peso_bm25, 1 - cfg.rag_peso_bm25])
        logger.info("Base de conocimiento lista: %d fragmentos, top_k=%d", self.cantidad_fragmentos, cfg.rag_top_k)

    async def buscar(self, consulta: str) -> BuscarConocimientoOut:
        if self._retriever is None:
            return BuscarConocimientoOut(consulta=consulta, error="La base de conocimiento no está inicializada.")
        docs = (await self._retriever.ainvoke(consulta))[: obtener_config().rag_top_k]
        logger.info("RAG '%s' -> %s", consulta, [d.metadata["chunk_id"] for d in docs])
        return BuscarConocimientoOut(
            consulta=consulta,
            fragmentos=[FragmentoOut(fuente=d.metadata["fuente"],
                                     titulo=d.metadata.get("seccion") or d.metadata.get("titulo", ""),
                                     contenido=d.page_content) for d in docs],
        )


base_conocimiento = BaseConocimiento()
