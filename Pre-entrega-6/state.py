"""Esquema del estado compartido entre el supervisor y los especialistas."""
import operator
from typing import Annotated, TypedDict

from langgraph.graph import MessagesState


class Contribucion(TypedDict):
    paso: int
    agente: str
    instruccion: str
    herramientas_usadas: list[str]
    resultado: str


class EstadoOrquestador(MessagesState):
    """Estado compartido. Registra qué agente aportó qué información."""
    siguiente: str                                               
    instruccion: str                                             
    contribuciones: Annotated[list[Contribucion], operator.add]  
    pasos_supervisor: int                                        
    tarea_completa: bool                                         
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