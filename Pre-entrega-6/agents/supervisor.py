"""Supervisor (router con rúbrica de validación) y nodo de síntesis final."""
import asyncio
import logging
from typing import Any, Callable, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from config import MAX_PASOS_SUPERVISOR, PAUSA_ENTRE_NODOS, crear_llm, texto_de
from state import EstadoOrquestador, resumir_contribuciones

logger = logging.getLogger("orquestador")


class DecisionSupervisor(BaseModel):
    siguiente: Literal["investigador", "analista", "FINALIZAR"] = Field(
        description="Quién interviene ahora, o FINALIZAR si la tarea está completa.")
    instruccion: str = Field(
        description="Tarea concreta y autocontenida para el especialista. Vacía si es FINALIZAR.")
    motivo: str = Field(description="Por qué se toma esta decisión, en una oración.")


PROMPT_SUPERVISOR = """Sos el Supervisor de un equipo de agentes de una tienda de tecnología.
Dada la solicitud del usuario y las contribuciones de los especialistas, decidí quién debe
intervenir ahora o si es momento de finalizar.

Especialistas disponibles:
- investigador: busca productos y reseñas en la base de datos. No hace cálculos.
- analista: calcula promedios, analiza el sentimiento y hace cuentas sobre datos ya obtenidos.
  No puede buscar información: necesita que el investigador haya trabajado antes.

Rúbrica de validación (TODOS los puntos deben cumplirse para FINALIZAR):
1. El investigador obtuvo precio y reseñas de TODOS los productos que menciona el usuario.
2. El analista calculó con herramientas todo lo que pide el usuario (promedios, sentimiento,
   comparación de precio/calidad) para todos esos productos.
3. Ninguna contribución contiene ERROR ni dice que faltan datos.

Si un punto no se cumple, delegá en el especialista que corresponda con una instrucción
específica de corrección. No repitas una tarea que ya está bien hecha."""

PROMPT_SINTESIS = """Sos el responsable de redactar la respuesta final para el cliente.
Usá SOLO la información de las contribuciones de los especialistas; no agregues datos nuevos.
Respondé en español, de forma clara y breve: comparación de los productos, opinión de los
clientes, puntajes y una recomendación final justificada con los números."""


def crear_nodo_supervisor(modelos: list[str]) -> Callable:
    """Si el primer modelo falla, se usan los siguientes como respaldo."""
    llm_decisor = crear_llm(modelos[0]).with_structured_output(DecisionSupervisor).with_fallbacks(
        [crear_llm(m).with_structured_output(DecisionSupervisor) for m in modelos[1:]])

    async def nodo_supervisor(state: EstadoOrquestador) -> dict[str, Any]:
        pasos = state.get("pasos_supervisor", 0)
        solicitud = texto_de(state["messages"][0])

        if pasos >= MAX_PASOS_SUPERVISOR:
            logger.warning("Supervisor: se alcanzó el máximo de %d pasos -> se fuerza el cierre", pasos)
            decision = DecisionSupervisor(siguiente="FINALIZAR", instruccion="",
                                          motivo="Se alcanzó el límite de pasos del supervisor")
        else:
            if pasos > 0:
                await asyncio.sleep(PAUSA_ENTRE_NODOS)
            # El supervisor ve la solicitud y el resumen de contribuciones, no todo el historial
            decision = await llm_decisor.ainvoke([
                SystemMessage(PROMPT_SUPERVISOR),
                HumanMessage(f"SOLICITUD DEL USUARIO:\n{solicitud}\n\nCONTRIBUCIONES HASTA AHORA:\n"
                             f"{resumir_contribuciones(state.get('contribuciones', []))}"),
            ])

        logger.info("SUPERVISOR (paso %d) -> %s | %s", pasos + 1, decision.siguiente, decision.motivo)
        return {
            "siguiente": decision.siguiente,
            "instruccion": decision.instruccion,
            "pasos_supervisor": pasos + 1,
            "tarea_completa": decision.siguiente == "FINALIZAR",
            "messages": [AIMessage(content=f"Decisión: {decision.siguiente}. "
                                           f"Motivo: {decision.motivo.rstrip('.')}. "
                                           f"Instrucción: {decision.instruccion}", name="supervisor")],
        }

    return nodo_supervisor


def enrutar(state: EstadoOrquestador) -> Literal["investigador", "analista", "sintesis"]:
    """Arista condicional: traduce la decisión del supervisor al nombre del nodo."""
    return "sintesis" if state["siguiente"] == "FINALIZAR" else state["siguiente"]


def crear_nodo_sintesis(modelos: list[str]) -> Callable:
    llm = crear_llm(modelos[0]).with_fallbacks([crear_llm(m) for m in modelos[1:]])

    async def nodo_sintesis(state: EstadoOrquestador) -> dict[str, Any]:
        await asyncio.sleep(PAUSA_ENTRE_NODOS)
        solicitud = texto_de(state["messages"][0])
        respuesta = await llm.ainvoke([
            SystemMessage(PROMPT_SINTESIS),
            HumanMessage(f"SOLICITUD DEL USUARIO:\n{solicitud}\n\n"
                         f"CONTRIBUCIONES:\n{resumir_contribuciones(state.get('contribuciones', []))}"),
        ])
        texto = texto_de(respuesta)
        logger.info("SINTESIS: respuesta final generada (%d caracteres)", len(texto))
        return {"respuesta_final": texto, "messages": [AIMessage(content=texto, name="sintesis")]}

    return nodo_sintesis