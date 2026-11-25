"""Grafo de agentes: Supervisor + 3 especialistas + aprobación humana + síntesis."""
import logging

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.analyst_agent import crear_nodo_analista
from app.agents.knowledge_agent import crear_nodo_documentalista
from app.agents.research_agent import crear_nodo_investigador
from app.agents.supervisor import crear_nodo_sintesis, crear_nodo_supervisor, enrutar
from app.config import obtener_config
from app.hitl import nodo_aprobacion
from app.state import EstadoOrquestador

logger = logging.getLogger("orquestador")


def construir_grafo(checkpointer: BaseCheckpointSaver | None) -> CompiledStateGraph:
    cfg = obtener_config()
    logger.info("Supervisor/síntesis: %s | Especialistas: %s", cfg.modelos_supervisor, cfg.modelos_especialistas)

    builder = StateGraph(EstadoOrquestador)
    builder.add_node("supervisor", crear_nodo_supervisor(cfg.modelos_supervisor))
    builder.add_node("investigador", crear_nodo_investigador(cfg.modelos_especialistas))
    builder.add_node("analista", crear_nodo_analista(cfg.modelos_especialistas))
    builder.add_node("documentalista", crear_nodo_documentalista(cfg.modelos_especialistas))
    builder.add_node("aprobacion", nodo_aprobacion)
    builder.add_node("sintesis", crear_nodo_sintesis(cfg.modelos_supervisor))

    builder.add_edge(START, "supervisor")
    builder.add_conditional_edges("supervisor", enrutar)   # -> investigador / analista / documentalista / aprobacion
    for especialista in ("investigador", "analista", "documentalista"):
        builder.add_edge(especialista, "supervisor")         # todos reportan al supervisor
    builder.add_edge("aprobacion", "sintesis")
    builder.add_edge("sintesis", END)

    # Con el checkpointer de Redis, cada conversación (thread_id) se guarda paso a paso:
    # sobrevive a un reinicio y permite pausar con interrupt() y reanudar después.
    return builder.compile(checkpointer=checkpointer)
