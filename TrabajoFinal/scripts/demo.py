"""Ejecuta las 5 pruebas del sistema contra la API. Uso: python scripts/demo.py [url]"""
import asyncio
import sys

import httpx

API = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
FINALES = {"DONE", "FAILED", "WAITING_APPROVAL"}


async def esperar(cliente: httpx.AsyncClient, job_id: str) -> dict:
    while True:
        try:
            trabajo = (await cliente.get(f"{API}/tasks/{job_id}")).json()
            if trabajo["estado"] in FINALES:
                return trabajo
        except httpx.TransportError:
            pass
        await asyncio.sleep(3)


async def prueba(cliente: httpx.AsyncClient, titulo: str, consulta: str, thread_id: str | None = None) -> dict:
    print(f"\n=== {titulo} ===\nConsulta: {consulta}")
    r = await cliente.post(f"{API}/tasks", json={"consulta": consulta, "thread_id": thread_id})
    trabajo = await esperar(cliente, r.json()["job_id"])
    resultado = trabajo.get("resultado") or {}
    print(f"Estado: {trabajo['estado']} | Flujo: {' -> '.join(resultado.get('flujo', []))}")
    print("Respuesta:", resultado.get("respuesta_final") or trabajo.get("error") or trabajo.get("aprobacion_pendiente"))
    return trabajo


async def main() -> None:
    async with httpx.AsyncClient(timeout=30) as c:
        await prueba(c, "1. RAG", "¿Cuántos días tengo para devolver un producto y quién paga el envío de la devolución?")
        await prueba(c, "2. Multi-agente", "Compará los Pulse X1 y los Nova Pro: puntaje promedio de los clientes, "
                     "cuál conviene más por precio/calidad y cuánta garantía tiene cada uno.", "demo")
        await prueba(c, "3. Memoria", "¿Y si no me gustan, los puedo devolver aunque los haya abierto?", "demo")
        t4 = await prueba(c, "4. HITL", "Perfecto, reservame el que convenía más.", "demo")
        if t4["estado"] == "WAITING_APPROVAL":
            await c.post(f"{API}/tasks/{t4['id']}/approve", json={"aprobado": True, "operador": "demo"})
            final = await esperar(c, t4["id"])
            print("Después de aprobar:", final["estado"], "|", (final.get("resultado") or {}).get("accion_ejecutada"))
        await prueba(c, "5. Anti-alucinación", "¿Hacen envíos a Uruguay? ¿Cuánto cuestan?")


if __name__ == "__main__":
    asyncio.run(main())
