"""Mini-script de prueba asíncrono: tres textos procesados en paralelo."""
import asyncio
import json
import logging

from chain import process_text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("httpx").setLevel(logging.WARNING)

TEXTOS = {
    "log_error": (
        "2026-10-14 03:12:44 ERROR [api-gateway] FastAPI worker timeout: "
        "psycopg2.OperationalError: too many connections for role 'app'. "
        "Redis cache miss rate 92%. Kubernetes reinició el pod 4 veces en 10 minutos."
    ),
    "arquitectura": (
        "El frontend en React consume una API REST hecha con NestJS. Los datos se "
        "guardan en MySQL y las imágenes en un bucket de S3. Todo corre en Docker "
        "y se despliega con GitHub Actions. Por ahora no hay problemas reportados."
    ),
    "ambiguo": (
        "Ayer algo andaba lento, creo que era la base o el caché, no sé. "
        "Hoy parece que anda."
    ),
}


async def main():
    resultados = await asyncio.gather(
        *(process_text(t) for t in TEXTOS.values()),
        return_exceptions=True,
    )
    for nombre, r in zip(TEXTOS, resultados):
        print(f"\n=== {nombre} ===")
        if isinstance(r, Exception):
            print(f"Error controlado ({type(r).__name__}): {r}")
        else:
            print(json.dumps(r.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())