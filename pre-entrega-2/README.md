Pre-entrega 2: Pipeline de extracción de entidades técnicas

Recibe un texto sin procesar (descripción de arquitectura o log de error) y devuelve
un objeto validado con Pydantic, usando una cadena LCEL de LangChain con reintentos.


Archivos

- schemas.py: modelo ExtraccionTecnica. Tecnologías como lista no vacía (sin duplicados),
  criticidad como enum (baja, media, alta) y resumen de 20 a 400 caracteres.
- chain.py: ChatPromptTemplate modular, cadena prompt | model.with_structured_output(Schema),
  validación del finish_reason, reintentos con .with_retry() y la función asíncrona process_text().
- main.py: mini-script de prueba que procesa tres textos en paralelo con asyncio.gather.
- Pre_entrega_2.ipynb: notebook de Colab con el código celda por celda y las salidas de las pruebas.


Cómo correrlo

```
pip install -r requirements.txt
cp .env.example .env
python main.py
```

En el archivo .env hay que completar GOOGLE_API_KEY con una clave propia.
El proveedor se elige con LLM_PROVIDER (gemini, openai o anthropic), igual que en la Pre-entrega 1.
Las pruebas se hicieron con Gemini (gemini-3.8-flash) porque es gratuito.


Resiliencia

- JSON mal formado o incompleto: si la salida no cumple el esquema, se reintenta.
- finish_reason: si el modelo cortó la respuesta por límite de tokens, se detecta antes de
  armar el objeto y se reintenta.
- Reintentos: .with_retry() con hasta 3 intentos y espera exponencial.
- Errores de la API (503, 429): los reintenta el cliente de Gemini (max_retries=5). Si igual
  fallan, process_text() los registra en el log y el programa sigue.


Ejemplo de salida

Entrada: log de error de una API en FastAPI con PostgreSQL, Redis y Kubernetes.

```
{
  "tecnologias": ["FastAPI", "psycopg2", "Redis", "Kubernetes"],
  "nivel_de_criticidad": "alta",
  "resumen_tecnico": "Agotamiento del pool de conexiones mediante psycopg2 y alta tasa de fallos en Redis provocaron timeouts en FastAPI, causando cuatro reinicios del pod en Kubernetes."
}
```


Pruebas realizadas

- Validación del esquema: tres entradas inválidas rechazadas antes de llamar al modelo
  (lista vacía, criticidad inexistente y resumen demasiado corto).
- Respuesta cortada: con LLM_MAX_TOKENS=30, Gemini devolvió finish_reason=MAX_TOKENS;
  el pipeline lo detectó, reintentó 3 veces y terminó con un error controlado.
- Texto ambiguo: el modelo no falló, pero devolvió categorías genéricas ("Base de datos", "Caché")
  en vez de tecnologías concretas. La validación garantiza la estructura, no la calidad del contenido.
- Alta demanda: Gemini devolvió 503 en algunas pruebas en paralelo; el pipeline los capturó
  como errores controlados sin cortar el programa.