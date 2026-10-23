"""Cadena RAG asíncrona: recupera fragmentos de ChromaDB y genera una respuesta grounded."""
import asyncio
import json
import logging
import os

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.exceptions import OutputParserException
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnableParallel, RunnablePassthrough
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field, model_validator

from ingest import ingestar

load_dotenv()
logger = logging.getLogger("rag")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
TOP_K = 4  # fragmentos a recuperar (entre 3 y 5)


# ---------- Esquema de la respuesta ----------
class RespuestaRAG(BaseModel):
    """Respuesta del asistente basada solo en el contexto recuperado."""

    respuesta: str = Field(..., min_length=2, description='Respuesta en español. Si no está en el contexto: "No lo sé".')
    encontrado: bool = Field(..., description="True si la respuesta está en el contexto, False si no.")
    referencias: list[str] = Field(default_factory=list, description="Nombres de los archivos fuente usados para responder.")

    @model_validator(mode="after")
    def sin_referencias_si_no_sabe(self):
        if not self.encontrado:
            self.referencias = []
        return self


# ---------- Prompt de sistema ("filtro de veracidad") ----------
parser = PydanticOutputParser(pydantic_object=RespuestaRAG)

PROMPT_RAG = ChatPromptTemplate.from_messages([
    ("system",
    "Sos un asistente técnico. Respondé SOLO con la información del CONTEXTO.\n"
    "Reglas:\n"
    "- Si la respuesta no está en el contexto, respondé exactamente \"No lo se\" "
    "y poné encontrado en false.\n"
    "- No uses conocimiento propio ni inventes datos.\n"
    "- En referencias, poné solo los nombres de archivo (Fuente) que usaste.\n\n"
    "{format_instructions}"),
    ("human", "CONTEXTO:\n{contexto}\n\nPREGUNTA: {pregunta}"),
]).partial(format_instructions=parser.get_format_instructions())


def formatear_contexto(docs: list[Document]) -> str:
    """Une los fragmentos recuperados indicando de qué archivo viene cada uno."""
    return "\n\n---\n\n".join(
        f"[Fuente: {d.metadata['fuente']}]\n{d.page_content}" for d in docs
    )


# ---------- Cadena LCEL ----------
def construir_cadena():
    vectorstore = ingestar()  # no reindexa si la base ya existe
    retriever = vectorstore.as_retriever(search_kwargs={"k": TOP_K})
    llm = ChatGoogleGenerativeAI(model=GEMINI_MODEL, temperature=0, max_retries=5)
    logger.info("LLM configurado: %s", GEMINI_MODEL)

    generacion = (
        RunnableLambda(lambda x: {"contexto": formatear_contexto(x["docs"]), "pregunta": x["pregunta"]})
        | PROMPT_RAG
        | llm
        | parser
    ).with_retry(
        retry_if_exception_type=(OutputParserException,),
        wait_exponential_jitter=True,
        stop_after_attempt=3,
    )

    return (
        RunnableParallel(docs=retriever, pregunta=RunnablePassthrough())
        | RunnablePassthrough.assign(resultado=generacion)
    )


_cadena = None


def obtener_cadena():
    """Construye la cadena la primera vez que se usa."""
    global _cadena
    if _cadena is None:
        _cadena = construir_cadena()
    return _cadena


# ---------- Función principal ----------
async def get_rag_response(query: str) -> RespuestaRAG:
    """Busca en ChromaDB, arma el prompt con el contexto y devuelve una respuesta validada."""
    if not query or not query.strip():
        raise ValueError("La consulta está vacía")

    logger.info("Consulta: %s", query)
    try:
        salida = await obtener_cadena().ainvoke(query)
    except Exception as error:
        logger.error("Falló la cadena RAG: %s: %s", type(error).__name__, error)
        raise

    fuentes = {d.metadata["fuente"] for d in salida["docs"]}
    logger.info("Fragmentos recuperados: %d de %s", len(salida["docs"]), sorted(fuentes))

    respuesta: RespuestaRAG = salida["resultado"]
    inventadas = [r for r in respuesta.referencias if r not in fuentes]
    if inventadas:
        logger.warning("Referencias que no estaban en el contexto (se descartan): %s", inventadas)
        respuesta.referencias = [r for r in respuesta.referencias if r in fuentes]

    logger.info("Respuesta validada: encontrado=%s, referencias=%s",
                respuesta.encontrado, respuesta.referencias)
    return respuesta


# ---------- Pruebas ----------
async def probar(query: str, intentos: int = 3, espera: int = 30):
    """Ejecuta una consulta; si Gemini está saturado (503), espera y reintenta."""
    for intento in range(1, intentos + 1):
        try:
            r = await get_rag_response(query)
            print(json.dumps(r.model_dump(), ensure_ascii=False, indent=2))
            return r
        except Exception as e:
            if "503" in str(e) and intento < intentos:
                logger.warning("Gemini saturado (503). Reintento %d de %d en %d segundos...", intento + 1, intentos, espera)
                await asyncio.sleep(espera)
            else:
                print(f"Error controlado ({type(e).__name__}): {e}")
                return None


async def main():
    print("\n=== Prueba 1: pregunta con respuesta en los documentos ===")
    await probar("¿Qué hace with_retry y cuántos intentos se usaron en la Pre-entrega 2?")

    print("\n=== Prueba 2: pregunta trampa ===")
    await probar("¿Cuánto cuesta la API de OpenAI por millón de tokens?")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
                        datefmt="%H:%M:%S")
    for ruidoso in ("httpx", "chromadb", "sentence_transformers", "google_genai"):
        logging.getLogger(ruidoso).setLevel(logging.WARNING)
    asyncio.run(main())