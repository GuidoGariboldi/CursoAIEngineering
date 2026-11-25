"""Supervisor: decide quién trabaja y valida con una rúbrica. Síntesis: redacta la respuesta final."""
import asyncio
import logging
from typing import Any, Callable, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.config import crear_llm, obtener_config, texto_de
from app.schemas import DecisionSupervisor
from app.state import EstadoOrquestador, historial_previo, pregunta_actual, resumir_contribuciones

logger = logging.getLogger("orquestador")

PROMPT_SUPERVISOR = """Sos el Supervisor de un equipo de agentes de una tienda de tecnología.
Dada la pregunta del cliente, el historial de la conversación y las contribuciones de esta pregunta,
decidí quién interviene ahora o si ya se puede responder.

Especialistas:
- investigador: busca productos (precio, características, garantía) y reseñas en el catálogo. No calcula.
- analista: calcula promedios, analiza el sentimiento y hace cuentas sobre datos que ya obtuvo el
  investigador. No puede buscar información.
- documentalista: consulta las políticas de la tienda (garantías, devoluciones, envíos, medios de pago,
  uso y cuidado de los auriculares). Es el único que conoce esas políticas.

Rúbrica para FINALIZAR (todo lo que aplique a la pregunta debe cumplirse):
1. Si pide datos de productos, el investigador los obtuvo para TODOS los productos mencionados.
2. Si pide comparaciones, promedios u opiniones, el analista lo calculó con herramientas.
3. Si pregunta por políticas, el documentalista las consultó.
4. Ninguna contribución contiene ERROR.
Si la pregunta se responde con el historial (por ejemplo, un dato que ya se dio), FINALIZAR directamente.
Si el documentalista dijo que no encontró la información, no insistas: FINALIZAR (la respuesta dirá que no se sabe).
Si el cliente pide reservar o comprar, NO lo delegues: esa acción tiene un paso aparte con aprobación humana.
No repitas una tarea que ya está bien hecha. Las instrucciones a los especialistas deben ser autocontenidas:
nombrá los productos explícitamente aunque el cliente haya dicho "ese" o "el otro"."""

PROMPT_SINTESIS = """Sos el responsable de redactar la respuesta final para el cliente.
Usá SOLO la información de las contribuciones de los especialistas y del historial; no agregues datos.
Respondé en español, claro y breve. Si hay datos de políticas, mencioná de qué documento salen.
Si algo no se pudo averiguar, decilo. Si hubo una acción crítica (por ejemplo, una reserva),
informá si se ejecutó o no."""


def _llm_con_respaldo(modelos: list[str], esquema=None):
    principal = crear_llm(modelos[0])
    respaldos = [crear_llm(m) for m in modelos[1:]]
    if esquema is not None:
        return principal.with_structured_output(esquema).with_fallbacks(
            [r.with_structured_output(esquema) for r in respaldos])
    return principal.with_fallbacks(respaldos)


def crear_nodo_supervisor(modelos: list[str]) -> Callable:
    llm_decisor = _llm_con_respaldo(modelos, DecisionSupervisor)

    async def nodo_supervisor(state: EstadoOrquestador) -> dict[str, Any]:
        cfg = obtener_config()
        pasos = state.get("pasos_supervisor", 0)
        if pasos >= cfg.max_pasos_supervisor:
            logger.warning("Supervisor: máximo de %d pasos alcanzado -> se fuerza el cierre", pasos)
            decision = DecisionSupervisor(siguiente="FINALIZAR", motivo="Se alcanzó el límite de pasos")
        else:
            if pasos > 0:
                await asyncio.sleep(cfg.pausa_entre_nodos)
            mensajes = state["messages"]
            decision = await llm_decisor.ainvoke([
                SystemMessage(PROMPT_SUPERVISOR),
                HumanMessage(
                    f"HISTORIAL DE LA CONVERSACIÓN:\n{historial_previo(mensajes, cfg.max_mensajes_historial)}\n\n"
                    f"PREGUNTA ACTUAL DEL CLIENTE:\n{pregunta_actual(mensajes)}\n\n"
                    f"CONTRIBUCIONES EN ESTA PREGUNTA:\n{resumir_contribuciones(state.get('contribuciones') or [])}"),
            ])

        logger.info("SUPERVISOR (paso %d) -> %s | %s", pasos + 1, decision.siguiente, decision.motivo)
        return {
            "siguiente": decision.siguiente,
            "instruccion": decision.instruccion,
            "pasos_supervisor": pasos + 1,
            "tarea_completa": decision.siguiente == "FINALIZAR",
            "messages": [AIMessage(content=f"Decisión: {decision.siguiente}. Motivo: {decision.motivo.rstrip('.')}. "
                                           f"Instrucción: {decision.instruccion}", name="supervisor")],
        }

    return nodo_supervisor


def enrutar(state: EstadoOrquestador) -> Literal["investigador", "analista", "documentalista", "aprobacion"]:
    """Arista condicional: el nombre que elige el supervisor es el nombre del nodo."""
    return "aprobacion" if state["siguiente"] == "FINALIZAR" else state["siguiente"]


def crear_nodo_sintesis(modelos: list[str]) -> Callable:
    llm = _llm_con_respaldo(modelos)

    async def nodo_sintesis(state: EstadoOrquestador) -> dict[str, Any]:
        cfg = obtener_config()
        await asyncio.sleep(cfg.pausa_entre_nodos)
        mensajes = state["messages"]
        accion = state.get("accion_ejecutada") or "No se solicitó ninguna acción crítica."
        respuesta = await llm.ainvoke([
            SystemMessage(PROMPT_SINTESIS),
            HumanMessage(
                f"HISTORIAL DE LA CONVERSACIÓN:\n{historial_previo(mensajes, cfg.max_mensajes_historial)}\n\n"
                f"PREGUNTA ACTUAL DEL CLIENTE:\n{pregunta_actual(mensajes)}\n\n"
                f"CONTRIBUCIONES:\n{resumir_contribuciones(state.get('contribuciones') or [])}\n\n"
                f"ESTADO DE LA ACCIÓN SOLICITADA:\n{accion}"),
        ])
        texto = texto_de(respuesta)
        logger.info("SINTESIS: respuesta final generada (%d caracteres)", len(texto))
        return {"respuesta_final": texto, "messages": [AIMessage(content=texto, name="sintesis")]}

    return nodo_sintesis
