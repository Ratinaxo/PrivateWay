# PrivateWay — Variables de entorno y reproducción local

Este documento explica la configuración del **laboratorio local** de PrivateWay: Next.js (BFF), FastAPI (gateway), Nginx, Keycloak y PostgreSQL de Keycloak.

> **Seguridad:** `.env` contiene secretos en texto plano. **Nunca se sube a Git, no se comparte por chat y no se incorpora a imágenes Docker.** Cada desarrollador debe generar sus propios secretos. La plantilla versionable es `.env.example` (sin valores secretos).
>
> El despliegue actual utiliza **HTTP local** y Keycloak en modo `start-dev`. No está preparado para producción ni para exponer sus puertos a la red pública.

## 1. Dónde se guardan y quién los utiliza

- **`.env` (raíz del proyecto):** configuración privada de la máquina. Docker Compose la lee para sustituir expresiones `${VARIABLE}` en `compose.yaml` y `compose.dev.yaml`. No se debe subir al repositorio.
- **`.env.model` (raíz del proyecto):** configuración privada obligatoria para el único flujo híbrido. Se crea al preparar el entorno del modelo y contiene credenciales locales de SLM/embeddings; no se sube al repositorio.
- **`.env.example` (raíz):** plantilla que se versiona. Los valores vacíos de los secretos son placehoders: el script de python los rellena al ejecutarse por primera vez.
- **`compose.yaml`:** inyecta las variables necesarias en los contenedores. Algunas URL e identificadores se fijan aquí y no requieren una entrada adicional en `.env`.
- **Volumen `keycloak_db_data`:** almacena el estado de Keycloak (realm, cuentas, roles, credenciales y configuración). **No forma parte de `.env` ni de Git.**

### Convenciones

- **Obligatoria:** Compose o el servicio correspondiente la requiere para arrancar correctamente.
- **Opcional:** su ausencia o valor vacío es válido en el laboratorio actual.
- **Secreto:** no debe publicarse. Generarlo con un generador criptográficamente seguro (basicamente el script de python), distinto para cada variable y cada equipo.

## 2. Variables del gateway y Docker

