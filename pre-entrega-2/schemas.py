"""Esquema de salida del pipeline de extracción de entidades técnicas."""
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class NivelCriticidad(str, Enum):
    BAJA = "baja"
    MEDIA = "media"
    ALTA = "alta"


class ExtraccionTecnica(BaseModel):
    """Entidades técnicas extraídas de un texto (arquitectura de software o log de error)."""

    tecnologias: list[str] = Field(
        ...,
        min_length=1,
        description="Tecnologías, lenguajes, frameworks, bases de datos o servicios "
                    "mencionados explícitamente en el texto, con su nombre oficial.",
    )
    nivel_de_criticidad: NivelCriticidad = Field(
        ...,
        description="Gravedad del problema o riesgo descripto: baja, media o alta.",
    )
    resumen_tecnico: str = Field(
        ...,
        min_length=20,
        max_length=400,
        description="Resumen técnico de una o dos oraciones, en español.",
    )

    @field_validator("tecnologias")
    @classmethod
    def limpiar_tecnologias(cls, valores: list[str]) -> list[str]:
        """Quita espacios, vacíos y duplicados."""
        limpias, vistas = [], set()
        for valor in valores:
            valor = valor.strip()
            if valor and valor.lower() not in vistas:
                limpias.append(valor)
                vistas.add(valor.lower())
        if not limpias:
            raise ValueError("La lista de tecnologías no puede estar vacía")
        return limpias