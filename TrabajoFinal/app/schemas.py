"""Contratos del sistema. Todo lo que entra o sale de la API y de las herramientas pasa por acá."""
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


# =====================================================================
# API
# =====================================================================
class EstadoTrabajo(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    DONE = "DONE"
    FAILED = "FAILED"


class TareaIn(BaseModel):
    consulta: str = Field(..., min_length=5, max_length=2000, description="Pedido del cliente en lenguaje natural")
    thread_id: str | None = Field(None, pattern=r"^[A-Za-z0-9_-]{3,64}$",
                                  description="Conversación a continuar. Si no se envía, se crea una nueva.")


class TareaCreada(BaseModel):
    job_id: str
    thread_id: str
    estado: EstadoTrabajo


class AprobacionIn(BaseModel):
    aprobado: bool
    comentario: str = Field("", max_length=500)
    operador: str = Field("operador", min_length=1, max_length=50)


class ContribucionResumen(BaseModel):
    paso: int
    agente: str
    herramientas_usadas: list[str]


class ResultadoTrabajo(BaseModel):
    respuesta_final: str
    flujo: list[str]
    pasos_supervisor: int
    requiere_aprobacion: bool
    accion_ejecutada: str
    fuentes: list[str]
    contribuciones: list[ContribucionResumen]


class TrabajoOut(BaseModel):
    id: str
    thread_id: str
    estado: EstadoTrabajo
    consulta: str
    creado: str
    actualizado: str
    resultado: ResultadoTrabajo | None = None
    aprobacion_pendiente: list[dict[str, Any]] | None = None
    error: str | None = None


class MensajeOut(BaseModel):
    rol: Literal["usuario", "asistente"]
    contenido: str


class ConversacionOut(BaseModel):
    thread_id: str
    mensajes: list[MensajeOut]


class ReservaOut(BaseModel):
    job_id: str
    solicitud: str
    aprobado_por: str
    comentario: str
    fecha: str


class HealthOut(BaseModel):
    api: Literal["ok"]
    redis: bool
    en_cola: int
    documentos_indexados: int


# =====================================================================
# Herramientas del Investigador (catálogo y reseñas)
# =====================================================================
class BuscarProductosIn(BaseModel):
    consulta: str = Field(..., min_length=1, max_length=100,
                          description='Nombre, modelo o categoría del producto, por ejemplo "Pulse X1" o "auriculares"')


class ProductoOut(BaseModel):
    producto_id: str
    nombre: str
    categoria: str
    precio: int = Field(ge=0)
    bateria_horas: int = Field(ge=0)
    cancelacion_ruido: bool
    garantia_meses: int = Field(ge=0)


class BuscarProductosOut(BaseModel):
    productos: list[ProductoOut] = []
    error: str | None = None


class ObtenerResenasIn(BaseModel):
    producto_id: str = Field(..., pattern=r"^P-\d{3}$", description='Identificador del producto, por ejemplo "P-101"')


class ResenaOut(BaseModel):
    puntaje: int = Field(ge=1, le=5)
    texto: str


class ObtenerResenasOut(BaseModel):
    producto_id: str
    resenas: list[ResenaOut] = []
    error: str | None = None


# =====================================================================
# Herramientas del Analista (cómputo)
# =====================================================================
class EstadisticasIn(BaseModel):
    valores: list[float] = Field(..., min_length=1, max_length=200, description="Lista de números, por ejemplo puntajes")


class EstadisticasOut(BaseModel):
    cantidad: int
    promedio: float
    minimo: float
    maximo: float
    desvio: float


class SentimientoIn(BaseModel):
    textos: list[str] = Field(..., min_length=1, max_length=100, description="Textos a analizar, por ejemplo reseñas")


class SentimientoDetalle(BaseModel):
    texto: str
    sentimiento: Literal["positivo", "mixto", "negativo"]


class SentimientoOut(BaseModel):
    positivo: int
    mixto: int
    negativo: int
    porcentaje_positivo: float = Field(ge=0, le=100)
    detalle: list[SentimientoDetalle]


class CalcularIn(BaseModel):
    expresion: str = Field(..., min_length=1, max_length=200, description='Expresión aritmética, por ejemplo "45000 / 4.2"')


class CalcularOut(BaseModel):
    expresion: str
    resultado: float | None = None
    error: str | None = None


# =====================================================================
# Herramienta del Documentalista (RAG)
# =====================================================================
class BuscarConocimientoIn(BaseModel):
    consulta: str = Field(..., min_length=3, max_length=300,
                          description="Pregunta sobre políticas de la tienda: garantías, devoluciones, envíos, pagos o uso de productos")


class FragmentoOut(BaseModel):
    fuente: str
    titulo: str
    contenido: str


class BuscarConocimientoOut(BaseModel):
    consulta: str
    fragmentos: list[FragmentoOut] = []
    error: str | None = None


# =====================================================================
# Decisión del Supervisor (salida estructurada del LLM)
# =====================================================================
class DecisionSupervisor(BaseModel):
    siguiente: Literal["investigador", "analista", "documentalista", "FINALIZAR"] = Field(
        description="Quién interviene ahora, o FINALIZAR si ya se puede responder.")
    instruccion: str = Field("", max_length=1000,
                             description="Tarea concreta y autocontenida para el especialista. Vacía si es FINALIZAR.")
    motivo: str = Field(..., max_length=500, description="Por qué se toma esta decisión, en una oración.")
