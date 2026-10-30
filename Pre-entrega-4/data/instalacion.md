categoria: primeros-pasos
# Instalación y primer servidor

FastAPI se instala con pip. La forma recomendada es instalar el paquete con sus extras estándar: pip install "fastapi[standard]". Esto agrega Uvicorn, el servidor ASGI que ejecuta la aplicación, y la herramienta de línea de comandos de FastAPI.

Una aplicación mínima crea un objeto app = FastAPI() en el archivo main.py y define al menos una ruta. Para desarrollo se ejecuta con el comando fastapi dev main.py, que reinicia el servidor automáticamente cada vez que cambia el código. En producción se usa fastapi run main.py.

Por defecto el servidor escucha en el puerto 8000. Una de las ventajas de FastAPI es la documentación automática: al entrar a /docs se abre Swagger UI, una interfaz interactiva para probar cada endpoint, y en /redoc está la versión de ReDoc. Ambas se generan a partir del esquema OpenAPI que FastAPI construye solo, leyendo las rutas y los tipos de datos.
