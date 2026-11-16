"""Instrumentación: envía a Arize Phoenix una traza por trabajo, con cada nodo y llamada al LLM."""
import logging

from openinference.instrumentation.langchain import LangChainInstrumentor
from opentelemetry.trace import Tracer
from phoenix.otel import register

from app.config import PHOENIX_COLLECTOR_ENDPOINT, PHOENIX_PROJECT_NAME

logger = logging.getLogger("orquestador")


def iniciar_observabilidad() -> Tracer:
    tracer_provider = register(
        project_name=PHOENIX_PROJECT_NAME,
        endpoint=PHOENIX_COLLECTOR_ENDPOINT,
        batch=True,
        verbose=False,   # sin el cartel de bienvenida de Phoenix
    )
    # Instrumenta automáticamente LangChain y LangGraph: nodos, agentes, herramientas y LLM
    LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
    logger.info("Observabilidad activa: proyecto '%s' en %s", PHOENIX_PROJECT_NAME, PHOENIX_COLLECTOR_ENDPOINT)
    return tracer_provider.get_tracer("orquestador-api")
