## Comandos de Docker — PrivateWay

Todos los comandos deben ejecutarse desde la raíz del proyecto:

```bash
cd ~/Projects/PrivateWay
```

### 1. Construir los contenedores

Construir las imágenes e iniciar los servicios:

```bash
sudo docker compose -f compose.yaml -f compose.dev.yaml -f compose.vllm.yaml up -d --build
```

### 2. Iniciar los contenedores

**Primer arranque o después de ejecutar `down`** (requiere que las imágenes ya estén construidas):

```bash
sudo docker compose -f compose.yaml -f compose.dev.yaml -f compose.vllm.yaml up -d --no-build
```

**Reanudar los contenedores después de ejecutar `stop`:**

```bash
sudo docker compose -f compose.yaml -f compose.dev.yaml -f compose.vllm.yaml start
```

### 3. Apagar los contenedores

**Detener los servicios sin eliminar los contenedores:**

```bash
sudo docker compose -f compose.yaml -f compose.dev.yaml -f compose.vllm.yaml stop
```

**Detener y eliminar los contenedores y las redes creadas por Compose:**

```bash
sudo docker compose -f compose.yaml -f compose.dev.yaml -f compose.vllm.yaml down
```

**Detener y eliminar los contenedores, las redes y los volúmenes administrados por Compose:**

```bash
sudo docker compose -f compose.yaml -f compose.dev.yaml -f compose.vllm.yaml down -v
```

**Advertencia:** `down -v` puede eliminar datos persistentes almacenados en los volúmenes de Docker. Utilizar únicamente cuando se quiera reiniciar el entorno y descartar esos datos.

### 4. Ver los logs del sistema en tiempo real

**Frontend — Next.js:**

```bash
sudo docker compose -f compose.yaml -f compose.dev.yaml -f compose.vllm.yaml logs -f frontend
```

**Backend — FastAPI:**

```bash
sudo docker compose -f compose.yaml -f compose.dev.yaml -f compose.vllm.yaml logs -f backend
```

**Servidor proxy — Nginx:**

```bash
sudo docker compose -f compose.yaml -f compose.dev.yaml -f compose.vllm.yaml logs -f proxy
```

**Servidor SLM - vLLM**
```bash
sudo docker compose -f compose.yaml -f compose.dev.yaml -f compose.vllm.yaml logs -f vllm
```
**Todos los servicios (mostrando inicialmente las últimas 100 líneas):**

```bash
sudo docker compose -f compose.yaml -f compose.dev.yaml -f compose.vllm.yaml logs -f --tail=100
```

Para dejar de visualizar los logs, presionar `Ctrl + C`. Esto no detiene los contenedores.

### 5. Comprobar el estado de los contenedores

```bash
sudo docker compose -f compose.yaml -f compose.dev.yaml -f compose.vllm.yaml ps -a
```

Este comando muestra los contenedores del proyecto, su estado de ejecución y los puertos publicados.

### 6. Reiniciar los servicios

**Reiniciar todos los contenedores:**

```bash
sudo docker compose -f compose.yaml -f compose.dev.yaml -f compose.vllm.yaml restart
```

**Reiniciar únicamente un servicio:**

```bash
sudo docker compose -f compose.yaml -f compose.dev.yaml -f compose.vllm.yaml restart frontend
```

Se puede sustituir `frontend` por `backend` o `proxy`.
