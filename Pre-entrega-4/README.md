Pre-entrega 4: Sistema RAG escalable en la nube con Pinecone

Módulo de recuperación que indexa documentación técnica de FastAPI en un índice Serverless
de Pinecone, la consulta con un recuperador híbrido (BM25 + búsqueda vectorial) y mide su
calidad con Precision@5, Recall@5 y MRR sobre un Golden Set de 5 preguntas.


Archivos

- data/: dataset de 8 documentos Markdown sobre FastAPI. La primera línea de cada uno indica su categoría.
- golden_set.json: 5 preguntas de prueba con el documento fuente esperado.
- config.py: configuración compartida (índice, namespace, modelo de embeddings, chunking, k).
- setup_index.py: verifica si el índice existe y lo crea en modo Serverless si hace falta.
- ingest.py: carga los documentos, los fragmenta con RecursiveCharacterTextSplitter y los sube a Pinecone.
- rag_system.py: clase RAGSystem con un EnsembleRetriever que combina BM25 y Pinecone.
- evaluate.py: calcula las métricas con el Golden Set e imprime el reporte.
- Pre_entrega_4.ipynb: notebook de Colab con el código celda por celda y las salidas.


Cómo replicar el índice

1. Crear una cuenta gratuita en pinecone.io y generar una API key (sección API Keys).

2. Crear y activar un entorno virtual, e instalar las dependencias:

```
python -m venv .venv
.venv\Scripts\activate        (Windows)
source .venv/bin/activate     (Linux / Mac)
pip install -r requirements.txt
```

3. Copiar .env.example como .env y completar PINECONE_API_KEY.

4. Crear el índice (Serverless, AWS us-east-1, métrica coseno, 384 dimensiones):

```
python setup_index.py
```

5. Subir los documentos:

```
python ingest.py
```

Si el namespace ya tiene datos, no se vuelven a subir. Para reindexar: python ingest.py --forzar

6. Probar el recuperador y correr la evaluación:

```
python rag_system.py
python evaluate.py
```

No hace falta una clave de OpenAI ni de Anthropic: los embeddings se generan con un modelo
local y la consigna no requiere generar respuestas con un LLM.


Decisiones técnicas

- Embeddings: intfloat/multilingual-e5-small (local, gratuito, entiende español). Genera vectores
  de 384 dimensiones; el índice toma la dimensión del propio modelo y setup_index.py verifica
  que coincidan, para evitar el error de mismatch de dimensiones.
- Namespace: los vectores se guardan en el namespace fastapi-docs, separados de otros datasets
  que puedan compartir el índice.
- Metadatos: cada vector guarda fuente, titulo, categoria, pagina, chunk_id y el texto original
  (campo texto), así no hace falta consultar otra base de datos para recuperar el contenido.
- Chunking: chunk_size de 600 tokens y overlap de 60. Como cada documento tiene unos 200 tokens,
  entra entero en un solo chunk y ningún tema queda partido.
- Recuperador híbrido: EnsembleRetriever con pesos 0.5 / 0.5. BM25 usa un tokenizador propio
  (minúsculas y sin signos) para que los términos técnicos coincidan aunque cambie la escritura.


Métricas

- Recall@5: 1 si el documento esperado aparece entre los 5 recuperados, 0 si no.
- Precision@5: proporción de los 5 resultados que pertenecen al documento esperado.
- MRR: promedio de 1 / posición del documento correcto (1.0 = siempre aparece primero).


Resultados

```
Esperado                  BM25   Vectorial   Híbrido
seguridad.md                 2           1         1
middleware_cors.md           1           1         1
modelos_pydantic.md          1           1         1
dependencias.md              1           1         1
instalacion.md               1           2         1

Modo          Recall@5   Precision@5   Precision máx.     MRR
bm25              1.00          0.20             0.20    0.90
vectorial         1.00          0.20             0.20    0.90
hibrido           1.00          0.20             0.20    1.00
```

Conclusiones

- Los tres modos encuentran siempre el documento correcto (Recall@5 = 1.00).
- Precision@5 = 0.20 es el máximo posible: cada documento tiene un solo chunk, así que en el
  top-5 solo puede haber un resultado relevante.
- El MRR muestra la ventaja del híbrido: BM25 y la búsqueda vectorial fallan cada uno en una
  pregunta distinta (el documento correcto queda segundo), y al combinarlos el documento
  correcto aparece primero en las 5 preguntas.
- Limitación: con 8 documentos y top-5 se recupera más de la mitad de la base, por lo que el
  recall es fácil de alcanzar. Con un dataset más grande las diferencias entre modos serían mayores.