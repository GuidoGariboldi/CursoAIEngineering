"""Setup de Pinecone: verifica si el índice existe y lo crea en modo Serverless si hace falta."""
import logging

from pinecone import Pinecone, ServerlessSpec

from config import CLOUD, INDEX_NAME, PINECONE_API_KEY, REGION, configurar_logs, crear_embeddings

logger = logging.getLogger("rag")


def inicializar_indice(dimension: int):
    """Crea el índice si no existe y verifica que la dimensión coincida con el modelo."""
    if not PINECONE_API_KEY:
        raise ValueError("Falta PINECONE_API_KEY en el archivo .env")

    pc = Pinecone(api_key=PINECONE_API_KEY)
    existentes = [i.name for i in pc.list_indexes()]

    if INDEX_NAME in existentes:
        logger.info("El índice '%s' ya existe", INDEX_NAME)
    else:
        logger.info("Creando índice serverless '%s' (dim=%d, %s/%s)...",
                    INDEX_NAME, dimension, CLOUD, REGION)
        pc.create_index(
            name=INDEX_NAME,
            dimension=dimension,
            metric="cosine",
            spec=ServerlessSpec(cloud=CLOUD, region=REGION),
        )
        logger.info("Índice creado")

    descripcion = pc.describe_index(INDEX_NAME)
    if descripcion.dimension != dimension:
        raise ValueError(
            f"Mismatch de dimensiones: el índice tiene {descripcion.dimension} "
            f"y el modelo de embeddings genera {dimension}"
        )
    logger.info("Dimensión verificada: %d", dimension)
    return pc.Index(INDEX_NAME)


if __name__ == "__main__":
    configurar_logs()
    dimension = len(crear_embeddings().embed_query("prueba"))
    index = inicializar_indice(dimension)
    print(index.describe_index_stats())