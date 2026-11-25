"""Envía a Arize Phoenix una traza por trabajo, con cada nodo, herramienta y llamada al LLM."""
import logging

from openinference.instrumentation.langchain import LangChainInstrumentor
from opentelemetry.trace import Tracer
from phoenix.otel import register

from app.config import obtener_config

logger = logging.getLogger("orquestador")


def iniciar_observabilidad() -> Tracer:
    cfg = obtener_config()
    tracer_provider = register(project_name=cfg.phoenix_project_name,
                               endpoint=cfg.phoenix_collector_endpoint, batch=True, verbose=False)
    LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
    logger.info("Observabilidad activa: proyecto '%s'", cfg.phoenix_project_name)
    return tracer_provider.get_tracer("intelligence-system")
