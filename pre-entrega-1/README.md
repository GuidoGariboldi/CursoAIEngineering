# Cliente de LLM robusto y asíncrono

Pre-entrega 1 del curso de AI Engineering. Cliente asíncrono y unificado para **OpenAI**, **Anthropic** y **Gemini** en Python: una sola interfaz, proveedores intercambiables, streaming, validación con Pydantic y errores controlados.

Gemini se suma como tercer proveedor porque su API tiene nivel gratuito, lo que permite probar todo el flujo sin tarjeta.

## Estructura

```
├── Pre_entrega_1.ipynb        # notebook de Colab con la ejecución completa y sus salidas
├── main.py                    # script de prueba (modo normal + streaming)
├── requirements.txt
├── .env.example
└── llm_client/
    ├── schemas.py             # modelos Pydantic (mensajes, config, respuestas, errores)
    ├── base.py                # BaseLLMClient (clase abstracta + manejo de errores)
    ├── openai_client.py       # OpenAIClient    -> AsyncOpenAI
    ├── anthropic_client.py    # AnthropicClient -> AsyncAnthropic
    ├── gemini_client.py       # GeminiClient    -> genai.Client(...).aio
    └── manager.py             # AsyncLLMManager (elige proveedor según configuración)
```

El notebook y la carpeta `llm_client/` contienen el mismo código: en el notebook está celda por celda con las pruebas ejecutadas, y en los archivos está organizado como paquete.

## Cómo ejecutarlo

Requiere Python 3.12 o superior.

```bash
# 1. Entorno virtual
python3.12 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Dependencias
pip install -r requirements.txt

# 3. Variables de entorno
cp .env.example .env             # Windows: copy .env.example .env
# ...y completá tus claves en .env

# 4. Script de prueba
python main.py                           # usa el proveedor de LLM_PROVIDER
python main.py gemini openai anthropic   # prueba los tres, uno después del otro
```

El script pregunta "¿Qué es la entropía?" primero en modo normal y después en streaming.

### En Google Colab

Abrí `Pre_entrega_1.ipynb`, cargá `GOOGLE_API_KEY` en Secretos (ícono de la llave) con acceso desde el notebook, y ejecutá todas las celdas en orden.

## Variables de entorno

| Variable | Obligatoria | Descripción |
|---|---|---|
| `LLM_PROVIDER` | No (default `gemini`) | Proveedor a usar: `gemini`, `openai` o `anthropic` |
| `GOOGLE_API_KEY` | Si usás Gemini | Clave de Google AI Studio (gratuita) |
| `OPENAI_API_KEY` | Si usás OpenAI | Clave de la API de OpenAI |
| `ANTHROPIC_API_KEY` | Si usás Anthropic | Clave de la API de Anthropic |
| `GEMINI_MODEL` | No (default `gemini-flash-lite-latest`) | Modelo de Gemini |
| `OPENAI_MODEL` | No (default `gpt-4.1-mini`) | Modelo de OpenAI |
| `ANTHROPIC_MODEL` | No (default `claude-haiku-4-5-20251001`) | Modelo de Anthropic |
| `LLM_TIMEOUT` | No (default `30`) | Timeout por request, en segundos |
| `LLM_MAX_RETRIES` | No (default `2`) | Reintentos ante errores transitorios |

## Uso desde código

```python
from llm_client import AsyncLLMManager, ChatMessage, GenerationConfig

messages = [ChatMessage(role="user", content="¿Qué es la entropía?")]
config = GenerationConfig(temperature=0.3, max_tokens=1000)

async with AsyncLLMManager("gemini") as llm:   # o sin argumento: lee LLM_PROVIDER
    # Modo normal
    resp = await llm.generate(messages, config)
    print(resp.content if resp.ok else resp.error.message)

    # Streaming
    async for chunk in llm.stream(messages, config):
        print(chunk.content, end="", flush=True)
```

## Decisiones de diseño

**Intercambiabilidad.** `BaseLLMClient` define el contrato (`generate` y `stream`). Cada proveedor implementa solo su parte específica (`_generate`, `_stream` y `_clasificar`). `AsyncLLMManager` instancia el que corresponda según `LLM_PROVIDER`, así que cambiar de proveedor es cambiar una variable. Sumar Gemini fue agregar una clase, sin tocar el resto.

**Asincronía.** Se usan `AsyncOpenAI`, `AsyncAnthropic` y `client.aio` de Gemini, y todas las llamadas llevan `await`. No hay llamadas síncronas dentro de funciones `async`, por lo que el event loop nunca se bloquea. El notebook incluye una prueba con `asyncio.gather` que envía tres consultas a la vez.

**Streaming.** `stream()` es un generador asíncrono: recorre el stream del SDK con `async for` y hace `yield` de cada fragmento como `StreamChunk`.

**Validación.** `GenerationConfig` valida los parámetros (`temperature` entre 0 y 2, `max_tokens` positivo) y rechaza campos desconocidos. `ChatMessage` valida rol y contenido. Los errores se detectan antes de llamar a la API.

**Errores controlados.** `generate()` y `stream()` nunca dejan escapar excepciones de la API. Los errores de red, timeout, rate limit/cuota y autenticación se traducen a un `ErrorInfo` (tipo, mensaje, código HTTP, si es reintentable), que llega en `ModelResponse.error` o en un `StreamChunk` final. Antes de eso se reintentan los errores transitorios (red, 429, 5xx) con backoff exponencial: en OpenAI y Anthropic lo hace el SDK, y en Gemini lo hace el cliente.

La única excepción que sí se lanza es `ConfigurationError`, al crear el manager, si el proveedor no existe o falta la API key: es un error de configuración que conviene detectar al arrancar.

**Diferencias entre proveedores que el cliente resuelve:**

- Anthropic y Gemini reciben el mensaje `system` como parámetro aparte, no dentro de la lista de mensajes.
- Anthropic acepta temperatura de 0 a 1; si se pasa un valor mayor, se recorta a 1.
- Gemini llama `model` al rol del asistente.
- `temperature=None` omite el parámetro, útil para modelos de razonamiento que no lo aceptan.

## Pruebas realizadas

Ejecutadas en Google Colab (ver salidas en el notebook):

- Gemini: modo normal, streaming y tres consultas concurrentes.
- Validación: Pydantic rechaza temperatura fuera de rango, rol inexistente y parámetro mal escrito.
- Resiliencia: una API key inválida de OpenAI devuelve un error `authentication` (HTTP 401) sin romper el programa, y un 503 de Gemini por alta demanda se devolvió como error controlado.

Los clientes de OpenAI y Anthropic no se probaron con una respuesta real por no contar con crédito en esas APIs; sí se verificó su manejo de errores.
