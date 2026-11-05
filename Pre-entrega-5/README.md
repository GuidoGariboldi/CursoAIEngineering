Pre-entrega 5: Agente de razonamiento cíclico con memoria persistente

Agente ReAct construido con LangGraph para atención al cliente de una tienda. Consulta una
base de datos simulada de clientes y pedidos, decide por sí mismo qué herramienta usar en cada
paso, reintenta cuando una herramienta falla, pide aclaraciones cuando la información es ambigua
y recuerda la conversación gracias a la persistencia en SQLite por thread_id.


Archivos

- config.py: configuración (modelo, base de checkpoints, recursion_limit, pausas).
- base_datos.py: base de datos simulada de clientes y pedidos, con una falla pasajera simulada.
- herramientas.py: tres herramientas con @tool y docstrings descriptivos:
  buscar_cliente, buscar_pedidos y detalle_pedido.
- agente.py: estado (hereda de MessagesState), LLM con bind_tools y StateGraph con nodo de modelo,
  nodo de herramientas (ToolNode) y arista condicional (tools_condition).
- main.py: ejecuta las pruebas, lee la traza desde el checkpointer y la guarda en traza_react.json.
- traza_react.json: traza ReAct de una ejecución real.
- Pre_entrega_5.ipynb: notebook de Colab con el código celda por celda y las salidas.


Cómo levantar el entorno (Python 3.12 o superior)

```
python -m venv .venv
.venv\Scripts\activate        (Windows)
source .venv/bin/activate     (Linux / Mac)
pip install -r requirements.txt
```

Copiar .env.example como .env y completar GOOGLE_API_KEY con una clave de Gemini
(se obtiene gratis en aistudio.google.com). Después:

```
python main.py
```


Arquitectura del grafo

```
START -> agente
agente -> tools     (si el modelo pidió una herramienta)
agente -> END       (si el modelo ya tiene la respuesta)
tools  -> agente    (el resultado vuelve al modelo: ciclo ReAct)
```

- Estado: EstadoAgente hereda de MessagesState (los mensajes se acumulan con el reducer
  add_messages) y agrega llamadas_llm, un contador que se acumula con operator.add.
- Autonomía: no hay rutas if/else; tools_condition decide el camino según si el modelo pidió
  una herramienta.
- Errores de herramientas: ToolNode con handle_tool_errors=True devuelve el error al agente
  como mensaje en lugar de cortar el programa.
- Persistencia: AsyncSqliteSaver (la versión asíncrona de SqliteSaver) guarda el estado en
  checkpoints.db. Cada conversación se identifica con su thread_id.
- recursion_limit = 10 en cada invocación, para evitar bucles infinitos.
- Estado sucio: antes de cada llamada al modelo se recorta el historial a los últimos 20 mensajes
  con trim_messages.


Sobre el LLM

La consigna sugiere OpenAI o Anthropic. Se usó Gemini (gemini-3-flash-preview) porque tiene un plan
gratuito; bind_tools funciona igual con cualquier proveedor de LangChain. El plan gratuito tiene
límites de consultas por minuto y por día, por eso main.py hace una pausa entre preguntas.


Pruebas y resultados (ver traza_react.json)

1. Razonamiento multi-paso (sesion-1). "¿Cuántos pedidos tuvo Martín Gómez y cuál fue el total?"
   El agente usó buscar_cliente para obtener el ID y después buscar_pedidos.
   Respuesta: 3 pedidos por $14.500.

2. Memoria con el mismo thread_id (sesion-1). "¿Y el último? ¿Qué compró y en qué estado está?"
   Sin volver a nombrar al cliente, el agente usó detalle_pedido(5012).
   Respuesta: Auriculares USB, $4.000, en camino.

3. Ciclo de retorno ante un error (sesion-2). "¿Cuánto gastó en total Lucía Fernández?"
   La primera llamada a buscar_pedidos devolvió un timeout simulado; el agente reintentó solo y
   obtuvo los datos (3 llamadas a herramientas). Respuesta: $16.000 en 2 pedidos.

4. Pedido de aclaración (sesion-3). "¿Cuántos pedidos tiene Martín?"
   buscar_cliente encontró dos Martín; el agente no eligió y preguntó cuál. Ante "El de Mendoza",
   usó buscar_pedidos(103). Respuesta: 1 pedido por $21.000.

5. Thread nuevo sin memoria (sesion-nueva). La misma pregunta de la prueba 2 en otra conversación:
   el agente no sabía de qué cliente se hablaba y pidió el nombre.


Ejemplo de traza (sesion-2)

```
Usuario: "¿Cuánto gastó en total Lucía Fernández?"
  → El agente decide usar: buscar_cliente(nombre='Lucía Fernández')
  → La herramienta devuelve: {"coincidencias": [{"cliente_id": 101, "nombre": "Lucía Fernández", "ciudad": "Rosario"}]}
  → El agente decide usar: buscar_pedidos(cliente_id=101)
  → La herramienta devuelve: {"error": "Timeout temporal de la base de datos. Reintentá la misma consulta."}
  → El agente decide usar: buscar_pedidos(cliente_id=101)
  → La herramienta devuelve: {"cliente_id": 101, "pedidos": 2, "total": 16000, ...}
Respuesta: "Lucía Fernández gastó un total de $16.000 en sus 2 pedidos realizados."
```