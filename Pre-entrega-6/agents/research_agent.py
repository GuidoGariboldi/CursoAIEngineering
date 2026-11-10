"""Agente Investigador: busca productos y reseñas en la base de datos."""
import asyncio
import logging
from typing import Any, Callable

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from agents.base import ejecutar_especialista
from config import normalizar
from datos import PRODUCTOS, RESENAS
from state import EstadoOrquestador

logger = logging.getLogger("orquestador")

PROMPT_INVESTIGADOR = """Sos el agente Investigador de una tienda de tecnología.
Tu trabajo es buscar información en la base de datos con tus herramientas: productos y reseñas.
Reglas:
- Primero buscá cada producto para obtener su producto_id y después pedí sus reseñas.
- No hagas cálculos ni opines: solo reportá los datos encontrados.
- Devolvé para cada producto: producto_id, nombre, precio, características y la lista completa
  de reseñas (puntaje y texto), en un formato claro.
- Si no encontrás algo, decilo explícitamente."""


@tool
async def buscar_productos(consulta: str) -> dict[str, Any]:
    """Busca productos del catálogo por nombre, modelo o categoría (por ejemplo "Pulse X1",
    "Nova" o "auriculares").

    Devuelve los productos que coinciden con su producto_id, nombre, precio en pesos y
    características técnicas (batería, cancelación de ruido, garantía). Usala primero para
    obtener el producto_id, que se necesita para pedir las reseñas.
    """
    await asyncio.sleep(0.2)  # latencia simulada
    palabras = [p for p in normalizar(consulta).split() if len(p) >= 2]
    encontrados = [p for p in PRODUCTOS
                   if any(w in normalizar(f"{p['nombre']} {p['categoria']}") for w in palabras)]
    logger.info("buscar_productos(%r) -> %d resultado(s)", consulta, len(encontrados))
    if not encontrados:
        return {"error": f"No hay productos que coincidan con '{consulta}'."}
    return {"productos": encontrados}


@tool
async def obtener_resenas(producto_id: str) -> dict[str, Any]:
    """Devuelve todas las reseñas de clientes de un producto a partir de su producto_id
    (por ejemplo "P-101"). Cada reseña tiene un puntaje de 1 a 5 y el texto del comentario.
    El producto_id se obtiene antes con buscar_productos.
    """
    await asyncio.sleep(0.2)
    resenas = [{"puntaje": r["puntaje"], "texto": r["texto"]}
               for r in RESENAS if r["producto_id"] == producto_id]
    logger.info("obtener_resenas(%r) -> %d reseña(s)", producto_id, len(resenas))
    if not resenas:
        return {"error": f"No hay reseñas para el producto '{producto_id}'."}
    return {"producto_id": producto_id, "resenas": resenas}


HERRAMIENTAS_INVESTIGADOR = [buscar_productos, obtener_resenas]


def crear_nodo_investigador(llm: BaseChatModel) -> Callable:
    agente = create_react_agent(llm, HERRAMIENTAS_INVESTIGADOR, prompt=PROMPT_INVESTIGADOR)

    async def nodo_investigador(state: EstadoOrquestador) -> dict[str, Any]:
        # Solo recibe la instrucción del supervisor, no todo el historial
        return await ejecutar_especialista("investigador", agente, state["instruccion"], state)

    return nodo_investigador