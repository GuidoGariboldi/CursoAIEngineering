categoria: arquitectura
# Inyección de dependencias

FastAPI tiene un sistema de inyección de dependencias basado en Depends. Una dependencia es una función que FastAPI ejecuta antes del endpoint; su resultado se pasa como argumento. Se declara así: def listar(db = Depends(obtener_sesion)).

Las dependencias sirven para reutilizar lógica común: abrir una conexión a la base de datos, leer el usuario autenticado o validar parámetros de paginación. Una dependencia puede, a su vez, depender de otras, y FastAPI resuelve toda la cadena.

Si la dependencia usa yield en lugar de return, el código que está después del yield se ejecuta cuando termina la petición. Es la forma habitual de cerrar la sesión de la base de datos aunque haya ocurrido un error. También se pueden aplicar dependencias a un router completo con el parámetro dependencies, para que se ejecuten en todos sus endpoints.
