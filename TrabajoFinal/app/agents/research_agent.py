"""Agente Investigador: consulta el catálogo de productos y las reseñas de clientes."""
import asyncio
import logging
from typing import Any, Callable

from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from app.agents.base import ejecutar_especialista
from app.config import crear_llm, normalizar
from app.datos import PRODUCTOS, RESENAS
from app.schemas import (BuscarProductosIn, BuscarProductosOut, ObtenerResenasIn, ObtenerResenasOut,
                         ResenaOut)
from app.state import EstadoOrquestador

logger = logging.getLogger("orquestador")

PROMPT_INVESTIGADOR = """Sos el agente Investigador de una tienda de tecnología.
Buscás información del catálogo con tus herramientas: productos y reseñas de clientes.
Reglas:
- Primero buscá cada producto para obtener su producto_id y después pedí sus reseñas si hacen falta.
- No hagas cálculos ni opines: reportá los datos encontrados, en un formato claro.
- Para cada producto incluí producto_id, nombre, precio, características, garantía y, si las pediste,
  todas las reseñas (puntaje y texto).
- Si no encontrás algo, decilo explícitamente."""


@tool(args_schema=BuscarProductosIn)
async def buscar_productos(consulta: str) -> dict[str, Any]:
    """Busca productos del catálogo por nombre, modelo o categoría (por ejemplo "Pulse X1",
    "Nova" o "auriculares"). Devuelve producto_id, nombre, precio en pesos, batería, cancelación
    de ruido y meses de garantía. Usala primero: el producto_id se necesita para pedir reseñas."""
    await asyncio.sleep(0.1)  # latencia simulada de la base de datos
    palabras = [p for p in normalizar(consulta).split() if len(p) >= 2]
    encontrados = [p for p in PRODUCTOS if any(w in normalizar(f"{p.nombre} {p.categoria}") for w in palabras)]
    logger.info("buscar_productos(%r) -> %d resultado(s)", consulta, len(encontrados))
    if not encontrados:
        return BuscarProductosOut(error=f"No hay productos que coincidan con '{consulta}'.").model_dump()
    return BuscarProductosOut(productos=encontrados).model_dump()


@tool(args_schema=ObtenerResenasIn)
async def obtener_resenas(producto_id: str) -> dict[str, Any]:
    """Devuelve todas las reseñas de clientes de un producto a partir de su producto_id
    (por ejemplo "P-101"). Cada reseña tiene un puntaje de 1 a 5 y el texto del comentario."""
    await asyncio.sleep(0.1)
    resenas = [ResenaOut(puntaje=p, texto=t) for pid, p, t in RESENAS if pid == producto_id]
    logger.info("obtener_resenas(%r) -> %d reseña(s)", producto_id, len(resenas))
    if not resenas:
        return ObtenerResenasOut(producto_id=producto_id, error="No hay reseñas para ese producto.").model_dump()
    return ObtenerResenasOut(producto_id=producto_id, resenas=resenas).model_dump()


HERRAMIENTAS_INVESTIGADOR = [buscar_productos, obtener_resenas]


def crear_nodo_investigador(modelos: list[str]) -> Callable:
    agentes = [(m, create_react_agent(crear_llm(m), HERRAMIENTAS_INVESTIGADOR,
                                      prompt=PROMPT_INVESTIGADOR, name="investigador")) for m in modelos]

    async def nodo_investigador(state: EstadoOrquestador) -> dict[str, Any]:
        # Contexto acotado: solo la instrucción del supervisor, no toda la conversación
        return await ejecutar_especialista("investigador", agentes, state["instruccion"], state)

    return nodo_investigador
