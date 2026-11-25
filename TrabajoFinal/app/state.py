"""Estado compartido entre el supervisor, los especialistas, el nodo HITL y la síntesis."""
from typing import Any, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph import MessagesState

from app.config import texto_de


class Contribucion(TypedDict):
    paso: int
    agente: str
    instruccion: str
    herramientas_usadas: list[str]
    resultado: str
    fuentes: list[str]


class EstadoOrquestador(MessagesState):
    """messages guarda TODA la conversación (persiste en Redis). El resto se reinicia en cada pregunta."""
    siguiente: str
    instruccion: str
    contribuciones: list[Contribucion]
    pasos_supervisor: int
    tarea_completa: bool
    requiere_aprobacion: bool
    aprobacion: dict[str, Any]
    accion_ejecutada: str
    respuesta_final: str


def pregunta_actual(mensajes: list[BaseMessage]) -> str:
    """El último mensaje del usuario es la pregunta que se está resolviendo."""
    for m in reversed(mensajes):
        if isinstance(m, HumanMessage):
            return texto_de(m)
    return ""


def historial_previo(mensajes: list[BaseMessage], maximo: int) -> str:
    """Preguntas y respuestas finales de los turnos anteriores (sin la pregunta actual)."""
    turnos = [m for m in mensajes
              if isinstance(m, HumanMessage) or (isinstance(m, AIMessage) and m.name == "sintesis")]
    if turnos and isinstance(turnos[-1], HumanMessage):
        turnos = turnos[:-1]
    lineas = [f"{'Usuario' if isinstance(m, HumanMessage) else 'Asistente'}: {texto_de(m)}" for m in turnos[-maximo:]]
    return "\n".join(lineas) or "(es el primer mensaje de la conversación)"


def resumir_contribuciones(contribuciones: list[Contribucion]) -> str:
    if not contribuciones:
        return "(todavía no hay contribuciones)"
    return "\n\n".join(
        f"[Paso {c['paso']}] {c['agente'].upper()} "
        f"(herramientas: {', '.join(c['herramientas_usadas']) or 'ninguna'})\n"
        f"Instrucción: {c['instruccion']}\nResultado:\n{c['resultado']}"
        for c in contribuciones
    )
