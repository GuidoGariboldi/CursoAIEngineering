categoria: middleware
# Middleware y CORS

Un middleware es una función que se ejecuta en cada petición antes de llegar al endpoint y en cada respuesta antes de volver al cliente. Se define con el decorador @app.middleware("http") y sirve, por ejemplo, para medir el tiempo de respuesta o agregar encabezados.

CORS (Cross-Origin Resource Sharing) es el mecanismo que permite que un frontend alojado en otro origen, como una aplicación React en localhost:3000, llame a la API. Por seguridad, el navegador bloquea esas llamadas salvo que el servidor las autorice.

En FastAPI se habilita con CORSMiddleware: app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_methods=["*"], allow_headers=["*"]). En allow_origins conviene listar solo los orígenes permitidos en lugar de usar un asterisco, sobre todo si allow_credentials está activado.
