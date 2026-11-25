"""Cola de trabajos en segundo plano. El estado de cada trabajo se guarda en Redis y se valida con Pydantic."""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from opentelemetry.trace import Status, StatusCode, Tracer
from redis.asyncio import Redis

from app.config import obtener_config
from app.schemas import AprobacionIn, ContribucionResumen, EstadoTrabajo, ResultadoTrabajo, TrabajoOut

logger = logging.getLogger("orquestador")

# Campos que se reinician en cada pregunta nueva (los mensajes, en cambio, se acumulan: son la memoria)
ESTADO_PREGUNTA_NUEVA: dict[str, Any] = {
    "siguiente": "", "instruccion": "", "contribuciones": [], "pasos_supervisor": 0,
    "tarea_completa": False, "requiere_aprobacion": False, "aprobacion": {},
    "accion_ejecutada": "", "respuesta_final": "",
}


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


class GestorTrabajos:
    def __init__(self, grafo: CompiledStateGraph, redis: Redis, tracer: Tracer) -> None:
        self.grafo = grafo
        self.redis = redis
        self.tracer = tracer
        self.cola: asyncio.Queue[tuple[str, str, dict[str, Any]]] = asyncio.Queue()
        self.tareas: list[asyncio.Task] = []
        self._bloqueos: dict[str, asyncio.Lock] = {}   # una pregunta a la vez por conversación

    # ---------- Estado de los trabajos en Redis ----------
    async def guardar(self, job_id: str, **campos: Any) -> None:
        datos = {k: v.value if isinstance(v, EstadoTrabajo) else v if isinstance(v, str)
                 else json.dumps(v, ensure_ascii=False) for k, v in campos.items()}
        datos["actualizado"] = ahora()
        clave = f"job:{job_id}"
        await self.redis.hset(clave, mapping=datos)
        await self.redis.expire(clave, obtener_config().job_ttl_segundos)

    async def obtener(self, job_id: str) -> TrabajoOut | None:
        datos: dict[str, Any] = await self.redis.hgetall(f"job:{job_id}")
        if not datos:
            return None
        for campo in ("resultado", "aprobacion_pendiente"):
            if campo in datos:
                datos[campo] = json.loads(datos[campo])
        return TrabajoOut.model_validate(datos)

    async def crear(self, job_id: str, thread_id: str, consulta: str) -> None:
        await self.guardar(job_id, id=job_id, thread_id=thread_id, estado=EstadoTrabajo.PENDING,
                           consulta=consulta, creado=ahora())
        await self.cola.put((job_id, "nuevo", {"consulta": consulta}))

    async def reanudar(self, job_id: str, aprobacion: AprobacionIn) -> None:
        await self.guardar(job_id, estado=EstadoTrabajo.PENDING)
        await self.cola.put((job_id, "reanudar", aprobacion.model_dump()))

    async def tiene_aprobacion_pendiente(self, thread_id: str) -> bool:
        estado = await self.grafo.aget_state({"configurable": {"thread_id": thread_id}})
        return bool(estado.next)

    # ---------- Workers ----------
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

    async def _procesar(self, job_id: str, tipo: str, datos: dict[str, Any], numero: int) -> None:
        trabajo = await self.obtener(job_id)
        if trabajo is None:
            return
        thread_id = trabajo.thread_id
        async with self._bloqueos.setdefault(thread_id, asyncio.Lock()):
            logger.info("Worker %d toma el trabajo %s (%s, conversación %s)", numero, job_id, tipo, thread_id)
            await self.guardar(job_id, estado=EstadoTrabajo.RUNNING)
            cfg = obtener_config()
            config = {"configurable": {"thread_id": thread_id, "job_id": job_id},
                      "recursion_limit": cfg.recursion_limit_grafo,
                      "metadata": {"job_id": job_id, "thread_id": thread_id}, "run_name": "orquestador"}
            entrada: Any = ({"messages": [HumanMessage(datos["consulta"])], **ESTADO_PREGUNTA_NUEVA}
                            if tipo == "nuevo" else Command(resume=datos))

            nombre = f"trabajo {job_id}" + (" (reanudación)" if tipo != "nuevo" else "")
            with self.tracer.start_as_current_span(nombre, attributes={
                "openinference.span.kind": "CHAIN", "session.id": thread_id, "job.id": job_id,
                "input.value": json.dumps(datos, ensure_ascii=False),
            }) as span:
                try:
                    if "forzar_error" in datos.get("consulta", ""):
                        raise RuntimeError("Falla simulada para probar el estado FAILED")
                    resultado = await self.grafo.ainvoke(entrada, config)
                    interrupciones = resultado.get("__interrupt__") or []
                    if interrupciones:
                        await self.guardar(job_id, estado=EstadoTrabajo.WAITING_APPROVAL,
                                           aprobacion_pendiente=[i.value for i in interrupciones])
                        logger.info("Trabajo %s pausado: espera aprobación humana", job_id)
                    else:
                        resumen = self._resumen(resultado)
                        span.set_attribute("output.value", resumen.respuesta_final)
                        await self.guardar(job_id, estado=EstadoTrabajo.DONE, resultado=resumen.model_dump())
                        logger.info("Trabajo %s terminado", job_id)
                except Exception as e:
                    # Si el agente falla en segundo plano, el trabajo pasa a FAILED: el cliente no queda esperando
                    logger.exception("Trabajo %s falló", job_id)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    await self.guardar(job_id, estado=EstadoTrabajo.FAILED, error=f"{type(e).__name__}: {e}")

    @staticmethod
    def _resumen(resultado: dict[str, Any]) -> ResultadoTrabajo:
        mensajes = resultado.get("messages", [])
        ultima_pregunta = max((i for i, m in enumerate(mensajes) if isinstance(m, HumanMessage)), default=-1)
        turno = mensajes[ultima_pregunta + 1:]
        contribuciones = resultado.get("contribuciones") or []
        fuentes: list[str] = []
        for c in contribuciones:
            fuentes += [f for f in c.get("fuentes", []) if f not in fuentes]
        return ResultadoTrabajo(
            respuesta_final=resultado.get("respuesta_final", ""),
            flujo=[m.name for m in turno if isinstance(m, AIMessage) and m.name],
            pasos_supervisor=resultado.get("pasos_supervisor", 0),
            requiere_aprobacion=resultado.get("requiere_aprobacion", False),
            accion_ejecutada=resultado.get("accion_ejecutada", ""),
            fuentes=fuentes,
            contribuciones=[ContribucionResumen(paso=c["paso"], agente=c["agente"],
                                                herramientas_usadas=c["herramientas_usadas"])
                            for c in contribuciones],
        )
