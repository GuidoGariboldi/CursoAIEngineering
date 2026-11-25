"""Agente Analista: estadísticas, análisis de sentimiento y cálculos sobre datos ya obtenidos."""
import ast
import logging
import operator as op
import statistics
from typing import Any, Callable

from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from app.agents.base import ejecutar_especialista
from app.config import crear_llm, normalizar
from app.schemas import (CalcularIn, CalcularOut, EstadisticasIn, EstadisticasOut, SentimientoDetalle,
                         SentimientoIn, SentimientoOut)
from app.state import EstadoOrquestador

logger = logging.getLogger("orquestador")

PROMPT_ANALISTA = """Sos el agente Analista de una tienda de tecnología.
Recibís datos ya obtenidos por el Investigador y los procesás con tus herramientas.
Reglas:
- Puntajes promedio con calcular_estadisticas; sentimiento de reseñas con analizar_sentimiento.
- Cualquier cuenta (precio / promedio, diferencias, porcentajes) con calcular, nunca de memoria.
- Al comparar porcentajes, aclarás sobre qué base se calcula cada uno.
- Devolvé los resultados numéricos de cada producto y una conclusión breve basada en ellos.
- Si te faltan datos para algún cálculo, decí cuáles."""

PALABRAS_POSITIVAS = {"excelente", "buen", "buena", "buenos", "comodo", "comodos", "genial",
                      "recomiendo", "increible", "perfecto", "perfectos", "bien", "dura"}
PALABRAS_NEGATIVAS = {"fragil", "desconectan", "caro", "caros", "malo", "mala", "calientan",
                      "debil", "rompio", "falla"}
OPERADORES = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv,
              ast.Pow: op.pow, ast.USub: op.neg}


@tool(args_schema=EstadisticasIn)
def calcular_estadisticas(valores: list[float]) -> dict[str, Any]:
    """Calcula cantidad, promedio, mínimo, máximo y desvío estándar de una lista de números
    (por ejemplo, los puntajes de las reseñas de un producto)."""
    salida = EstadisticasOut(cantidad=len(valores), promedio=round(statistics.mean(valores), 2),
                             minimo=min(valores), maximo=max(valores),
                             desvio=round(statistics.pstdev(valores), 2))
    logger.info("calcular_estadisticas(%s) -> promedio %.2f", valores, salida.promedio)
    return salida.model_dump()


@tool(args_schema=SentimientoIn)
def analizar_sentimiento(textos: list[str]) -> dict[str, Any]:
    """Clasifica cada texto (por ejemplo, reseñas) como positivo, negativo o mixto con un léxico
    de palabras, y devuelve el conteo de cada tipo y el porcentaje de positivos."""
    detalle = []
    for texto in textos:
        palabras = set(normalizar(texto).replace(",", " ").replace(".", " ").split())
        pos, neg = len(palabras & PALABRAS_POSITIVAS), len(palabras & PALABRAS_NEGATIVAS)
        etiqueta = "positivo" if pos > neg else "negativo" if neg > pos else "mixto"
        detalle.append(SentimientoDetalle(texto=texto, sentimiento=etiqueta))
    conteo = {e: sum(d.sentimiento == e for d in detalle) for e in ("positivo", "mixto", "negativo")}
    salida = SentimientoOut(**conteo, porcentaje_positivo=round(100 * conteo["positivo"] / len(textos), 1),
                            detalle=detalle)
    logger.info("analizar_sentimiento(%d textos) -> %s", len(textos), conteo)
    return salida.model_dump()


def _evaluar(nodo: ast.AST) -> float:
    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, (int, float)):
        return nodo.value
    if isinstance(nodo, ast.BinOp) and type(nodo.op) in OPERADORES:
        return OPERADORES[type(nodo.op)](_evaluar(nodo.left), _evaluar(nodo.right))
    if isinstance(nodo, ast.UnaryOp) and type(nodo.op) in OPERADORES:
        return OPERADORES[type(nodo.op)](_evaluar(nodo.operand))
    raise ValueError("Expresión no permitida")


@tool(args_schema=CalcularIn)
def calcular(expresion: str) -> dict[str, Any]:
    """Calculadora segura: resuelve una expresión con +, -, *, /, ** y paréntesis, por ejemplo
    "45000 / 4.2". Usala para cualquier cuenta en lugar de calcular de memoria."""
    try:
        resultado = round(_evaluar(ast.parse(expresion, mode="eval").body), 2)
    except Exception as e:
        return CalcularOut(expresion=expresion, error=f"No se pudo calcular: {e}").model_dump()
    logger.info("calcular(%r) -> %s", expresion, resultado)
    return CalcularOut(expresion=expresion, resultado=resultado).model_dump()


HERRAMIENTAS_ANALISTA = [calcular_estadisticas, analizar_sentimiento, calcular]


def crear_nodo_analista(modelos: list[str]) -> Callable:
    agentes = [(m, create_react_agent(crear_llm(m), HERRAMIENTAS_ANALISTA,
                                      prompt=PROMPT_ANALISTA, name="analista")) for m in modelos]

    async def nodo_analista(state: EstadoOrquestador) -> dict[str, Any]:
        # Contexto acotado: su instrucción + lo que encontró el investigador en esta pregunta
        datos = [c["resultado"] for c in state.get("contribuciones") or [] if c["agente"] == "investigador"]
        entrada = state["instruccion"] + "\n\nDATOS DEL INVESTIGADOR:\n" + (datos[-1] if datos else "(no hay datos)")
        return await ejecutar_especialista("analista", agentes, entrada, state)

    return nodo_analista
