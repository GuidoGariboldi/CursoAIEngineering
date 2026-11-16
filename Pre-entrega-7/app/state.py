"""Esquema del estado compartido entre el supervisor, los especialistas y el nodo HITL."""
import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import MessagesState


class Contribucion(TypedDict):
    paso: int
    agente: str
    instruccion: str
    herramientas_usadas: list[str]
    resultado: str


class EstadoOrquestador(MessagesState):
    """Estado compartido. Registra qué agente aportó qué información."""
    siguiente: str                                               # a quién delega el supervisor
    instruccion: str                                             # tarea puntual para el especialista
    contribuciones: Annotated[list[Contribucion], operator.add]  # se acumulan, no se pisan
    pasos_supervisor: int                                        # contador para la condición de parada
    tarea_completa: bool
    requiere_aprobacion: bool                                    # la solicitud incluye una acción crítica
    aprobacion: dict[str, Any]                                   # decisión del humano
    accion_ejecutada: str                                        # resultado de la acción crítica
    respuesta_final: str


def resumir_contribuciones(contribuciones: list[Contribucion]) -> str:
    """Texto con las contribuciones, para pasarle al supervisor y a la síntesis."""
    if not contribuciones:
        return "(todavía no hay contribuciones)"
    return "\n\n".join(
        f"[Paso {c['paso']}] {c['agente'].upper()} "
        f"(herramientas: {', '.join(c['herramientas_usadas']) or 'ninguna'})\n"
        f"Instrucción: {c['instruccion']}\nResultado:\n{c['resultado']}"
        for c in contribuciones
    )
