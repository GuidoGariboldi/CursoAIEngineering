"""API REST del Sistema Intelligence. Recibe consultas, las encola y devuelve un job_id sin bloquear."""
import uuid
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, HTTPException, Path, Request, status
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from redis.asyncio import Redis

from app.config import configurar_logs, obtener_config, texto_de
from app.graph import construir_grafo
from app.observability import iniciar_observabilidad
from app.rag.retriever import base_conocimiento
from app.schemas import (AprobacionIn, ConversacionOut, EstadoTrabajo, HealthOut, MensajeOut, ReservaOut,
                         TareaCreada, TareaIn, TrabajoOut)
from app.worker import GestorTrabajos

JobId = Annotated[str, Path(pattern=r"^[a-f0-9]{12}$", description="Identificador del trabajo")]
ThreadId = Annotated[str, Path(pattern=r"^[A-Za-z0-9_-]{3,64}$", description="Identificador de la conversación")]


@asynccontextmanager
async def lifespan(app: FastAPI):
    configurar_logs()
    cfg = obtener_config()
    tracer = iniciar_observabilidad()
    await base_conocimiento.inicializar()                     # RAG: ingesta solo si hace falta
    redis = Redis.from_url(cfg.redis_url, decode_responses=True)
    async with AsyncRedisSaver.from_conn_string(cfg.redis_url) as checkpointer:
        await checkpointer.asetup()
        gestor = GestorTrabajos(construir_grafo(checkpointer), redis, tracer)
        await gestor.iniciar(cfg.workers)
        app.state.gestor, app.state.redis = gestor, redis
        yield
        await gestor.detener()
    await redis.aclose()


app = FastAPI(
    title="Sistema Intelligence",
    description="Asistente multi-agente de una tienda de tecnología: RAG sobre políticas, Supervisor con "
                "tres especialistas, aprobación humana para acciones críticas y trazas en Arize Phoenix.",
    version="1.0.0",
    lifespan=lifespan,
)


def _gestor(request: Request) -> GestorTrabajos:
    return request.app.state.gestor


@app.post("/tasks", response_model=TareaCreada, status_code=status.HTTP_202_ACCEPTED,
          summary="Enviar una consulta (nueva conversación o continuación)")
async def crear_tarea(tarea: TareaIn, request: Request) -> TareaCreada:
    gestor = _gestor(request)
    thread_id = tarea.thread_id or f"conv-{uuid.uuid4().hex[:12]}"
    if tarea.thread_id and await gestor.tiene_aprobacion_pendiente(thread_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "La conversación tiene una aprobación pendiente")
    job_id = uuid.uuid4().hex[:12]
    await gestor.crear(job_id, thread_id, tarea.consulta)
    return TareaCreada(job_id=job_id, thread_id=thread_id, estado=EstadoTrabajo.PENDING)


@app.get("/tasks/{job_id}", response_model=TrabajoOut, summary="Consultar el estado de un trabajo (polling)")
async def consultar_tarea(job_id: JobId, request: Request) -> TrabajoOut:
    trabajo = await _gestor(request).obtener(job_id)
    if trabajo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Trabajo no encontrado")
    return trabajo


@app.post("/tasks/{job_id}/approve", response_model=TareaCreada, status_code=status.HTTP_202_ACCEPTED,
          summary="Aprobar o rechazar una acción crítica pausada")
async def aprobar_tarea(job_id: JobId, aprobacion: AprobacionIn, request: Request) -> TareaCreada:
    gestor = _gestor(request)
    trabajo = await gestor.obtener(job_id)
    if trabajo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Trabajo no encontrado")
    if trabajo.estado != EstadoTrabajo.WAITING_APPROVAL:
        raise HTTPException(status.HTTP_409_CONFLICT, f"El trabajo no espera aprobación (estado {trabajo.estado.value})")
    await gestor.reanudar(job_id, aprobacion)
    return TareaCreada(job_id=job_id, thread_id=trabajo.thread_id, estado=EstadoTrabajo.PENDING)


@app.get("/conversations/{thread_id}", response_model=ConversacionOut,
         summary="Historial de una conversación (leído del checkpointer)")
async def ver_conversacion(thread_id: ThreadId, request: Request) -> ConversacionOut:
    estado = await _gestor(request).grafo.aget_state({"configurable": {"thread_id": thread_id}})
    mensajes = estado.values.get("messages", [])
    if not mensajes:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversación no encontrada")
    return ConversacionOut(thread_id=thread_id, mensajes=[
        MensajeOut(rol="usuario" if isinstance(m, HumanMessage) else "asistente", contenido=texto_de(m))
        for m in mensajes if isinstance(m, HumanMessage) or (isinstance(m, AIMessage) and m.name == "sintesis")
    ])


@app.get("/reservas", response_model=list[ReservaOut], summary="Reservas registradas por la acción crítica")
async def listar_reservas(request: Request) -> list[ReservaOut]:
    return [ReservaOut.model_validate_json(r) for r in await request.app.state.redis.lrange("reservas", 0, -1)]


@app.get("/health", response_model=HealthOut, summary="Estado de la API, Redis y la base de conocimiento")
async def health(request: Request) -> HealthOut:
    return HealthOut(api="ok", redis=await request.app.state.redis.ping(),
                     en_cola=_gestor(request).cola.qsize(),
                     documentos_indexados=base_conocimiento.cantidad_fragmentos)
