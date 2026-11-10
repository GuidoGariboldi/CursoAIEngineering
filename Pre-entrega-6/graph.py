"""Construcción del grafo jerárquico: supervisor + especialistas + síntesis."""
import logging

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agents.analyst_agent import crear_nodo_analista
from agents.research_agent import crear_nodo_investigador
from agents.supervisor import crear_nodo_sintesis, crear_nodo_supervisor, enrutar
from config import (DIAGRAMA_PATH, MODELO_ESPECIALISTAS, MODELO_SUPERVISOR,
                    MODELOS_SUPERVISOR_RESPALDO, configurar_logs, crear_llm)
from state import EstadoOrquestador

logger = logging.getLogger("orquestador")


def construir_grafo() -> CompiledStateGraph:
    modelos_supervisor = [MODELO_SUPERVISOR, *MODELOS_SUPERVISOR_RESPALDO]
    llm_especialistas = crear_llm(MODELO_ESPECIALISTAS, reintentos=3)
    logger.info("Supervisor/síntesis: %s | Especialistas: %s", modelos_supervisor, MODELO_ESPECIALISTAS)

    builder = StateGraph(EstadoOrquestador)
    builder.add_node("supervisor", crear_nodo_supervisor(modelos_supervisor))
    builder.add_node("investigador", crear_nodo_investigador(llm_especialistas))
    builder.add_node("analista", crear_nodo_analista(llm_especialistas))
    builder.add_node("sintesis", crear_nodo_sintesis(modelos_supervisor))

    builder.add_edge(START, "supervisor")
    builder.add_conditional_edges("supervisor", enrutar)  # -> investigador / analista / sintesis
    builder.add_edge("investigador", "supervisor")        # cada especialista reporta al supervisor
    builder.add_edge("analista", "supervisor")
    builder.add_edge("sintesis", END)
    return builder.compile()


def guardar_diagrama(grafo: CompiledStateGraph, path: str = DIAGRAMA_PATH) -> str:
    """Guarda el diagrama como PNG (si hay conexión) y devuelve el texto Mermaid."""
    try:
        with open(path, "wb") as f:
            f.write(grafo.get_graph().draw_mermaid_png())
        logger.info("Diagrama guardado en %s", path)
    except Exception as e:
        logger.warning("No se pudo generar el PNG (%s)", type(e).__name__)
    return grafo.get_graph().draw_mermaid()


if __name__ == "__main__":
    configurar_logs()
    print(guardar_diagrama(construir_grafo()))