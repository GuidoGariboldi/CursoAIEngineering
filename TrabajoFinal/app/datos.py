"""Base de datos simulada del catálogo. Se valida con los mismos esquemas que usan las herramientas."""
from app.schemas import ProductoOut

PRODUCTOS: list[ProductoOut] = [
    ProductoOut(producto_id="P-101", nombre="Auriculares Pulse X1", categoria="auriculares",
                precio=45000, bateria_horas=30, cancelacion_ruido=True, garantia_meses=12),
    ProductoOut(producto_id="P-102", nombre="Auriculares Nova Pro", categoria="auriculares",
                precio=62000, bateria_horas=40, cancelacion_ruido=True, garantia_meses=18),
    ProductoOut(producto_id="P-103", nombre="Auriculares Basic 200", categoria="auriculares",
                precio=18000, bateria_horas=12, cancelacion_ruido=False, garantia_meses=6),
]

RESENAS: list[tuple[str, int, str]] = [
    ("P-101", 5, "Excelente sonido y muy cómodos, los uso todo el día."),
    ("P-101", 4, "Buena batería, aunque el estuche es un poco frágil."),
    ("P-101", 5, "Los recomiendo, la cancelación de ruido es genial."),
    ("P-101", 3, "Suenan bien pero se desconectan a veces del celular."),
    ("P-101", 4, "Muy buena relación precio calidad."),
    ("P-102", 5, "Sonido increíble y la batería dura muchísimo."),
    ("P-102", 2, "Muy caros para lo que ofrecen, el micrófono es malo."),
    ("P-102", 4, "Cómodos y con buena cancelación de ruido."),
    ("P-102", 3, "Buenos, pero se calientan las orejas después de un rato."),
    ("P-102", 5, "Perfectos para viajar, excelente calidad."),
    ("P-103", 3, "Cumplen, pero el sonido es débil."),
    ("P-103", 2, "Se rompió el cable al mes, mala calidad."),
    ("P-103", 4, "Para el precio están bien."),
]
