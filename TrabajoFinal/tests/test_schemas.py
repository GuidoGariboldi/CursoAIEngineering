"""Validación con Pydantic de las entradas de la API, la decisión del supervisor y la configuración."""
import pytest
from pydantic import ValidationError

from app.config import Configuracion
from app.schemas import AprobacionIn, DecisionSupervisor, TareaIn


def test_tarea_valida():
    tarea = TareaIn(consulta="Compará los Pulse X1 y los Nova Pro", thread_id="demo-1")
    assert tarea.thread_id == "demo-1"


@pytest.mark.parametrize("datos", [
    {"consulta": "hola"},                                   # muy corta
    {"consulta": "x" * 2001},                               # muy larga
    {"consulta": "Consulta válida", "thread_id": "con espacios"},
    {"consulta": "Consulta válida", "thread_id": "ab"},     # thread_id muy corto
])
def test_tarea_invalida(datos):
    with pytest.raises(ValidationError):
        TareaIn(**datos)


def test_aprobacion_invalida():
    with pytest.raises(ValidationError):
        AprobacionIn(aprobado=True, operador="")


def test_supervisor_no_puede_inventar_nodos():
    assert DecisionSupervisor(siguiente="documentalista", motivo="ok").siguiente == "documentalista"
    with pytest.raises(ValidationError):
        DecisionSupervisor(siguiente="vendedor", motivo="no existe")


def test_configuracion_invalida():
    with pytest.raises(ValidationError):
        Configuracion(redis_url="redis://x", phoenix_collector_endpoint="x", phoenix_project_name="x",
                      modelos_supervisor="m", modelos_especialistas="m", llm_timeout=60,
                      embeddings_model="e", chroma_collection="c", rag_top_k=4, rag_chunk_size=500,
                      rag_chunk_overlap=50, rag_peso_bm25=0.5, max_pasos_supervisor=8,
                      recursion_limit_especialista=10, recursion_limit_grafo=30, max_mensajes_historial=10,
                      pausa_entre_nodos=4, workers=0, job_ttl_segundos=86400)   # workers=0 no es válido
