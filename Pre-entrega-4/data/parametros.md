categoria: rutas
# Parámetros de ruta y de consulta

Los parámetros de ruta se escriben entre llaves en la URL, por ejemplo /items/{item_id}, y se reciben como argumentos de la función con el mismo nombre. Si se anota el tipo, como item_id: int, FastAPI convierte el valor automáticamente y rechaza la petición si no es un número.

Los argumentos de la función que no forman parte de la ruta se interpretan como parámetros de consulta (query parameters), los que van después del signo de pregunta en la URL, como ?skip=0&limit=10. Si tienen un valor por defecto son opcionales; si no, son obligatorios.

Para agregar validaciones se usan Query y Path. Por ejemplo, Query(max_length=50) limita el largo de un texto, y Path(ge=1) exige que un número sea mayor o igual a 1. Estas restricciones también aparecen en la documentación automática.
