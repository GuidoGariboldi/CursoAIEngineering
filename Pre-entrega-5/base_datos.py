"""Base de datos simulada de clientes y pedidos."""
from typing import TypedDict


class Cliente(TypedDict):
    cliente_id: int
    nombre: str
    ciudad: str


class Pedido(TypedDict):
    pedido_id: int
    cliente_id: int
    fecha: str
    total: int
    estado: str
    productos: list[str]


CLIENTES: list[Cliente] = [
    {"cliente_id": 101, "nombre": "Lucía Fernández", "ciudad": "Rosario"},
    {"cliente_id": 102, "nombre": "Martín Gómez", "ciudad": "Córdoba"},
    {"cliente_id": 103, "nombre": "Martín Sosa", "ciudad": "Mendoza"},
    {"cliente_id": 104, "nombre": "Carla Ruiz", "ciudad": "La Plata"},
]

PEDIDOS: list[Pedido] = [
    {"pedido_id": 5001, "cliente_id": 102, "fecha": "2026-08-14", "total": 4500,
     "estado": "entregado", "productos": ["Mouse inalámbrico", "Pad gamer"]},
    {"pedido_id": 5007, "cliente_id": 102, "fecha": "2026-09-30", "total": 6000,
     "estado": "entregado", "productos": ["Teclado mecánico"]},
    {"pedido_id": 5012, "cliente_id": 102, "fecha": "2026-10-21", "total": 4000,
     "estado": "en camino", "productos": ["Auriculares USB"]},
    {"pedido_id": 5003, "cliente_id": 101, "fecha": "2026-09-02", "total": 12800,
     "estado": "entregado", "productos": ["Disco SSD 1TB"]},
    {"pedido_id": 5010, "cliente_id": 101, "fecha": "2026-10-11", "total": 3200,
     "estado": "cancelado", "productos": ["Cable HDMI", "Adaptador USB-C"]},
    {"pedido_id": 5009, "cliente_id": 103, "fecha": "2026-10-05", "total": 21000,
     "estado": "entregado", "productos": ["Monitor 24 pulgadas"]},
]

# Simula una falla pasajera: la primera consulta de pedidos del cliente 101 da timeout
FALLAS_SIMULADAS: set[int] = {101}