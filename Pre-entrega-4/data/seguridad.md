categoria: seguridad
# Seguridad y autenticación

FastAPI incluye utilidades para implementar OAuth2. La clase OAuth2PasswordBearer define el esquema de autenticación con token: recibe el parámetro tokenUrl, que es la ruta donde el cliente envía usuario y contraseña para obtener el token. Usada como dependencia, extrae el token del encabezado Authorization: Bearer.

Si la petición no trae el token, FastAPI responde con el código 401 Unauthorized. El token suele ser un JWT firmado que contiene el identificador del usuario y una fecha de vencimiento.

Las contraseñas nunca se guardan en texto plano: se almacena un hash generado con un algoritmo seguro como bcrypt o Argon2. Al iniciar sesión se compara el hash de la contraseña ingresada con el guardado. Una dependencia como obtener_usuario_actual combina la lectura del token con la búsqueda del usuario y se reutiliza en todos los endpoints protegidos.
