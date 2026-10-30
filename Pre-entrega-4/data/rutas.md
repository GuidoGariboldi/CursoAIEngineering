categoria: rutas
# Rutas y operaciones

En FastAPI, cada endpoint se define con un decorador que indica el método HTTP y la ruta: @app.get, @app.post, @app.put, @app.patch y @app.delete. La función que está debajo del decorador se llama path operation function y su valor de retorno se convierte automáticamente a JSON.

Las funciones pueden declararse con def o con async def. Conviene usar async def cuando adentro se usan librerías asíncronas, por ejemplo un cliente HTTP o un driver de base de datos asíncrono, porque así el servidor puede atender otras peticiones mientras espera.

Cuando la aplicación crece, las rutas se organizan en módulos con APIRouter. Cada router agrupa endpoints relacionados y se incorpora a la aplicación principal con app.include_router. Al incluirlo se puede definir un prefix, como /usuarios, y una lista de tags, que agrupan los endpoints en la documentación de Swagger.
