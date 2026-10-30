"""Recuperador híbrido: combina BM25 (léxico) con Pinecone (semántico) en un EnsembleRetriever."""
import asyncio
import logging
import re

from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

try:
    from langchain_classic.retrievers import EnsembleRetriever
except ImportError:
    from langchain.retrievers import EnsembleRetriever

from config import TOP_K, configurar_logs, crear_embeddings
from ingest import cargar_documentos, fragmentar, ingestar
from setup_index import inicializar_indice

logger = logging.getLogger("rag")


def tokenizar(texto: str) -> list[str]:
    """Minúsculas y sin signos, para que 'HTTPException.' coincida con 'httpexception'."""
    return re.findall(r"\w+", texto.lower())


class RAGSystem:
    """Encapsula un EnsembleRetriever que combina BM25 (léxico) y Pinecone (semántico)."""

    def __init__(self, vectorstore, documentos: list[Document], k: int = TOP_K,
                 pesos: tuple[float, float] = (0.5, 0.5)):
        self.k = k
        self.vector_retriever = vectorstore.as_retriever(search_kwargs={"k": k})

        self.bm25_retriever = BM25Retriever.from_documents(documentos, preprocess_func=tokenizar)
        self.bm25_retriever.k = k

        self.hybrid_retriever = EnsembleRetriever(
            retrievers=[self.bm25_retriever, self.vector_retriever],
            weights=list(pesos),
        )
        self.retrievers = {
            "bm25": self.bm25_retriever,
            "vectorial": self.vector_retriever,
            "hibrido": self.hybrid_retriever,
        }
        logger.info("RAGSystem listo: k=%d, pesos BM25/vectorial=%s, %d documentos para BM25",
                    k, pesos, len(documentos))

    async def buscar(self, query: str, modo: str = "hibrido") -> list[Document]:
        """Devuelve los top-k documentos para la consulta."""
        if modo not in self.retrievers:
            raise ValueError(f"Modo inválido: {modo!r}. Opciones: {list(self.retrievers)}")
        docs = (await self.retrievers[modo].ainvoke(query))[: self.k]
        logger.info("[%s] '%s' -> %s", modo, query, [d.metadata["fuente"] for d in docs])
        return docs


def crear_rag_system() -> RAGSystem:
    """Arma todo el sistema: embeddings, índice, ingesta (si hace falta) y RAGSystem."""
    embeddings = crear_embeddings()
    index = inicializar_indice(len(embeddings.embed_query("prueba")))
    vectorstore = ingestar(index, embeddings)
    return RAGSystem(vectorstore, documentos=fragmentar(cargar_documentos()))


async def main():
    rag = crear_rag_system()
    consulta = "¿Cómo devuelvo un error 404 con un mensaje personalizado?"
    for modo in ("bm25", "vectorial", "hibrido"):
        docs = await rag.buscar(consulta, modo=modo)
        print(f"\n=== {modo.upper()} ===")
        for posicion, d in enumerate(docs, start=1):
            print(f"{posicion}. {d.metadata['fuente']:<22} [{d.metadata['categoria']}]")


if __name__ == "__main__":
    configurar_logs()
    asyncio.run(main())