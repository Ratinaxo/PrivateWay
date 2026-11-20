## Comandos de Docker — PrivateWay

Todos los comandos deben ejecutarse desde la raíz del proyecto:

```bash
cd ~/Projects/PrivateWay
```

### 1. Construir los contenedores

Construir las imágenes e iniciar los servicios:

```bash
sudo docker compose -f compose.yaml -f compose.dev.yaml up -d --build
```

### 2. Iniciar los contenedores

**Primer arranque o después de ejecutar `down`** (requiere que las imágenes ya estén construidas):

```bash
sudo docker compose -f compose.yaml -f compose.dev.yaml up -d --no-build
```

**Reanudar los contenedores después de ejecutar `stop`:**

```bash
sudo docker compose -f compose.yaml -f compose.dev.yaml start
```

### 3. Apagar los contenedores

**Detener los servicios sin eliminar los contenedores:**

```bash
sudo docker compose -f compose.yaml -f compose.dev.yaml stop
```

**Detener y eliminar los contenedores y las redes creadas por Compose:**

```bash
sudo docker compose -f compose.yaml -f compose.dev.yaml down
```

**Detener y eliminar los contenedores, las redes y los volúmenes administrados por Compose:**

```bash
sudo docker compose -f compose.yaml -f compose.dev.yaml down -v
```

**Advertencia:** `down -v` puede eliminar datos persistentes almacenados en los volúmenes de Docker. Utilizar únicamente cuando se quiera reiniciar el entorno y descartar esos datos.

### 4. Ver los logs del sistema en tiempo real

**Frontend — Next.js:**

```bash
sudo docker compose -f compose.yaml -f compose.dev.yaml logs -f frontend
```

**Backend — FastAPI:**

```bash
sudo docker compose -f compose.yaml -f compose.dev.yaml logs -f backend
```

**Servidor proxy — Nginx:**

```bash
sudo docker compose -f compose.yaml -f compose.dev.yaml logs -f proxy
```

**Servidor SLM - vLLM**
```bash
sudo docker compose -f compose.yaml -f compose.dev.yaml -f compose.hybrid.yaml logs -f vllm
```
**Todos los servicios (mostrando inicialmente las últimas 100 líneas):**

```bash
sudo docker compose -f compose.yaml -f compose.dev.yaml logs -f --tail=100
```

Para dejar de visualizar los logs, presionar `Ctrl + C`. Esto no detiene los contenedores.

### 5. Comprobar el estado de los contenedores

```bash
sudo docker compose -f compose.yaml -f compose.dev.yaml ps -a
```

Este comando muestra los contenedores del proyecto, su estado de ejecución y los puertos publicados.

### 6. Reiniciar los servicios

**Reiniciar todos los contenedores:**

```bash
sudo docker compose -f compose.yaml -f compose.dev.yaml restart
```

**Reiniciar únicamente un servicio:**

```bash
sudo docker compose -f compose.yaml -f compose.dev.yaml restart frontend
```

Se puede sustituir `frontend` por `backend` o `proxy`.

### 7. Contenedores del piloto híbrido (vLLM + RAG)

El piloto agrega los servicios `slm`, `embeddings`, `postgres` y un `backend` y `proxy`
aislados de los servicios principales. Para iniciarlo, primero preparar `.env.pilot`, los
modelos y el corpus según `README-pilot.md`. Luego, desde la raíz del proyecto:

**Construir las imágenes del piloto:**

```bash
sudo docker compose --env-file .env --env-file .env.pilot -f compose.pilot.yaml build
```

**Iniciar los modelos y la base de datos:**

```bash
sudo docker compose --env-file .env --env-file .env.pilot -f compose.pilot.yaml up -d slm embeddings postgres
```

**Cargar el corpus legislativo en PostgreSQL/pgvector:**

```bash
sudo docker compose --env-file .env --env-file .env.pilot -f compose.pilot.yaml run --rm --no-deps backend python -m privateway_model.rag /corpus/manifest.json
```

**Iniciar el gateway y el proxy del piloto:**

```bash
sudo docker compose --env-file .env --env-file .env.pilot -f compose.pilot.yaml -f compose.lab.yaml up -d backend proxy
```

El gateway del piloto queda disponible en `http://127.0.0.1:8082`. Para conectar la web
autenticada de desarrollo al gateway, generar una vez las credenciales E2E y aplicar los
overrides indicados. Configura primero un proveedor real y sus aliases en `.env`; el entorno
no habilita un proveedor simulado. Se requieren también las credenciales de desarrollo:

```bash
python3 Model/scripts/prepare_web_pilot.py
sudo docker compose --env-file .env --env-file .env.pilot --env-file .env.web-pilot -f compose.pilot.yaml -f compose.lab.yaml -f compose.pilot.web.yaml up -d --build backend proxy
sudo docker compose --env-file .env --env-file .env.web-pilot -f compose.yaml -f compose.dev.yaml -f compose.web-pilot.yaml up -d --build frontend proxy
```

La web queda disponible en `http://127.0.0.1:8080`; inicia sesión y selecciona un alias real
del catálogo. Usa solo mensajes sintéticos cuando el alias envíe consultas fuera del equipo.
Para volver a conectar la web al gateway
principal, ejecutar el comando de recreación del frontend y proxy descrito en `README-pilot.md`.

**Ver el estado de los contenedores del piloto:**

```bash
sudo docker compose --env-file .env --env-file .env.pilot -f compose.pilot.yaml ps -a
```

**Ver logs de un servicio del piloto:**

```bash
sudo docker compose --env-file .env --env-file .env.pilot -f compose.pilot.yaml logs -f backend
```

Se puede sustituir `backend` por `proxy`, `slm`, `embeddings` o `postgres`.

