Pre-entrega 7: API de producción y monitoreo activo

API REST con FastAPI que expone el orquestador multi-agente de la Pre-entrega 6 (Supervisor +
Investigador + Analista + Síntesis). Las tareas se encolan y se procesan en segundo plano; el estado
de los trabajos y los checkpoints de LangGraph se guardan en Redis; cada ejecución envía trazas a
Arize Phoenix; y las solicitudes críticas (reservar un producto) se pausan hasta recibir aprobación
humana.


Estructura

```
app/
  main.py            API: POST /tasks, GET /tasks/{id}, POST /tasks/{id}/approve, GET /reservas, GET /health
  worker.py          cola de trabajos en segundo plano y estado en Redis (PENDING/RUNNING/WAITING_APPROVAL/DONE/FAILED)
  graph.py           orquestador multi-agente + checkpointer de Redis (AsyncRedisSaver)
  hitl.py            nodo de aprobación humana con interrupt()
  observability.py   instrumentación con Arize Phoenix (OpenInference)
  config.py          configuración, modelos y utilidades
  state.py           estado compartido del grafo
  datos.py           base de datos simulada (productos y reseñas)
  agents/            investigador, analista, supervisor y síntesis
scripts/
  prueba_carga.py    envía 5 peticiones concurrentes y mide la latencia
screenshots/         capturas del dashboard de Phoenix
docker-compose.yml   Redis + Phoenix + API
Pre_entrega_7.ipynb  notebook de Colab donde se desarrolló y probó todo
```


Cómo levantar el entorno

Opción A: Docker Compose (Redis, Phoenix y la API juntos)

```
cp .env.example .env          (completar GOOGLE_API_KEY)
docker compose up --build
```

- API y documentación interactiva: http://localhost:8000/docs
- Phoenix: http://localhost:6006

Opción B: sin Docker (Python 3.12 o superior)

1. Iniciar Redis 8 (incluye los módulos JSON y Search que necesita RedisSaver):

```
docker run -d -p 6379:6379 redis:8
```

2. Iniciar Phoenix:

```
pip install arize-phoenix
phoenix serve
```

3. Iniciar la API:

```
python -m venv .venv
source .venv/bin/activate        (Windows: .venv\Scripts\activate)
pip install -r requirements.txt
cp .env.example .env             (completar GOOGLE_API_KEY)
uvicorn app.main:app --port 8000
```


Uso de la API

```
# Crear una tarea: devuelve el job_id de inmediato (202 Accepted)
curl -X POST localhost:8000/tasks -H "Content-Type: application/json" \
     -d '{"consulta": "Compará los Pulse X1 y los Nova Pro por precio/calidad"}'

# Consultar el estado (polling)
curl localhost:8000/tasks/<job_id>

# Tarea crítica: queda en WAITING_APPROVAL hasta que un humano responde
curl -X POST localhost:8000/tasks -H "Content-Type: application/json" \
     -d '{"consulta": "Compará los Pulse X1 y los Nova Pro y reservame el que convenga más"}'

curl -X POST localhost:8000/tasks/<job_id>/approve -H "Content-Type: application/json" \
     -d '{"aprobado": true, "comentario": "Hay stock", "operador": "Guido"}'

# Reservas registradas por la acción crítica
curl localhost:8000/reservas
```

Prueba de carga con 5 peticiones concurrentes:

```
python scripts/prueba_carga.py http://localhost:8000
```


Decisiones de diseño

- API no bloqueante: POST /tasks guarda el trabajo en Redis como PENDING, lo pone en una cola
  (asyncio.Queue) y responde enseguida con el job_id. Todo el código es async: Redis con
  redis.asyncio, el grafo con ainvoke y el LLM con su cliente asíncrono.
- Worker: dentro del mismo proceso corren 2 workers asíncronos (configurable con WORKERS) que toman
  trabajos de la cola. Limitar la concurrencia evita superar los límites por minuto de la API de Gemini.
- Estado en Redis: cada trabajo es un hash job:<id> con su estado, resultado o error, y vence a las
  24 horas. Si el agente falla en segundo plano, la excepción se captura y el estado pasa a FAILED
  con el error, así el cliente no queda haciendo polling para siempre.
