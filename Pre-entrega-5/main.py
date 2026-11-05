"""Pruebas del agente y exportación de la traza ReAct a JSON."""
import ast
import asyncio
import json
import logging
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.errors import GraphRecursionError
from langgraph.graph.state import CompiledStateGraph

from agente import construir_grafo, texto_de
from base_datos import FALLAS_SIMULADAS
from config import (DB_CHECKPOINTS, GEMINI_MODEL, PAUSA_ENTRE_PREGUNTAS, RECURSION_LIMIT,
                    TRAZA_PATH, configurar_logs)

logger = logging.getLogger("agente")

PRUEBAS: list[tuple[str, str]] = [
    ("sesion-1", "¿Cuántos pedidos tuvo Martín Gómez y cuál fue el total?"),   # multi-paso
    ("sesion-1", "¿Y el último? ¿Qué compró y en qué estado está?"),            # memoria
    ("sesion-2", "¿Cuánto gastó en total Lucía Fernández?"),                    # reintento
    ("sesion-3", "¿Cuántos pedidos tiene Martín?"),                             # aclaración
    ("sesion-3", "El de Mendoza"),
    ("sesion-nueva", "¿Y el último? ¿Qué compró y en qué estado está?"),        # sin memoria
]


async def preguntar(grafo: CompiledStateGraph, pregunta: str, thread_id: str,
                    intentos: int = 3, espera: int = 30) -> str | None:
    """Envía una pregunta al agente dentro de una conversación (thread_id)."""
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": RECURSION_LIMIT}
    print(f"\n [{thread_id}] {pregunta}")

    for intento in range(1, intentos + 1):
        try:
            resultado = await grafo.ainvoke({"messages": [HumanMessage(pregunta)]}, config)
            respuesta = texto_de(resultado["messages"][-1])
            print(f" {respuesta}")
            return respuesta
        except GraphRecursionError:
            print(f" Se alcanzó el límite de {RECURSION_LIMIT} pasos sin respuesta final")
            return None
        except Exception as e:
            if "503" in str(e) and intento < intentos:
                logger.warning("Gemini saturado (503). Reintento %d de %d en %ds...",
                               intento + 1, intentos, espera)
                await asyncio.sleep(espera)
            else:
                print(f" Error controlado ({type(e).__name__}): {e}")
                return None
    return None


def parsear(contenido: str) -> Any:
    """Convierte la salida de una herramienta a dict si se puede."""
    for cargar in (json.loads, ast.literal_eval):
        try:
            return cargar(contenido)
        except Exception:
            pass
    return contenido


def mensaje_a_paso(m: BaseMessage) -> dict[str, Any]:
    if isinstance(m, HumanMessage):
        return {"tipo": "usuario", "contenido": texto_de(m)}
    if isinstance(m, ToolMessage):
        return {"tipo": "resultado_herramienta", "herramienta": m.name, "contenido": parsear(m.content)}
    if isinstance(m, AIMessage) and m.tool_calls:
        return {"tipo": "agente_decide_herramienta",
                "llamadas": [{"herramienta": t["name"], "argumentos": t["args"]} for t in m.tool_calls]}
    return {"tipo": "respuesta_final", "contenido": texto_de(m)}


async def obtener_traza(grafo: CompiledStateGraph, thread_id: str) -> dict[str, Any]:
    """Lee del checkpointer todo lo que pasó en una conversación."""
    estado = await grafo.aget_state({"configurable": {"thread_id": thread_id}})
    pasos = [mensaje_a_paso(m) for m in estado.values.get("messages", [])]
    llamadas = sum(len(p["llamadas"]) for p in pasos if p["tipo"] == "agente_decide_herramienta")
    return {"thread_id": thread_id,
            "llamadas_llm": estado.values.get("llamadas_llm", 0),
            "llamadas_herramientas": llamadas,
            "pasos": pasos}


def imprimir_traza(traza: dict[str, Any]) -> None:
    print(f"\n===== {traza['thread_id']} | LLM: {traza['llamadas_llm']} | "
          f"herramientas: {traza['llamadas_herramientas']} =====")
    for p in traza["pasos"]:
        if p["tipo"] == "usuario":
            print(f'Usuario: "{p["contenido"]}"')
        elif p["tipo"] == "agente_decide_herramienta":
            for ll in p["llamadas"]:
                args = ", ".join(f"{k}={v!r}" for k, v in ll["argumentos"].items())
                print(f"  → El agente decide usar: {ll['herramienta']}({args})")
        elif p["tipo"] == "resultado_herramienta":
            print(f"  → La herramienta devuelve: {json.dumps(p['contenido'], ensure_ascii=False)[:150]}")
        else:
            print(f'Respuesta: "{p["contenido"]}"')


async def main() -> None:
    threads = list(dict.fromkeys(t for t, _ in PRUEBAS))

    async with AsyncSqliteSaver.from_conn_string(DB_CHECKPOINTS) as checkpointer:
        grafo = construir_grafo(checkpointer)

        # Las pruebas arrancan desde cero
        for thread in threads:
            await checkpointer.adelete_thread(thread)
        FALLAS_SIMULADAS.clear()
        FALLAS_SIMULADAS.add(101)

        for i, (thread_id, pregunta) in enumerate(PRUEBAS):
            if i > 0:
                await asyncio.sleep(PAUSA_ENTRE_PREGUNTAS)  # respeta el límite por minuto del plan gratuito
            await preguntar(grafo, pregunta, thread_id)

        trazas = [await obtener_traza(grafo, t) for t in threads]

    for traza in trazas:
        imprimir_traza(traza)

    with open(TRAZA_PATH, "w", encoding="utf-8") as f:
        json.dump({"modelo": GEMINI_MODEL, "recursion_limit": RECURSION_LIMIT, "conversaciones": trazas},
                  f, ensure_ascii=False, indent=2)
    print(f"\n Traza guardada en {TRAZA_PATH}")


if __name__ == "__main__":
    configurar_logs()
    asyncio.run(main())