| Variable | Tipo | Uso |
|---|---|---|
| `PRIVATEWAY_GATEWAY_TOKEN` | **Secreto obligatorio** | Token compartido **solo entre el BFF Next.js y FastAPI**. Compose lo inyecta como `GATEWAY_CLIENT_TOKEN` en frontend y `GATEWAY_CLIENT_TOKENS` en backend. Debe tener al menos 24 caracteres. |
| `GATEWAY_ROUTES_JSON` | Opcional al iniciar | JSON con aliases visibles y correspondencia `{ "proveedor": ..., "modelo_externo": ... }`. Vacío significa que no hay chat habilitado; la API responde explícitamente que no hay proveedor disponible. |
| `GATEWAY_PROVIDERS_JSON` | Opcional al iniciar | JSON con adaptadores reales (`openai`, `anthropic`, `gemini` o `compatible_chat`). Vacío significa que no hay adaptadores disponibles. Los dobles simulados/espías se limitan a pruebas y evaluación local. |
| `PRIVATEWAY_HTTP_PORT` | Opcional | Puerto de Nginx en `127.0.0.1`; normalmente `8080`. También se usa para los URI de retorno OIDC al inicializar Keycloak. |
| `PRIVATEWAY_DEV_FRONTEND_PORT` | Opcional | Puerto directo de Next.js en modo desarrollo; normalmente `3000`. Para **probar el login**, usar el acceso por Nginx (`:8080`), coherente con `NEXTAUTH_URL`. |
| `GATEWAY_ALLOWED_PROVIDER_HOSTS` | Opcional | Lista separada por comas de hosts (sin esquema ni puerto) autorizados para adaptadores `compatible_chat` HTTPS. Debe coincidir con el host de `base_url`. |
| `OPENAI_API_KEY` | Secreto opcional | Clave de OpenAI; necesaria solo al configurar y probar ese proveedor. |
| `ANTHROPIC_API_KEY` | Secreto opcional | Clave de Anthropic, si se utiliza su adaptador. |
| `GEMINI_API_KEY` | Secreto opcional | Clave de Gemini, si se utiliza su adaptador. |
| `PRIVATEWAY_COMPATIBLE_API_KEY` | Secreto opcional | Nombre exacto de la variable de clave dedicada para `compatible_chat`; `api_key_env` debe usar `PRIVATEWAY_COMPATIBLE_API_KEY`. No se aceptan otros nombres en ese namespace ni se reutilizan claves nativas. |
| `PRIVATEWAY_DB_PASSWORD` | **Secreto obligatorio** | Contraseña de PostgreSQL de conversaciones, independiente de `KEYCLOAK_DB_PASSWORD`. No cambiarla después de inicializar el volumen sin actualizar el rol de PostgreSQL. |
| `PRIVATEWAY_HISTORY_TOKEN` | **Secreto obligatorio** | Token BFF → gateway, exclusivamente para listar/guardar/eliminar conversaciones, diferente del de chat y auditoría. |
| `PRIVATEWAY_CONVERSATION_KEY` | **Secreto obligatorio** | Clave Fernet para cifrar las conversaciones en PostgreSQL. Si se pierde, no se pueden recuperar los chats anteriores. |
| `PRIVATEWAY_AUDIT_READ_TOKEN` | **Secreto obligatorio** | Token de lectura de auditoría para el BFF; distinto del token de chat e historial. |
| `PRIVATEWAY_AUDIT_CONTENT_KEY` | **Secreto obligatorio** | Clave Fernet para guardar y recuperar las vistas sensibles «antes/después». Si se pierde, las vistas existentes no serán legibles. |
| `PRIVATEWAY_SLM_TOKEN` | **Secreto obligatorio en `.env.model`** | Credencial local entre el gateway y vLLM. No se envía a proveedores externos. |
| `PRIVATEWAY_EMBEDDINGS_TOKEN` | **Secreto obligatorio en `.env.model`** | Credencial local entre el gateway y el servicio de embeddings. |
| `PRIVATEWAY_E5_REVISION` | Obligatoria en `.env.model` | Revisión local del modelo de embeddings, generada durante la preparación de modelos. |
| `PRIVATEWAY_SLM_MODEL_DIR`, `PRIVATEWAY_SLM_QUANTIZATION`, `PRIVATEWAY_SLM_CONTEXT`, `PRIVATEWAY_GPU_MEMORY` | Opcionales en `.env.model` | Ajustes locales de vLLM; los valores predeterminados se definen en Compose. |

Configuración inicial sin proveedores externos ni aliases:

```dotenv
GATEWAY_ROUTES_JSON={}
GATEWAY_PROVIDERS_JSON={}
GATEWAY_ALLOWED_PROVIDER_HOSTS=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
```

Para habilitar el chat, declara un adaptador y una ruta en `.env`. El valor `proveedor` de
cualquier ruta debe coincidir con una clave de `GATEWAY_PROVIDERS_JSON`; `modelo_externo` es
el identificador habilitado por la cuenta del proveedor. Por ejemplo, sustituye los
placeholders y guarda la clave real únicamente en la variable nombrada por `api_key_env`:

```dotenv
GATEWAY_PROVIDERS_JSON={"mi-openai":{"tipo":"openai","api_key_env":"OPENAI_API_KEY"}}
GATEWAY_ROUTES_JSON={"mi-alias":{"proveedor":"mi-openai","modelo_externo":"<id-modelo-configurado>"}}
OPENAI_API_KEY=
```

Para Anthropic o Gemini cambia `tipo` y `api_key_env` por `anthropic`/`ANTHROPIC_API_KEY` o
`gemini`/`GEMINI_API_KEY`. Para un servicio OpenAI-compatible, usa HTTPS, un host exacto en
`GATEWAY_ALLOWED_PROVIDER_HOSTS` y una clave dedicada:

