"""Evaluación del recuperador con un Golden Set: Precision@5, Recall@5 y MRR."""
import asyncio
import json
from collections import Counter

from config import GOLDEN_SET_PATH, TOP_K, configurar_logs
from ingest import cargar_documentos, fragmentar
from rag_system import RAGSystem, crear_rag_system

MODOS = ("bm25", "vectorial", "hibrido")


async def evaluar(rag: RAGSystem, golden_set: list[dict], chunks_por_documento: Counter,
                  modo: str, k: int = TOP_K) -> dict:
    """Corre el Golden Set con un modo de búsqueda y calcula las métricas."""
    filas = []
    for item in golden_set:
        esperado = item["documento_id_esperado"]
        docs = await rag.buscar(item["pregunta"], modo=modo)
        fuentes = [d.metadata["fuente"] for d in docs]

        relevantes = sum(f == esperado for f in fuentes)
        posicion = fuentes.index(esperado) + 1 if esperado in fuentes else None
        filas.append({
            "posicion": posicion,
            "recall": 1.0 if relevantes > 0 else 0.0,
            "precision": relevantes / k,
            "precision_max": min(chunks_por_documento[esperado], k) / k,
            "rr": 1 / posicion if posicion else 0.0,
        })

    n = len(filas)
    return {
        "filas": filas,
        "recall": sum(f["recall"] for f in filas) / n,
        "precision": sum(f["precision"] for f in filas) / n,
        "precision_max": sum(f["precision_max"] for f in filas) / n,
        "mrr": sum(f["rr"] for f in filas) / n,
    }


def imprimir_reporte(golden_set: list[dict], resultados: dict, chunks_por_documento: Counter):
    print("\n" + "=" * 78)
    print("DETALLE POR PREGUNTA (posición del documento correcto en el top-5; '-' = no apareció)")
    print("=" * 78)
    print(f"{'Esperado':<22}{'BM25':>8}{'Vectorial':>12}{'Híbrido':>10}   Pregunta")
    for i, item in enumerate(golden_set):
        pos = [resultados[m]["filas"][i]["posicion"] or "-" for m in MODOS]
        print(f"{item['documento_id_esperado']:<22}{pos[0]!s:>8}{pos[1]!s:>12}{pos[2]!s:>10}   "
              f"{item['pregunta'][:45]}...")

    print("\n" + "=" * 78)
    print("RESUMEN")
    print("=" * 78)
    print(f"{'Modo':<12}{'Recall@5':>10}{'Precision@5':>14}{'Precision máx.':>17}{'MRR':>8}")
    for modo in MODOS:
        r = resultados[modo]
        print(f"{modo:<12}{r['recall']:>10.2f}{r['precision']:>14.2f}"
              f"{r['precision_max']:>17.2f}{r['mrr']:>8.2f}")

    print(f"\nDocumentos indexados: {len(chunks_por_documento)} | "
          f"Chunks: {sum(chunks_por_documento.values())} | k = {TOP_K}")
    print("Precision máx.: el mejor valor posible, porque cada documento tiene un solo chunk "
          "y en el top-5 solo puede haber 1 relevante.")


async def main():
    with open(GOLDEN_SET_PATH, encoding="utf-8") as f:
        golden_set = json.load(f)

    rag = crear_rag_system()
    chunks_por_documento = Counter(c.metadata["fuente"] for c in fragmentar(cargar_documentos()))

    resultados = {}
    for modo in MODOS:
        resultados[modo] = await evaluar(rag, golden_set, chunks_por_documento, modo)

    imprimir_reporte(golden_set, resultados, chunks_por_documento)


if __name__ == "__main__":
    configurar_logs()
    asyncio.run(main())