"""Agente Documentalista: responde sobre políticas de la tienda usando el RAG."""
import logging
from typing import Any, Callable

from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from app.agents.base import ejecutar_especialista
from app.config import crear_llm
from app.rag.retriever import base_conocimiento
from app.schemas import BuscarConocimientoIn
from app.state import EstadoOrquestador

logger = logging.getLogger("orquestador")

PROMPT_DOCUMENTALISTA = """Sos el agente Documentalista de una tienda de tecnología.
Respondés preguntas sobre las políticas de la tienda (garantías, devoluciones, envíos, medios de pago
y uso de los productos) usando SOLO lo que devuelve la herramienta buscar_conocimiento.
Reglas:
- Buscá siempre antes de responder. Si la pregunta tiene varios temas, hacé una búsqueda por tema.
- Respondé citando la fuente de cada dato, por ejemplo: (fuente: garantia.md).
- Si la información no aparece en los fragmentos, decí exactamente: "No encontré esa información
  en las políticas de la tienda." No uses conocimiento propio ni inventes plazos, montos ni condiciones."""


@tool(args_schema=BuscarConocimientoIn)
async def buscar_conocimiento(consulta: str) -> dict[str, Any]:
    """Busca en la base de conocimiento de la tienda (políticas de garantía, devoluciones, envíos,
    medios de pago y guías de uso de los auriculares). Devuelve los fragmentos más relevantes con
    su archivo de origen y su sección."""
    return (await base_conocimiento.buscar(consulta)).model_dump()


HERRAMIENTAS_DOCUMENTALISTA = [buscar_conocimiento]


def crear_nodo_documentalista(modelos: list[str]) -> Callable:
    agentes = [(m, create_react_agent(crear_llm(m), HERRAMIENTAS_DOCUMENTALISTA,
                                      prompt=PROMPT_DOCUMENTALISTA, name="documentalista")) for m in modelos]

    async def nodo_documentalista(state: EstadoOrquestador) -> dict[str, Any]:
        return await ejecutar_especialista("documentalista", agentes, state["instruccion"], state)

    return nodo_documentalista