```dotenv
GATEWAY_PROVIDERS_JSON={"mi-compatible":{"tipo":"compatible_chat","base_url":"https://<host-autorizado>/v1","api_key_env":"PRIVATEWAY_COMPATIBLE_API_KEY"}}
GATEWAY_ROUTES_JSON={"mi-alias":{"proveedor":"mi-compatible","modelo_externo":"<id-modelo-configurado>"}}
GATEWAY_ALLOWED_PROVIDER_HOSTS=<host-autorizado>
PRIVATEWAY_COMPATIBLE_API_KEY=
```

Puedes definir varios adaptadores y aliases en los dos JSON. No incluyas claves ni
identificadores sensibles en el catálogo. El runtime normal no ofrece un proveedor simulado:
sin una ruta real habilitada la API responde con un error explícito.

## 3. Variables de autenticación y Keycloak (La mayoría se generan con el script de python)

| Variable | Tipo | Uso |
|---|---|---|
| `NEXTAUTH_SECRET` | **Secreto obligatorio** | Secreto de sesión de NextAuth en el servidor Next.js; mínimo 32 caracteres según el código actual. |
| `PRIVATEWAY_OIDC_CLIENT_SECRET` | **Secreto obligatorio** | Contraseña del cliente OIDC confidencial `privateway-web`. Debe coincidir con el valor configurado en Keycloak por `keycloak-init`. |
| `PRIVATEWAY_KEYCLOAK_ADMIN_CLIENT_SECRET` | **Secreto obligatorio** | Contraseña del cliente de servicio `privateway-admin-api`, utilizado **desde el servidor Next.js** para la administración de usuarios. Nunca debe exponerse en el navegador. |
| `KEYCLOAK_DB_PASSWORD` | **Secreto obligatorio** | Contraseña de PostgreSQL **de Keycloak**, compartida entre los servicios `keycloak` y `keycloak-db`. |
| `KEYCLOAK_BOOTSTRAP_ADMIN_USERNAME` | Nombre de usuario | Administrador inicial del realm `master` de Keycloak. Predeterminado: `kc-bootstrap`. |
| `KEYCLOAK_BOOTSTRAP_ADMIN_PASSWORD` | **Secreto obligatorio** | Contraseña inicial del superadministrador `master`, usada para configurar Keycloak. **No es la contraseña de `pwadmin`.** |
| `PRIVATEWAY_FIRST_ADMIN_USERNAME` | Nombre de usuario | Usuario administrador inicial **del realm `privateway`**. Predeterminado: `pwadmin`. |
| `PRIVATEWAY_FIRST_ADMIN_PASSWORD` | **Secreto obligatorio** | Contraseña **temporal** de la primera cuenta `pwadmin`, usada únicamente si esa cuenta todavía no existe. Keycloak solicita cambiarla en el primer acceso. |

El `compose.yaml` que hemos integrado define adicionalmente estas variables **dentro del contenedor frontend** (no es necesario repetirlas en `.env` raíz):

| Variable en el contenedor | Valor de laboratorio |
|---|---|
| `NEXTAUTH_URL` | `http://127.0.0.1:8080` (el puerto se obtiene de `PRIVATEWAY_HTTP_PORT`) |
| `PRIVATEWAY_OIDC_ISSUER` | `http://auth.privateway.test:8081/realms/privateway` |
| `PRIVATEWAY_OIDC_CLIENT_ID` | `privateway-web` |
| `PRIVATEWAY_KEYCLOAK_INTERNAL_URL` | `http://keycloak:8081` |
| `PRIVATEWAY_KEYCLOAK_REALM` | `privateway` |
| `PRIVATEWAY_KEYCLOAK_ADMIN_CLIENT_ID` | `privateway-admin-api` |
| `GATEWAY_INTERNAL_URL` | `http://backend:8000` |

