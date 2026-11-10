"""Demo del flujo de delegación y exportación de la traza."""
import asyncio
import json
import sys

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.errors import GraphRecursionError

from config import (MODELO_ESPECIALISTAS, MODELO_SUPERVISOR, MODELOS_SUPERVISOR_RESPALDO,
                    RECURSION_LIMIT_GRAFO, TRAZA_PATH, configurar_logs, texto_de)
from graph import construir_grafo

CONSULTA_DEMO = ("Estoy por comprar auriculares. Compará los Pulse X1 y los Nova Pro: qué opinan los "
                 "clientes, el puntaje promedio de cada uno y cuál conviene más por relación precio/calidad.")


async def main(consulta: str) -> None:
    grafo = construir_grafo()
    print(f"USUARIO: {consulta}\n")
    try:
        resultado = await grafo.ainvoke(
            {"messages": [HumanMessage(consulta)], "contribuciones": [], "pasos_supervisor": 0},
            {"recursion_limit": RECURSION_LIMIT_GRAFO},
        )
    except GraphRecursionError:
        print(f"Se alcanzó el límite de {RECURSION_LIMIT_GRAFO} pasos del grafo")
        return
    except Exception as e:
        print(f"Error controlado ({type(e).__name__}): {e}")
        return

    print("\n" + "=" * 70 + "\nRESPUESTA FINAL\n" + "=" * 70)
    print(resultado["respuesta_final"])

    flujo = [m.name for m in resultado["messages"] if isinstance(m, AIMessage)]
    print("\nFLUJO:", " -> ".join(flujo), "-> END")

    traza = {
        "consulta": consulta,
        "modelos": {"supervisor_y_sintesis": [MODELO_SUPERVISOR, *MODELOS_SUPERVISOR_RESPALDO],
                    "especialistas": MODELO_ESPECIALISTAS},
        "flujo": flujo,
        "pasos_supervisor": resultado["pasos_supervisor"],
        "tarea_completa": resultado["tarea_completa"],
        "decisiones_supervisor": [texto_de(m) for m in resultado["messages"]
                                  if isinstance(m, AIMessage) and m.name == "supervisor"],
        "contribuciones": resultado["contribuciones"],
        "respuesta_final": resultado["respuesta_final"],
    }
    with open(TRAZA_PATH, "w", encoding="utf-8") as f:
        json.dump(traza, f, ensure_ascii=False, indent=2)
    print(f"\nTraza guardada en {TRAZA_PATH}")


if __name__ == "__main__":
    configurar_logs()
    asyncio.run(main(" ".join(sys.argv[1:]) or CONSULTA_DEMO))