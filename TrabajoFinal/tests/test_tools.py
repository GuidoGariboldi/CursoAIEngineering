"""Herramientas de los agentes: resultados correctos y rechazo de entradas inválidas."""
import pytest
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import ValidationError

from app.agents.analyst_agent import analizar_sentimiento, calcular, calcular_estadisticas
from app.agents.research_agent import buscar_productos, obtener_resenas
from app.hitl import es_accion_critica
from app.state import historial_previo, pregunta_actual


async def test_buscar_productos():
    resultado = await buscar_productos.ainvoke({"consulta": "Pulse X1"})
    assert [p["producto_id"] for p in resultado["productos"]] == ["P-101"]


async def test_buscar_producto_inexistente():
    resultado = await buscar_productos.ainvoke({"consulta": "parlante"})
    assert resultado["productos"] == [] and resultado["error"]


async def test_resenas_con_id_invalido():
    with pytest.raises(ValidationError):
        await obtener_resenas.ainvoke({"producto_id": "101"})


def test_estadisticas():
    assert calcular_estadisticas.invoke({"valores": [5, 4, 5, 3, 4]})["promedio"] == 4.2


def test_sentimiento():
    resultado = analizar_sentimiento.invoke({"textos": ["Excelente sonido", "El micrófono es malo"]})
    assert (resultado["positivo"], resultado["negativo"]) == (1, 1)


def test_calculadora_segura():
    assert calcular.invoke({"expresion": "45000 / 4.2"})["resultado"] == 10714.29
    assert calcular.invoke({"expresion": "__import__('os')"})["error"]


def test_accion_critica():
    assert es_accion_critica("Reservame el que convenga más")
    assert not es_accion_critica("Compará los auriculares")


def test_historial_de_conversacion():
    mensajes = [HumanMessage("Primera pregunta"), AIMessage("Primera respuesta", name="sintesis"),
                AIMessage("Decisión interna", name="supervisor"), HumanMessage("Segunda pregunta")]
    assert pregunta_actual(mensajes) == "Segunda pregunta"
    assert historial_previo(mensajes, 10) == "Usuario: Primera pregunta\nAsistente: Primera respuesta"
