# Docker Compose de PrivateWay

Ejecuta los comandos desde la raíz del repositorio. Hay tres archivos Compose en total:

- `compose.yaml`: servicios del flujo principal, incluidos frontend, gateway, Nginx, Keycloak
  y PostgreSQL.
- `compose.dev.yaml`: recarga local de código para el frontend.
- `compose.hybrid.yaml`: añade vLLM, embeddings y configuración SLM/RAG al mismo flujo.

## Flujo principal con REGEX

```bash
docker compose -f compose.yaml -f compose.dev.yaml up -d --build
docker compose -f compose.yaml -f compose.dev.yaml ps
docker compose -f compose.yaml -f compose.dev.yaml logs -f --tail=100
docker compose -f compose.yaml -f compose.dev.yaml stop
```

## Flujo híbrido con SLM/RAG

Primero prepara `.env.model`, los pesos y el corpus como describe
[README-experimentos.md](README-experimentos.md). Luego inicia el mismo stack principal con
el override híbrido:

```bash
docker compose --env-file .env --env-file .env.model \
  -f compose.yaml -f compose.dev.yaml -f compose.hybrid.yaml up -d --build
```

Para cargar el corpus:

```bash
docker compose --env-file .env --env-file .env.model \
  -f compose.yaml -f compose.dev.yaml -f compose.hybrid.yaml \
  run --rm --no-deps backend python -m privateway_model.rag /corpus/manifest.json
```

Los logs de los servicios de modelo se consultan con la misma lista de archivos:

```bash
docker compose --env-file .env --env-file .env.model \
  -f compose.yaml -f compose.dev.yaml -f compose.hybrid.yaml logs -f vllm embeddings
```

Detén el stack con `stop` o `down`. No uses `down -v` salvo que quieras borrar también las
bases de datos persistentes.
