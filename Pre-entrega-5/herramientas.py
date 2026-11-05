"""Herramientas del agente. El LLM elige cuál usar leyendo solo sus docstrings."""
import asyncio
import logging
from typing import Any

from langchain_core.tools import tool

from base_datos import CLIENTES, FALLAS_SIMULADAS, PEDIDOS

logger = logging.getLogger("agente")


@tool
async def buscar_cliente(nombre: str) -> dict[str, Any]:
    """Busca clientes por nombre o apellido (no hace falta el nombre completo).

    Usala cuando el usuario mencione a un cliente por su nombre y necesites su cliente_id
    para consultar pedidos. Devuelve la lista de coincidencias con cliente_id, nombre y ciudad.
    Si hay varias coincidencias, NO elijas una: preguntale al usuario cuál es.
    Si no hay coincidencias, devuelve un error.
    """
    await asyncio.sleep(0.2)  # latencia simulada de la base de datos
    texto = nombre.strip().lower()
    coincidencias = [c for c in CLIENTES if texto in c["nombre"].lower()]
    logger.info(" buscar_cliente(%r) -> %d coincidencia(s)", nombre, len(coincidencias))

    if not coincidencias:
        return {"error": f"No existe ningún cliente que coincida con '{nombre}'."}
    if len(coincidencias) > 1:
        return {"coincidencias": coincidencias,
                "aviso": "Hay más de un cliente con ese nombre. Pedile al usuario que aclare cuál."}
    return {"coincidencias": coincidencias}


@tool
async def buscar_pedidos(cliente_id: int) -> dict[str, Any]:
    """Devuelve el resumen de pedidos de un cliente a partir de su cliente_id numérico.

    Usala para responder cuántos pedidos tiene un cliente, cuánto gastó en total o cuál
    fue su último pedido. Devuelve la cantidad de pedidos, el total en pesos y la lista
    de pedidos (pedido_id, fecha, total y estado) ordenada del más viejo al más nuevo.
    Si devuelve un error temporal, volvé a llamarla con el mismo cliente_id.
    """
    await asyncio.sleep(0.2)
    if cliente_id in FALLAS_SIMULADAS:
        FALLAS_SIMULADAS.discard(cliente_id)
        logger.warning(" buscar_pedidos(%d) -> timeout simulado", cliente_id)
        return {"error": "Timeout temporal de la base de datos. Reintentá la misma consulta."}

    if not any(c["cliente_id"] == cliente_id for c in CLIENTES):
        logger.info(" buscar_pedidos(%d) -> cliente inexistente", cliente_id)
        return {"error": f"No existe el cliente_id {cliente_id}."}

    pedidos = sorted((p for p in PEDIDOS if p["cliente_id"] == cliente_id), key=lambda p: p["fecha"])
    logger.info(" buscar_pedidos(%d) -> %d pedido(s)", cliente_id, len(pedidos))
    return {
        "cliente_id": cliente_id,
        "pedidos": len(pedidos),
        "total": sum(p["total"] for p in pedidos),
        "lista": [{k: p[k] for k in ("pedido_id", "fecha", "total", "estado")} for p in pedidos],
    }


@tool
async def detalle_pedido(pedido_id: int) -> dict[str, Any]:
    """Devuelve el detalle completo de un pedido a partir de su pedido_id numérico:
    fecha, total, estado de envío y productos comprados.

    Usala cuando el usuario pregunte qué compró en un pedido puntual o en qué estado está.
    El pedido_id se obtiene antes con buscar_pedidos.
    """
    await asyncio.sleep(0.2)
    pedido = next((p for p in PEDIDOS if p["pedido_id"] == pedido_id), None)
    logger.info(" detalle_pedido(%d) -> %s", pedido_id, "encontrado" if pedido else "no existe")
    if pedido is None:
        return {"error": f"No existe el pedido {pedido_id}."}
    return dict(pedido)


HERRAMIENTAS = [buscar_cliente, buscar_pedidos, detalle_pedido]