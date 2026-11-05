"""Estado, modelo y grafo del agente (StateGraph con ciclo agente <-> herramientas)."""
import logging
import operator
from typing import Annotated, Any

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, trim_messages
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from config import GEMINI_MODEL, MAX_MENSAJES
from herramientas import HERRAMIENTAS

logger = logging.getLogger("agente")

SYSTEM_PROMPT = """Sos el asistente de atención al cliente de una tienda de tecnología.
Respondés consultas sobre clientes y pedidos usando SOLO las herramientas disponibles.

Reglas:
- Nunca inventes datos: si no los tenés, usá una herramienta.
- Si el usuario nombra a un cliente, primero buscá su cliente_id con buscar_cliente.
- Si una herramienta devuelve un error temporal, volvé a intentarlo una vez.
- Si hay varios clientes que coinciden, no elijas vos: preguntale al usuario cuál es.
- Los montos son en pesos argentinos; escribilos con separador de miles, por ejemplo $14.500.
- Respondé en español, de forma breve y clara."""


class EstadoAgente(MessagesState):
    """Estado del grafo: la lista de mensajes (heredada) más un contador de pasos del modelo."""
    llamadas_llm: Annotated[int, operator.add]


def texto_de(mensaje: BaseMessage) -> str:
    """Extrae el texto de un mensaje (Gemini a veces devuelve el contenido en bloques)."""
    contenido = mensaje.content
    if isinstance(contenido, str):
        return contenido
    return "".join(b.get("text", "") for b in contenido if isinstance(b, dict) and b.get("type") == "text")


def construir_grafo(checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    """Arma el grafo ReAct y lo compila con persistencia."""
    llm = ChatGoogleGenerativeAI(model=GEMINI_MODEL, temperature=0, max_retries=5)
    llm_con_herramientas = llm.bind_tools(HERRAMIENTAS)
    logger.info("LLM %s vinculado a %d herramientas: %s",
                GEMINI_MODEL, len(HERRAMIENTAS), [h.name for h in HERRAMIENTAS])

    async def nodo_agente(state: EstadoAgente) -> dict[str, Any]:
        """Llama al LLM; este decide si responder o pedir una herramienta."""
        historial = trim_messages(
            state["messages"],
            strategy="last",
            token_counter=len,        # cuenta mensajes
            max_tokens=MAX_MENSAJES,
            start_on="human",         # el recorte siempre arranca en un mensaje del usuario
        )
        respuesta: AIMessage = await llm_con_herramientas.ainvoke(
            [SystemMessage(SYSTEM_PROMPT), *historial])

        if respuesta.tool_calls:
            for llamada in respuesta.tool_calls:
                logger.info("🤖 El agente decide usar: %s(%s)", llamada["name"], llamada["args"])
        else:
            logger.info("🤖 El agente responde sin herramientas")
        return {"messages": [respuesta], "llamadas_llm": 1}

    builder = StateGraph(EstadoAgente)
    builder.add_node("agente", nodo_agente)
    builder.add_node("tools", ToolNode(HERRAMIENTAS, handle_tool_errors=True))
    builder.add_edge(START, "agente")
    builder.add_conditional_edges("agente", tools_condition)  # herramienta -> tools, si no -> END
    builder.add_edge("tools", "agente")                       # el resultado vuelve al agente

    return builder.compile(checkpointer=checkpointer)