**Detener los contenedores del piloto conservando sus datos:**

```bash
sudo docker compose --env-file .env --env-file .env.pilot -f compose.pilot.yaml stop
```

**Detener y eliminar los contenedores y redes del piloto:**

```bash
sudo docker compose --env-file .env --env-file .env.pilot -f compose.pilot.yaml down
```

No agregar `-v` al comando `down`: los volúmenes contienen la base de datos, el historial y
la auditoría del piloto.

### 8. Conectar el stack principal al pipeline híbrido

Este overlay mantiene el frontend, Keycloak, el gateway y PostgreSQL del stack principal,
y conecta el backend a vLLM, embeddings y RAG. Requiere GPU NVIDIA, `.env.pilot`, los modelos
E5 descargados y el corpus preparado como se indica en `README-pilot.md`. El catálogo y los
adaptadores se leen de `GATEWAY_ROUTES_JSON` y `GATEWAY_PROVIDERS_JSON`; no hay proveedor
simulado en el runtime. Sin rutas/adaptadores reales, la API responde con el error explícito
de proveedor no disponible.

**Validar el Compose y construir el backend y embeddings:**

```bash
sudo docker compose --env-file .env --env-file .env.pilot -f compose.yaml -f compose.dev.yaml -f compose.hybrid.yaml config --quiet
sudo docker compose --env-file .env --env-file .env.pilot -f compose.yaml -f compose.dev.yaml -f compose.hybrid.yaml build backend embeddings
```

El overlay requiere ambos archivos en ese orden: `PRIVATEWAY_SLM_TOKEN`,
`PRIVATEWAY_EMBEDDINGS_TOKEN`, `PRIVATEWAY_E5_REVISION` y los parámetros del modelo salen de
`.env.pilot`; las rutas, adaptadores, claves API reales y credenciales de PostgreSQL/gateway
principal salen de `.env`.

Configura los aliases y adaptadores en `.env`, sin poner claves API dentro del JSON. Por
ejemplo, reemplaza los placeholders con el alias y el id de modelo habilitado en tu cuenta:

```dotenv
GATEWAY_PROVIDERS_JSON={"mi-openai":{"tipo":"openai","api_key_env":"OPENAI_API_KEY"}}
GATEWAY_ROUTES_JSON={"mi-alias":{"proveedor":"mi-openai","modelo_externo":"<id-modelo>"}}
```

Para Anthropic o Gemini cambia `tipo` y `api_key_env` por `anthropic`/`ANTHROPIC_API_KEY` o
`gemini`/`GEMINI_API_KEY`. Guarda el secreto solo en la variable correspondiente de `.env`.
El frontend muestra el nombre de alias (`mi-alias`) en su catálogo. Si no hay una ruta real
disponible, el gateway inicia sin habilitar chat y responde con un error explícito.

Para un endpoint compatible con Chat Completions, define un `base_url` HTTPS y permite su host
exacto en `GATEWAY_ALLOWED_PROVIDER_HOSTS`; usa la variable dedicada para la clave:

```dotenv
GATEWAY_PROVIDERS_JSON={"mi-compatible":{"tipo":"compatible_chat","base_url":"https://<host-autorizado>/v1","api_key_env":"PRIVATEWAY_COMPATIBLE_API_KEY"}}
GATEWAY_ROUTES_JSON={"mi-alias":{"proveedor":"mi-compatible","modelo_externo":"<id-modelo-configurado>"}}
GATEWAY_ALLOWED_PROVIDER_HOSTS=<host-autorizado>
PRIVATEWAY_COMPATIBLE_API_KEY=
```

El valor de allowlist es el hostname sin esquema ni puerto. No reutilices `OPENAI_API_KEY`,
`ANTHROPIC_API_KEY` ni `GEMINI_API_KEY` para `compatible_chat`.

**Iniciar vLLM, embeddings y PostgreSQL del stack principal:**

```bash
sudo docker compose --env-file .env --env-file .env.pilot -f compose.yaml -f compose.dev.yaml -f compose.hybrid.yaml up -d vllm embeddings postgres
```

**Indexar el corpus en la base principal:**

```bash
sudo docker compose --env-file .env --env-file .env.pilot -f compose.yaml -f compose.dev.yaml -f compose.hybrid.yaml run --rm --no-deps backend python -m privateway_model.rag /corpus/manifest.json
```

La ingesta crea o reutiliza el esquema RAG, añade una versión identificada por hash y activa
esa versión dentro de una transacción. No elimina tablas, filas de versiones anteriores ni
volúmenes Docker.

**Activar el pipeline híbrido en el gateway:**

```bash
sudo docker compose --env-file .env --env-file .env.pilot -f compose.yaml -f compose.dev.yaml -f compose.hybrid.yaml up -d --build backend
```

El frontend sigue usando el mismo BFF y el mismo inicio de sesión. Selecciona un alias real
para recorrer el análisis REGEX + SLM/RAG; usa mensajes sintéticos al probar un proveedor
externo. vLLM se utiliza solo para la etapa SLM/RAG y no es el proveedor de respuesta del chat.
Comprueba el estado con:

```bash
sudo docker compose --env-file .env --env-file .env.pilot -f compose.yaml -f compose.dev.yaml -f compose.hybrid.yaml exec -T backend python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/ready',timeout=5).read().decode())"
```

Para inspeccionar los logs, sustituye `backend` por `vllm` o `embeddings` en el comando
de logs de la sección anterior, que para este flujo también incluye `compose.hybrid.yaml`.
El contexto y el uso de GPU de vLLM se ajustan con `PRIVATEWAY_SLM_CONTEXT` y
`PRIVATEWAY_GPU_MEMORY` en `.env.pilot`; el valor de contexto se comparte con el gateway.
