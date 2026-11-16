"""Human-in-the-loop: pausa el grafo antes de ejecutar una acción crítica (reservar un producto)."""
import json
import logging
from datetime import datetime, timezone
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt
from redis.asyncio import Redis

from app.config import REDIS_URL, normalizar, texto_de
from app.state import EstadoOrquestador

logger = logging.getLogger("orquestador")

# Pedidos con efectos secundarios: generan una reserva real en el sistema
PALABRAS_CRITICAS = ("reserv", "apart", "orden de compra", "pagar", "cobrar")

_redis: Redis | None = None


def _cliente_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(REDIS_URL, decode_responses=True)
    return _redis


def es_accion_critica(solicitud: str) -> bool:
    """El sistema identifica como crítica cualquier solicitud que implique reservar o pagar."""
    texto = normalizar(solicitud)
    return any(p in texto for p in PALABRAS_CRITICAS)


async def registrar_reserva(job_id: str, solicitud: str, aprobacion: dict[str, Any]) -> str:
    """Efecto secundario simulado: guarda la reserva en Redis."""
    reserva = {
        "job_id": job_id,
        "solicitud": solicitud,
        "aprobado_por": aprobacion.get("operador", "operador"),
        "comentario": aprobacion.get("comentario", ""),
        "fecha": datetime.now(timezone.utc).isoformat(),
    }
    numero = await _cliente_redis().rpush("reservas", json.dumps(reserva, ensure_ascii=False))
    return f"Reserva N° {numero} registrada (aprobada por {reserva['aprobado_por']})."


async def nodo_aprobacion(state: EstadoOrquestador, config: RunnableConfig) -> dict[str, Any]:
    """Si la solicitud es crítica, detiene el grafo hasta recibir la aprobación humana."""
    solicitud = texto_de(state["messages"][0])
    if not es_accion_critica(solicitud):
        logger.info("HITL: la solicitud no requiere aprobación")
        return {"requiere_aprobacion": False}

    logger.info("HITL: acción crítica detectada -> se pausa hasta recibir aprobación")
    contribuciones = state.get("contribuciones", [])
    decision = interrupt({
        "tipo": "aprobacion_requerida",
        "accion": "Registrar una reserva del producto recomendado",
        "solicitud": solicitud,
        "analisis": contribuciones[-1]["resultado"][:1500] if contribuciones else "",
    })

    # Esto se ejecuta recién cuando llega la respuesta del humano (Command(resume=...))
    aprobado = bool(decision.get("aprobado"))
    if aprobado:
        job_id = config["configurable"]["thread_id"]
        accion = await registrar_reserva(job_id, solicitud, decision)
    else:
        accion = f"La reserva NO se realizó: fue rechazada por el operador ({decision.get('comentario', '')})."
    logger.info("HITL: decisión recibida (aprobado=%s) -> %s", aprobado, accion)
    return {"requiere_aprobacion": True, "aprobacion": decision, "accion_ejecutada": accion}