La configuración de `NEXTAUTH_URL`, `issuer` y callback tiene que ser coherente. En este laboratorio **no se debe sustituir arbitrariamente** el nombre `auth.privateway.test`, el puerto `8081` o la URL pública sin modificar también Compose, la resolución local y la configuración del cliente OIDC.

## 4. Primer arranque para otros desarrolladores (Fish) (Comprueba los comandos para windows, son casi los mismos)

Se parte de un clon limpio del repositorio, con los puertos locales `8080`, `8081` y `3000` disponibles.

### 4.1 Clonar y crear su `.env`

```fish
# Sustituir la URL por la URL real del repositorio.
git clone <URL_DEL_REPOSITORIO> PrivateWay
cd PrivateWay
cp .env.example .env
chmod 600 .env
```

Si el equipo utiliza un archivo llamado `.env-example` en lugar de `.env.example`, copiar ese archivo a `.env`.

### 4.2 Configurar resolución de Keycloak

Añadir **una sola vez** esta línea en `/etc/hosts` (por ejemplo, mediante `sudoedit /etc/hosts`):

```text
127.0.0.1 auth.privateway.test
```

Verificar:

```fish
getent hosts auth.privateway.test
```

### 4.3 Generar los secretos locales

Primero, crear el token del gateway (si `PRIVATEWAY_GATEWAY_TOKEN` está vacío). En Fish:

```fish
openssl rand -hex 32
```

Copiar el resultado **solo a** `PRIVATEWAY_GATEWAY_TOKEN=` dentro del archivo `.env` local.

Después, generar automáticamente los seis secretos de autenticación vacíos:

```fish
python3 Servidor/configurar-entorno.py
```

El script rellena **únicamente las variables de autenticación que falten o estén vacías**, agrega los nombres de administrador cuando faltan y mantiene los demás valores. No genera `PRIVATEWAY_GATEWAY_TOKEN` ni `PRIVATEWAY_DB_PASSWORD`. También restringe `.env` a permisos `0600`. Como el script modifica valores de Linux, puede que tengas que adaptarlo para Windows.

> **Alternativa manual:** ejecutar `openssl rand -hex 32` una vez **por cada secreto**, poner cada resultado en la variable correspondiente y omitir el script. No reutilizar el mismo valor entre variables ni entre desarrolladores.

### 4.4 Validar y arrancar

```fish
docker compose --env-file .env --env-file .env.model -f compose.yaml -f compose.dev.yaml config --quiet
docker compose --env-file .env --env-file .env.model -f compose.yaml -f compose.dev.yaml up -d --build
docker compose --env-file .env --env-file .env.model -f compose.yaml -f compose.dev.yaml ps -a
```

Antes de este paso, completa la preparación de SLM, embeddings y corpus descrita en
`README-experimentos.md`; el stack requiere GPU y los modelos locales.

`keycloak-init` **debe terminar en `Exited (0)`**. El resto de los servicios debe estar iniciado; el frontend, backend y PostgreSQL de Keycloak deberían alcanzar  su estado saludable. Todos los contenedores deberían estar en ejecución menos `keycloak-init`, este contenedor unicamente inicializa los valores para keycloak y muere.

Comprobar OIDC:

```fish
curl -fsS http://auth.privateway.test:8081/realms/privateway/.well-known/openid-configuration
```

El JSON debe publicar como `issuer`:

```text
http://auth.privateway.test:8081/realms/privateway
```

### 4.5 Primer usuario y prueba de roles

- Acceder a `http://127.0.0.1:8080/login`.
- Iniciar sesión como `pwadmin`, con la contraseña temporal guardada en el `.env` como `PRIVATEWAY_FIRST_ADMIN_PASSWORD`.
- Cambiar la contraseña cuando Keycloak lo solicite.
- Abrir `http://127.0.0.1:8080/admin` y crear un usuario normal.
- Verificar que ese usuario puede entrar al chat pero no administrar cuentas.
- Comprobar que una petición sin sesión a `http://127.0.0.1:8080/api/admin/usuarios` devuelve `401`.

