categoria: validacion
# Cuerpo de la petición y modelos Pydantic

Para recibir datos en el cuerpo (body) de una petición POST o PUT se define una clase que hereda de BaseModel de Pydantic y se usa como tipo de un argumento de la función. FastAPI lee el JSON recibido, lo valida contra el modelo y entrega a la función un objeto ya validado.

Si el cuerpo no cumple con el modelo, por ejemplo porque falta un campo obligatorio o un valor tiene el tipo equivocado, FastAPI responde automáticamente con el código de estado 422 Unprocessable Entity y un detalle de los errores, sin ejecutar la función.

El parámetro response_model del decorador indica qué forma tiene la respuesta. FastAPI filtra la salida para devolver solo los campos de ese modelo, lo que sirve para no exponer datos sensibles como contraseñas. Con Field se agregan restricciones y descripciones a cada campo.
