"""Datos simulados: catálogo de productos y reseñas de clientes."""
from typing import TypedDict


class Producto(TypedDict):
    producto_id: str
    nombre: str
    categoria: str
    precio: int
    bateria_horas: int
    cancelacion_ruido: bool
    garantia_meses: int


class Resena(TypedDict):
    producto_id: str
    puntaje: int
    texto: str


PRODUCTOS: list[Producto] = [
    {"producto_id": "P-101", "nombre": "Auriculares Pulse X1", "categoria": "auriculares",
        "precio": 45000, "bateria_horas": 30, "cancelacion_ruido": True, "garantia_meses": 12},
    {"producto_id": "P-102", "nombre": "Auriculares Nova Pro", "categoria": "auriculares",
        "precio": 62000, "bateria_horas": 40, "cancelacion_ruido": True, "garantia_meses": 18},
    {"producto_id": "P-103", "nombre": "Auriculares Basic 200", "categoria": "auriculares",
        "precio": 18000, "bateria_horas": 12, "cancelacion_ruido": False, "garantia_meses": 6},
]

RESENAS: list[Resena] = [
    {"producto_id": "P-101", "puntaje": 5, "texto": "Excelente sonido y muy cómodos, los uso todo el día."},
    {"producto_id": "P-101", "puntaje": 4, "texto": "Buena batería, aunque el estuche es un poco frágil."},
    {"producto_id": "P-101", "puntaje": 5, "texto": "Los recomiendo, la cancelación de ruido es genial."},
    {"producto_id": "P-101", "puntaje": 3, "texto": "Suenan bien pero se desconectan a veces del celular."},
    {"producto_id": "P-101", "puntaje": 4, "texto": "Muy buena relación precio calidad."},
    {"producto_id": "P-102", "puntaje": 5, "texto": "Sonido increíble y la batería dura muchísimo."},
    {"producto_id": "P-102", "puntaje": 2, "texto": "Muy caros para lo que ofrecen, el micrófono es malo."},
    {"producto_id": "P-102", "puntaje": 4, "texto": "Cómodos y con buena cancelación de ruido."},
    {"producto_id": "P-102", "puntaje": 3, "texto": "Buenos, pero se calientan las orejas después de un rato."},
    {"producto_id": "P-102", "puntaje": 5, "texto": "Perfectos para viajar, excelente calidad."},
    {"producto_id": "P-103", "puntaje": 3, "texto": "Cumplen, pero el sonido es débil."},
    {"producto_id": "P-103", "puntaje": 2, "texto": "Se rompió el cable al mes, mala calidad."},
    {"producto_id": "P-103", "puntaje": 4, "texto": "Para el precio están bien."},
]