**Importante:** la contraseña temporal guardada en `.env` deja de ser la contraseña efectiva después de cambiarla en Keycloak; no se actualiza en ese archivo.

## 5. Qué se comparte y qué no se replica con Git

**Versionar:** código `Backend/`, `Frontend/`, `Model/src/` y `Servidor/`; Compose, `.env.example`, pruebas y archivos de dependencias bloqueadas. Los modelos descargados y resultados locales quedan fuera de Git.

**No versionar:** `.env` reales (incluidos los de subdirectorios), credenciales, tokens, claves privadas, bases de datos, archivos de auditoría, backups con secretos, volúmenes Docker, `node_modules/`, `.next/`, entornos Python virtuales ni respaldos locales de carpetas.

El script `Servidor/keycloak/bootstrap.sh` crea el realm `privateway`, los roles `privateway-user` y `privateway-admin`, los clientes OIDC y `pwadmin` **si todavía no existen**. Las cuentas adicionales que se hayan creado durante la instalación **no estarán** en la del resto de desarrolladores: viven en PostgreSQL de Keycloak, dentro del volumen Docker `keycloak_db_data`.

Si ente desarrolladores necesitan el **mismo entorno de cuentas**, eso requiere una estrategia separada (por ejemplo, servidor de identidad compartido o copia/restauración controlada), nunca subir el volumen o la base de datos a Git.

## 6. Persistencia y rotación

- `docker compose stop` detiene los servicios sin eliminar contenedores.
- `docker compose down` elimina contenedores y redes, **pero conserva los volúmenes nombrados**.
- **`docker compose down -v` elimina también `keycloak_db_data` y puede borrar todas las cuentas locales. Evitarlo si no quieres crear las cuentas de nuevo.**
- Cambiar `KEYCLOAK_DB_PASSWORD` solo en `.env` **no rota** la contraseña del usuario existente en PostgreSQL.
- Cambiar `KEYCLOAK_BOOTSTRAP_ADMIN_PASSWORD` o `PRIVATEWAY_FIRST_ADMIN_PASSWORD` en `.env` **no actualiza** contraseñas de cuentas Keycloak ya creadas.
- El inicializador sí sincroniza los secretos configurados de los clientes `privateway-web` y `privateway-admin-api` cuando se ejecuta.
- Para recuperar el acceso de `pwadmin`, utilizar las herramientas administrativas de Keycloak; no borrar el volumen.

## 7. Seguridad de Git y comprobaciones antes del commit

En la raíz, asegurarse de que `.gitignore` incluya como mínimo:

```gitignore
.env
.env.*
!.env.example
**/.env
**/.env.*
!**/.env.example
**/node_modules/
**/.next/
**/.venv/
```

Revisar antes de publicar:

```fish
git status --short
git ls-files .env Frontend/.env
# Si alguna ruta aparece aquí, el secreto ya está bajo seguimiento y debe retirarse del índice.
git diff --cached --name-only
git diff --cached --check
```

Si `.env` está versionado, retirarlo **del índice sin borrar la copia local** mediante `git rm --cached .env`, revisar el historial y **rotar** las credenciales que hayan sido expuestas. Eliminarlo en un commit nuevo no borra sus valores de commits anteriores.

No ejecutar `docker compose config` sin `--quiet` al compartir logs: puede mostrar los valores de variables secretas resueltas.

## 8. Limitaciones vigentes

- El login OIDC y el panel de administración se han comprobado manualmente en la instalación original; los demás desarrolladores deben repetir su propia prueba.
- El flujo del gateway combina REGEX/Presidio y SLM/RAG en paralelo. REGEX solo reconoce las categorías implementadas y el SLM depende de los modelos locales preparados; la detección no cubre todos los datos personales o semánticos.
- Las claves API de LLM son opcionales para probar la autenticación y la gestión de cuentas.
- Para producción: utilizar HTTPS, secretos gestionados, Keycloak fuera de `start-dev`, MFA, copias de seguridad, hostname corporativo y revisión de permisos administrativos.
