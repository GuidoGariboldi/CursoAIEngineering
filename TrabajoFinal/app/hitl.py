"""Human-in-the-loop: pausa el grafo antes de ejecutar una acción crítica (reservar un producto)."""
import logging
from datetime import datetime, timezone
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt
from redis.asyncio import Redis

from app.config import normalizar, obtener_config
from app.schemas import AprobacionIn, ReservaOut
from app.state import EstadoOrquestador, pregunta_actual

logger = logging.getLogger("orquestador")

PALABRAS_CRITICAS = ("reserv", "apart", "orden de compra", "pagar", "cobrar")
_redis: Redis | None = None


def _cliente_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(obtener_config().redis_url, decode_responses=True)
    return _redis


def es_accion_critica(solicitud: str) -> bool:
    """Una solicitud es crítica si implica reservar, apartar o pagar: tiene efectos reales."""
    texto = normalizar(solicitud)
    return any(p in texto for p in PALABRAS_CRITICAS)


async def registrar_reserva(job_id: str, solicitud: str, aprobacion: AprobacionIn) -> str:
    """Efecto secundario: guarda la reserva en Redis, validada con Pydantic."""
    reserva = ReservaOut(job_id=job_id, solicitud=solicitud, aprobado_por=aprobacion.operador,
                         comentario=aprobacion.comentario, fecha=datetime.now(timezone.utc).isoformat())
    numero = await _cliente_redis().rpush("reservas", reserva.model_dump_json())
    return f"Reserva N° {numero} registrada (aprobada por {reserva.aprobado_por})."


async def nodo_aprobacion(state: EstadoOrquestador, config: RunnableConfig) -> dict[str, Any]:
    solicitud = pregunta_actual(state["messages"])
    if not es_accion_critica(solicitud):
        logger.info("HITL: la solicitud no requiere aprobación")
        return {"requiere_aprobacion": False}

    logger.info("HITL: acción crítica detectada -> se pausa hasta recibir aprobación")
    contribuciones = state.get("contribuciones") or []
    respuesta = interrupt({
        "tipo": "aprobacion_requerida",
        "accion": "Registrar una reserva del producto recomendado",
        "solicitud": solicitud,
        "analisis": contribuciones[-1]["resultado"][:1500] if contribuciones else "",
    })

    # Esto se ejecuta cuando llega la respuesta humana (Command(resume=...)), validada con Pydantic
    decision = AprobacionIn.model_validate(respuesta)
    if decision.aprobado:
        accion = await registrar_reserva(config["configurable"]["job_id"], solicitud, decision)
    else:
        accion = f"La reserva NO se realizó: la rechazó {decision.operador} ({decision.comentario})."
    logger.info("HITL: decisión recibida (aprobado=%s) -> %s", decision.aprobado, accion)
    return {"requiere_aprobacion": True, "aprobacion": decision.model_dump(), "accion_ejecutada": accion}
