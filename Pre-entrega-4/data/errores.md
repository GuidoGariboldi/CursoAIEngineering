categoria: errores
# Manejo de errores

Para devolver un error al cliente se lanza una HTTPException con un status_code y un detail. Por ejemplo, raise HTTPException(status_code=404, detail="Producto no encontrado") corta la ejecución del endpoint y responde con ese código y un JSON que contiene el mensaje personalizado.

El campo detail puede ser un texto, una lista o un diccionario. También se pueden agregar encabezados (headers) a la respuesta de error, algo útil en errores de autenticación.

Para cambiar cómo se responde ante cierto tipo de error se registra un manejador con el decorador @app.exception_handler. Así se puede capturar una excepción propia y convertirla en una respuesta con el formato que use la API. El mismo mecanismo permite personalizar la respuesta de RequestValidationError, que es la excepción que FastAPI lanza cuando los datos recibidos no pasan la validación.
