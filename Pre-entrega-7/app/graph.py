"""Orquestador multi-agente de la Pre-entrega 6 + nodo HITL + checkpointer de Redis."""
import logging

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.analyst_agent import crear_nodo_analista
from app.agents.research_agent import crear_nodo_investigador
from app.agents.supervisor import crear_nodo_sintesis, crear_nodo_supervisor, enrutar
from app.config import MODELOS_ESPECIALISTAS, MODELOS_SUPERVISOR
from app.hitl import nodo_aprobacion
from app.state import EstadoOrquestador

logger = logging.getLogger("orquestador")


def construir_grafo(checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    logger.info("Supervisor/síntesis: %s | Especialistas: %s", MODELOS_SUPERVISOR, MODELOS_ESPECIALISTAS)

    builder = StateGraph(EstadoOrquestador)
    builder.add_node("supervisor", crear_nodo_supervisor(MODELOS_SUPERVISOR))
    builder.add_node("investigador", crear_nodo_investigador(MODELOS_ESPECIALISTAS))
    builder.add_node("analista", crear_nodo_analista(MODELOS_ESPECIALISTAS))
    builder.add_node("aprobacion", nodo_aprobacion)      # Human-in-the-loop
    builder.add_node("sintesis", crear_nodo_sintesis(MODELOS_SUPERVISOR))

    builder.add_edge(START, "supervisor")
    builder.add_conditional_edges("supervisor", enrutar)  # -> investigador / analista / aprobacion
    builder.add_edge("investigador", "supervisor")
    builder.add_edge("analista", "supervisor")
    builder.add_edge("aprobacion", "sintesis")
    builder.add_edge("sintesis", END)

    # Con checkpointer, el estado de cada trabajo (thread_id = job_id) queda guardado en Redis,
    # y eso es lo que permite pausar con interrupt() y reanudar más tarde.
    return builder.compile(checkpointer=checkpointer)
