"""Lógica común para ejecutar un especialista, con modelos de respaldo."""
import asyncio
import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.config import PAUSA_ENTRE_NODOS, RECURSION_LIMIT_ESPECIALISTA, texto_de
from app.state import Contribucion, EstadoOrquestador

logger = logging.getLogger("orquestador")


async def ejecutar_especialista(nombre: str, agentes: list[tuple[str, Any]], entrada: str,
                                state: EstadoOrquestador) -> dict[str, Any]:
    """Corre un especialista probando sus modelos en orden y registra su contribución."""
    await asyncio.sleep(PAUSA_ENTRE_NODOS)
    logger.info("%s recibe: %s", nombre, state["instruccion"])

    resultado, herramientas = None, []
    for modelo, agente in agentes:
        try:
            salida = await agente.ainvoke(
                {"messages": [HumanMessage(entrada)]},
                {"recursion_limit": RECURSION_LIMIT_ESPECIALISTA, "run_name": f"{nombre} ({modelo})"},
            )
            resultado = texto_de(salida["messages"][-1])
            herramientas = [m.name for m in salida["messages"] if isinstance(m, ToolMessage)]
            break
        except Exception as e:
            logger.warning("%s con %s falló (%s); se prueba el siguiente modelo",
                           nombre, modelo, type(e).__name__)

    if resultado is None:
        resultado = f"ERROR: el {nombre} no pudo completar la tarea con ningún modelo."

    logger.info("%s terminó usando %s", nombre, herramientas)
    contribucion: Contribucion = {
        "paso": len(state.get("contribuciones", [])) + 1,
        "agente": nombre,
        "instruccion": state["instruccion"],
        "herramientas_usadas": herramientas,
        "resultado": resultado,
    }
    return {"messages": [AIMessage(content=resultado, name=nombre)],
            "contribuciones": [contribucion]}
