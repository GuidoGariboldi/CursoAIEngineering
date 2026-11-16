"""API REST: recibe tareas, las encola y devuelve un job_id sin bloquear."""
import json
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.config import REDIS_URL, WORKERS, configurar_logs
from app.graph import construir_grafo
from app.observability import iniciar_observabilidad
from app.worker import PENDING, WAITING_APPROVAL, GestorTrabajos, _ahora


@asynccontextmanager
async def lifespan(app: FastAPI):
    configurar_logs()
    tracer = iniciar_observabilidad()
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    async with AsyncRedisSaver.from_conn_string(REDIS_URL) as checkpointer:
        await checkpointer.asetup()
        gestor = GestorTrabajos(construir_grafo(checkpointer), redis, tracer)
        await gestor.iniciar(WORKERS)
        app.state.gestor = gestor
        app.state.redis = redis
        yield
        await gestor.detener()
    await redis.aclose()


app = FastAPI(title="Orquestador multi-agente", version="1.0.0", lifespan=lifespan)


class TareaIn(BaseModel):
    consulta: str = Field(..., min_length=5, description="Pedido del cliente en lenguaje natural")


class AprobacionIn(BaseModel):
    aprobado: bool
    comentario: str = ""
    operador: str = "operador"


@app.post("/tasks", status_code=status.HTTP_202_ACCEPTED)
async def crear_tarea(tarea: TareaIn, request: Request) -> dict[str, str]:
    """Encola la tarea y devuelve el job_id de inmediato (no espera al agente)."""
    gestor: GestorTrabajos = request.app.state.gestor
    job_id = uuid.uuid4().hex[:12]
    await gestor.guardar(job_id, id=job_id, estado=PENDING, consulta=tarea.consulta, creado=_ahora())
    await gestor.encolar(job_id, "nuevo", {"consulta": tarea.consulta})
    return {"job_id": job_id, "estado": PENDING}


@app.get("/tasks/{job_id}")
async def consultar_tarea(job_id: str, request: Request) -> dict[str, Any]:
    """Devuelve el estado actual del trabajo (para hacer polling)."""
    trabajo = await request.app.state.gestor.obtener(job_id)
    if trabajo is None:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    return trabajo


@app.post("/tasks/{job_id}/approve", status_code=status.HTTP_202_ACCEPTED)
async def aprobar_tarea(job_id: str, aprobacion: AprobacionIn, request: Request) -> dict[str, str]:
    """Respuesta humana a una tarea pausada: la reanuda con la decisión tomada."""
    gestor: GestorTrabajos = request.app.state.gestor
    trabajo = await gestor.obtener(job_id)
    if trabajo is None:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    if trabajo["estado"] != WAITING_APPROVAL:
        raise HTTPException(status_code=409, detail=f"El trabajo no espera aprobación (estado {trabajo['estado']})")
    await gestor.guardar(job_id, estado=PENDING)
    await gestor.encolar(job_id, "reanudar", aprobacion.model_dump())
    return {"job_id": job_id, "estado": PENDING}


@app.get("/reservas")
async def listar_reservas(request: Request) -> list[dict[str, Any]]:
    """Reservas registradas por la acción crítica (solo las aprobadas)."""
    return [json.loads(r) for r in await request.app.state.redis.lrange("reservas", 0, -1)]


@app.get("/health")
async def health(request: Request) -> dict[str, Any]:
    return {"api": "ok", "redis": await request.app.state.redis.ping(),
            "en_cola": request.app.state.gestor.cola.qsize()}
