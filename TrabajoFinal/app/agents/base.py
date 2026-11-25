"""Ejecución común de un especialista: modelos de respaldo, contexto acotado y registro de su contribución."""
import ast
import asyncio
import json
import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.config import obtener_config, texto_de
from app.state import Contribucion, EstadoOrquestador

logger = logging.getLogger("orquestador")


def _parsear(contenido: Any) -> Any:
    if not isinstance(contenido, str):
        return contenido
    for cargar in (json.loads, ast.literal_eval):
        try:
            return cargar(contenido)
        except Exception:
            pass
    return contenido


def _fuentes(mensajes: list) -> list[str]:
    """Archivos de la base de conocimiento que devolvió la herramienta de RAG."""
    fuentes: list[str] = []
    for m in mensajes:
        if isinstance(m, ToolMessage) and m.name == "buscar_conocimiento":
            datos = _parsear(m.content)
            if isinstance(datos, dict):
                for f in datos.get("fragmentos", []):
                    if f.get("fuente") and f["fuente"] not in fuentes:
                        fuentes.append(f["fuente"])
    return fuentes


async def ejecutar_especialista(nombre: str, agentes: list[tuple[str, Any]], entrada: str,
                                state: EstadoOrquestador) -> dict[str, Any]:
    """Corre un especialista probando sus modelos en orden y agrega su contribución al estado."""
    cfg = obtener_config()
    await asyncio.sleep(cfg.pausa_entre_nodos)
    logger.info("%s recibe: %s", nombre, state["instruccion"])

    resultado, herramientas, fuentes = None, [], []
    for modelo, agente in agentes:
        try:
            salida = await agente.ainvoke(
                {"messages": [HumanMessage(entrada)]},
                {"recursion_limit": cfg.recursion_limit_especialista, "run_name": f"{nombre} ({modelo})"},
            )
            resultado = texto_de(salida["messages"][-1])
            herramientas = [m.name for m in salida["messages"] if isinstance(m, ToolMessage)]
            fuentes = _fuentes(salida["messages"])
            break
        except Exception as e:
            logger.warning("%s con %s falló (%s); se prueba el siguiente modelo", nombre, modelo, type(e).__name__)

    if not resultado:
        resultado = f"ERROR: el {nombre} no pudo completar la tarea con ningún modelo."

    previas = state.get("contribuciones") or []
    contribucion: Contribucion = {
        "paso": len(previas) + 1,
        "agente": nombre,
        "instruccion": state["instruccion"],
        "herramientas_usadas": herramientas,
        "resultado": resultado,
        "fuentes": fuentes,
    }
    logger.info("%s terminó usando %s", nombre, herramientas)
    return {"messages": [AIMessage(content=resultado, name=nombre)],
            "contribuciones": previas + [contribucion]}
