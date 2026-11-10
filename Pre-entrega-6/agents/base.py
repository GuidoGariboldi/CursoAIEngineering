"""Lógica común para ejecutar un especialista y registrar su contribución."""
import asyncio
import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from config import PAUSA_ENTRE_NODOS, RECURSION_LIMIT_ESPECIALISTA, texto_de
from state import Contribucion, EstadoOrquestador

logger = logging.getLogger("orquestador")


async def ejecutar_especialista(nombre: str, agente: Any, entrada: str,
                                state: EstadoOrquestador) -> dict[str, Any]:
    """Corre un especialista con su instrucción y guarda su aporte en el estado compartido."""
    await asyncio.sleep(PAUSA_ENTRE_NODOS)
    logger.info("%s recibe: %s", nombre, state["instruccion"])
    try:
        salida = await agente.ainvoke({"messages": [HumanMessage(entrada)]}, {"recursion_limit": RECURSION_LIMIT_ESPECIALISTA})
        resultado = texto_de(salida["messages"][-1])
        herramientas = [m.name for m in salida["messages"] if isinstance(m, ToolMessage)]
    except Exception as e:
        logger.error("%s falló: %s", nombre, e)
        resultado = f"ERROR: el {nombre} no pudo completar la tarea ({type(e).__name__})."
        herramientas = []

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