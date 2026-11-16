"""Prueba de carga: envía 5 peticiones concurrentes a la API y mide la latencia de punta a punta."""
import asyncio
import statistics
import sys
import time

import httpx

API = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
ESTADOS_FINALES = {"DONE", "FAILED", "WAITING_APPROVAL"}

CONSULTAS = [
    "Compará los Pulse X1 y los Nova Pro: puntaje promedio, opinión de los clientes y precio/calidad.",
    "Compará los Basic 200 y los Pulse X1: puntaje promedio, opinión de los clientes y cuál conviene.",
    "Compará los Nova Pro y los Basic 200: puntaje promedio y relación precio/calidad.",
    "¿Qué opinan los clientes de los Basic 200? Quiero el puntaje promedio y el análisis de sentimiento.",
    "Compará los tres modelos de auriculares (Pulse X1, Nova Pro y Basic 200) por precio/calidad.",
]


async def esperar(cliente: httpx.AsyncClient, job_id: str, maximo: int = 1800) -> dict:
    for _ in range(maximo // 3):
        try:
            trabajo = (await cliente.get(f"{API}/tasks/{job_id}")).json()
        except httpx.TransportError:
            await asyncio.sleep(1)
            continue
        if trabajo["estado"] in ESTADOS_FINALES:
            return trabajo
        await asyncio.sleep(3)
    raise TimeoutError(job_id)


async def enviar(cliente: httpx.AsyncClient, consulta: str) -> dict:
    inicio = time.perf_counter()
    r = await cliente.post(f"{API}/tasks", json={"consulta": consulta})
    post_ms = (time.perf_counter() - inicio) * 1000
    trabajo = await esperar(cliente, r.json()["job_id"])
    return {"job_id": trabajo["id"], "estado": trabajo["estado"], "post_ms": post_ms,
            "total_s": time.perf_counter() - inicio}


async def main() -> None:
    async with httpx.AsyncClient(timeout=30) as cliente:
        resultados = await asyncio.gather(*(enviar(cliente, c) for c in CONSULTAS))

    for x in resultados:
        print(f"{x['job_id']}  {x['estado']:<10} POST {x['post_ms']:6.0f} ms   total {x['total_s']:6.1f} s")
    tiempos = sorted(x["total_s"] for x in resultados)
    print(f"\np50 = {statistics.median(tiempos):.1f} s | "
          f"p95 = {statistics.quantiles(tiempos, n=20, method='inclusive')[18]:.1f} s")


if __name__ == "__main__":
    asyncio.run(main())
