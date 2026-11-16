"""Cola de trabajos en segundo plano. El estado de cada trabajo se guarda en Redis."""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from opentelemetry.trace import Tracer
from redis.asyncio import Redis

from app.config import JOB_TTL_SEGUNDOS, RECURSION_LIMIT_GRAFO

logger = logging.getLogger("orquestador")

PENDING, RUNNING, WAITING_APPROVAL, DONE, FAILED = "PENDING", "RUNNING", "WAITING_APPROVAL", "DONE", "FAILED"


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


class GestorTrabajos:
    def __init__(self, grafo: CompiledStateGraph, redis: Redis, tracer: Tracer) -> None:
        self.grafo = grafo
        self.redis = redis
        self.tracer = tracer
        self.cola: asyncio.Queue[tuple[str, str, dict[str, Any]]] = asyncio.Queue()
        self.tareas: list[asyncio.Task] = []

    # ---------- Estado de los trabajos en Redis ----------
    async def guardar(self, job_id: str, **campos: Any) -> None:
        datos = {k: v if isinstance(v, str) else json.dumps(v, ensure_ascii=False) for k, v in campos.items()}
        datos["actualizado"] = _ahora()
        clave = f"job:{job_id}"
        await self.redis.hset(clave, mapping=datos)
        await self.redis.expire(clave, JOB_TTL_SEGUNDOS)

    async def obtener(self, job_id: str) -> dict[str, Any] | None:
        datos = await self.redis.hgetall(f"job:{job_id}")
        if not datos:
            return None
        for campo in ("resultado", "aprobacion_pendiente"):
            if campo in datos:
                datos[campo] = json.loads(datos[campo])
        return datos

    # ---------- Cola ----------
    async def encolar(self, job_id: str, tipo: str, datos: dict[str, Any]) -> None:
        await self.cola.put((job_id, tipo, datos))

    async def iniciar(self, cantidad: int) -> None:
        self.tareas = [asyncio.create_task(self._bucle(i)) for i in range(cantidad)]
        logger.info("%d worker(s) iniciados", cantidad)

    async def detener(self) -> None:
        for tarea in self.tareas:
            tarea.cancel()
        await asyncio.gather(*self.tareas, return_exceptions=True)

    async def _bucle(self, numero: int) -> None:
        while True:
            job_id, tipo, datos = await self.cola.get()
            try:
                await self._procesar(job_id, tipo, datos, numero)
            finally:
                self.cola.task_done()

    # ---------- Ejecución ----------
    async def _procesar(self, job_id: str, tipo: str, datos: dict[str, Any], numero: int) -> None:
        logger.info("Worker %d toma el trabajo %s (%s)", numero, job_id, tipo)
        await self.guardar(job_id, estado=RUNNING)
        config = {"configurable": {"thread_id": job_id}, "recursion_limit": RECURSION_LIMIT_GRAFO,
                  "metadata": {"job_id": job_id}, "run_name": "orquestador"}

        if tipo == "nuevo":
            entrada: Any = {"messages": [HumanMessage(datos["consulta"])],
                            "contribuciones": [], "pasos_supervisor": 0}
        else:
            entrada = Command(resume=datos)   # respuesta del humano al interrupt()

        nombre_span = f"trabajo {job_id}" + (" (reanudación)" if tipo != "nuevo" else "")
        with self.tracer.start_as_current_span(nombre_span, attributes={
            "openinference.span.kind": "CHAIN", "job.id": job_id, "job.tipo": tipo,
            "input.value": json.dumps(datos, ensure_ascii=False),
        }):
            try:
                if "forzar_error" in datos.get("consulta", ""):
                    raise RuntimeError("Falla simulada para probar el estado FAILED")

                resultado = await self.grafo.ainvoke(entrada, config)
                interrupciones = resultado.get("__interrupt__") or []

                if interrupciones:
                    await self.guardar(job_id, estado=WAITING_APPROVAL,
                                       aprobacion_pendiente=[i.value for i in interrupciones])
                    logger.info("Trabajo %s pausado: espera aprobación humana", job_id)
                else:
                    await self.guardar(job_id, estado=DONE, resultado=self._resumen(resultado))
                    logger.info("Trabajo %s terminado", job_id)

            except Exception as e:
                # Si el agente falla en segundo plano, el estado pasa a FAILED (el cliente no queda esperando)
                logger.exception("Trabajo %s falló", job_id)
                await self.guardar(job_id, estado=FAILED, error=f"{type(e).__name__}: {e}")

    @staticmethod
    def _resumen(resultado: dict[str, Any]) -> dict[str, Any]:
        return {
            "respuesta_final": resultado.get("respuesta_final", ""),
            "flujo": [m.name for m in resultado.get("messages", []) if isinstance(m, AIMessage)],
            "pasos_supervisor": resultado.get("pasos_supervisor", 0),
            "requiere_aprobacion": resultado.get("requiere_aprobacion", False),
            "accion_ejecutada": resultado.get("accion_ejecutada", ""),
            "contribuciones": [{"paso": c["paso"], "agente": c["agente"],
                                "herramientas_usadas": c["herramientas_usadas"]}
                               for c in resultado.get("contribuciones", [])],
        }
