"""Agente Analista: estadísticas, análisis de sentimiento y cálculos."""
import ast
import logging
import operator as op
import statistics
from typing import Any, Callable

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from agents.base import ejecutar_especialista
from config import normalizar
from state import EstadoOrquestador

logger = logging.getLogger("orquestador")

PROMPT_ANALISTA = """Sos el agente Analista de una tienda de tecnología.
Recibís datos ya obtenidos por el Investigador y los procesás con tus herramientas.
Reglas:
- Calculá el puntaje promedio de cada producto con calcular_estadisticas.
- Analizá el sentimiento de las reseñas de cada producto con analizar_sentimiento.
- Hacé cualquier cuenta (por ejemplo, precio / promedio) con calcular, nunca de memoria.
- Devolvé los resultados numéricos de cada producto y una conclusión breve basada en ellos.
- Si te faltan datos para algún cálculo, decí cuáles."""

PALABRAS_POSITIVAS = {"excelente", "buen", "buena", "buenos", "comodo", "comodos", "genial",
                      "recomiendo", "increible", "perfecto", "perfectos", "bien", "dura"}
PALABRAS_NEGATIVAS = {"fragil", "desconectan", "caro", "caros", "malo", "mala", "calientan",
                      "debil", "rompio", "falla"}

OPERADORES = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv,
              ast.Pow: op.pow, ast.USub: op.neg}


@tool
def calcular_estadisticas(valores: list[float]) -> dict[str, Any]:
    """Calcula estadísticas de una lista de números (por ejemplo, los puntajes de las reseñas
    de un producto): cantidad, promedio, mínimo, máximo y desvío estándar.
    Usala para obtener el puntaje promedio de un producto en lugar de calcularlo de memoria.
    """
    if not valores:
        return {"error": "La lista de valores está vacía."}
    resultado = {
        "cantidad": len(valores),
        "promedio": round(statistics.mean(valores), 2),
        "minimo": min(valores),
        "maximo": max(valores),
        "desvio": round(statistics.pstdev(valores), 2),
    }
    logger.info("calcular_estadisticas(%s) -> promedio %.2f", valores, resultado["promedio"])
    return resultado


@tool
def analizar_sentimiento(textos: list[str]) -> dict[str, Any]:
    """Analiza el sentimiento de una lista de textos (por ejemplo, las reseñas de un producto)
    con un léxico de palabras positivas y negativas.

    Devuelve, para cada texto, si es positivo, negativo o mixto, y un resumen con la cantidad
    de cada tipo y el porcentaje de reseñas positivas.
    """
    detalle = []
    for texto in textos:
        palabras = set(normalizar(texto).replace(",", " ").replace(".", " ").split())
        pos, neg = len(palabras & PALABRAS_POSITIVAS), len(palabras & PALABRAS_NEGATIVAS)
        etiqueta = "positivo" if pos > neg else "negativo" if neg > pos else "mixto"
        detalle.append({"texto": texto, "sentimiento": etiqueta})

    conteo = {e: sum(d["sentimiento"] == e for d in detalle) for e in ("positivo", "mixto", "negativo")}
    resumen = {**conteo,
               "porcentaje_positivo": round(100 * conteo["positivo"] / len(textos), 1) if textos else 0}
    logger.info("analizar_sentimiento(%d textos) -> %s", len(textos), resumen)
    return {"resumen": resumen, "detalle": detalle}


def _evaluar(nodo: ast.AST) -> float:
    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, (int, float)):
        return nodo.value
    if isinstance(nodo, ast.BinOp) and type(nodo.op) in OPERADORES:
        return OPERADORES[type(nodo.op)](_evaluar(nodo.left), _evaluar(nodo.right))
    if isinstance(nodo, ast.UnaryOp) and type(nodo.op) in OPERADORES:
        return OPERADORES[type(nodo.op)](_evaluar(nodo.operand))
    raise ValueError("Expresión no permitida")


@tool
def calcular(expresion: str) -> dict[str, Any]:
    """Calculadora: resuelve una expresión aritmética con +, -, *, /, ** y paréntesis,
    por ejemplo "45000 / 4.2". Usala para cualquier cuenta, como el precio por punto de
    puntaje (precio / promedio) o diferencias porcentuales, en lugar de calcular de memoria.
    """
    try:
        resultado = round(_evaluar(ast.parse(expresion, mode="eval").body), 2)
    except Exception as e:
        return {"error": f"No se pudo calcular '{expresion}': {e}"}
    logger.info("calcular(%r) -> %s", expresion, resultado)
    return {"expresion": expresion, "resultado": resultado}


HERRAMIENTAS_ANALISTA = [calcular_estadisticas, analizar_sentimiento, calcular]


def crear_nodo_analista(llm: BaseChatModel) -> Callable:
    agente = create_react_agent(llm, HERRAMIENTAS_ANALISTA, prompt=PROMPT_ANALISTA)

    async def nodo_analista(state: EstadoOrquestador) -> dict[str, Any]:
        # Solo recibe su instrucción y los datos del investigador, no todo el historial
        datos = [c["resultado"] for c in state.get("contribuciones", []) if c["agente"] == "investigador"]
        entrada = (state["instruccion"] + "\n\nDATOS DEL INVESTIGADOR:\n"
                   + (datos[-1] if datos else "(no hay datos)"))
        return await ejecutar_especialista("analista", agente, entrada, state)

    return nodo_analista