- Checkpoints en Redis: el grafo se compila con AsyncRedisSaver y usa el job_id como thread_id.
  Eso permite pausar un trabajo, liberar el worker y reanudarlo más tarde desde el mismo punto.
- Human-in-the-loop: el nodo aprobacion detecta las solicitudes críticas (reservar, apartar, pagar)
  y llama a interrupt(). El trabajo queda en WAITING_APPROVAL; al recibir POST /tasks/{id}/approve
  se reanuda con Command(resume=...) y, si fue aprobado, registra la reserva en Redis. LangGraph
  implementa la pausa con una excepción interna (Interrupt), por eso Phoenix la muestra como evento
  de tipo exception aunque el nodo termina en OK.
- Observabilidad: OpenInference instrumenta LangChain y LangGraph y envía a Phoenix cada nodo, cada
  agente, cada herramienta y cada llamada al LLM con sus tokens. Además, el worker abre un span
  "trabajo <job_id>" que agrupa toda la ejecución de un trabajo en una sola traza.
- Modelos de respaldo: supervisor, síntesis y especialistas tienen una lista de modelos de Gemini;
  si uno falla (saturación 503, cupo 429), se usa el siguiente sin cortar el trabajo.


Prueba de carga y lectura del dashboard

Se enviaron 5 peticiones concurrentes. La API respondió a todas de inmediato y los 5 trabajos
terminaron en DONE con el flujo supervisor -> investigador -> supervisor -> analista -> supervisor
-> sintesis.

```
Métrica (5 ejecuciones)                         Valor        Fuente
Latencia p95 de ejecución del agente            212,24 s     Phoenix, Metrics (04_latencia_p95.png)
Latencia p50 de ejecución del agente            157,34 s     Phoenix, Metrics
Costo total de la corrida                       $0,11 USD    Phoenix, Cost (03_costo.png)
Costo por ejecución                             ~$0,022 USD  costo total / 5
Latencia p95 de punta a punta (con cola)        437,7 s      timestamps de Redis
```

- La latencia de Phoenix mide la ejecución del agente desde que un worker toma el trabajo. La de
  punta a punta incluye además la espera en la cola: con 2 workers, 3 de los 5 trabajos esperaron
  a que se liberara uno.
- Dónde se concentra la latencia: en los especialistas. En la traza 02_traza_detalle.png el
  supervisor tarda unos 2,7 s, mientras que el investigador tarda 1m 33s, de los cuales 44,8 s son
  un intento fallido con un modelo saturado antes de pasar al modelo de respaldo. Las pausas entre
  nodos para respetar el límite por minuto del plan gratuito también suman.
- Qué consume más tokens y costo: los especialistas, que usan gemini-3.5-flash y procesan todas las
  reseñas. Ese modelo concentra la mayor parte del costo, incluidos sus tokens de razonamiento
  (Reasoning). Las llamadas del supervisor usan entre 400 y 1.500 tokens con modelos lite, mucho
  más baratos.
- Limpieza del dashboard: el polling del cliente (GET /tasks/{id}) generaba cientos de trazas de
  3 ms que distorsionaban los percentiles (la p95 daba 0,01 s). Para medir la corrida se borraron
  de Phoenix todas las trazas que no eran de los 5 trabajos de la prueba.


Capturas (carpeta screenshots/)

- 01_trazas_trabajos.png: lista de trazas, una por trabajo.
- 02_traza_detalle.png: árbol de una ejecución (supervisor, especialistas, modelo de respaldo).
- 03_costo.png: costo de la corrida y costo por modelo.
- 04_latencia_p95.png: percentiles de latencia de la corrida, incluida la p95.
- 05_traza_hitl_pausa.png: ejecución que se detiene en el nodo aprobacion.
- 06_traza_hitl_evento.png: evento de interrupción registrado en ese nodo.
- 07_resumen_carga.png: resumen de los 5 trabajos de la prueba de carga.


Sobre el LLM

Se usó Gemini por su plan gratuito. El plan gratuito tiene cupos bajos por día y por minuto, por
eso hay pausas entre nodos, 2 workers y modelos de respaldo. Con un plan pago se pueden quitar las
pausas y subir la cantidad de workers.
