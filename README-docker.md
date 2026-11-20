# Docker Compose de PrivateWay

Ejecuta los comandos desde la raíz del repositorio. El laboratorio local expone un único
flujo híbrido; no está preparado para producción.

- `compose.yaml`: servicios del flujo híbrido, incluidos frontend, gateway, Nginx, Keycloak,
  PostgreSQL, vLLM y embeddings.
- `compose.dev.yaml`: recarga local de código para el frontend.
- `compose.hybrid.yaml`: overlay de compatibilidad para comandos anteriores; ya no es necesario.

## Flujo híbrido único

Prepara `.env.model`, los pesos y el corpus como describe
[README-experimentos.md](README-experimentos.md). Luego inicia el stack:

```bash
docker compose --env-file .env --env-file .env.model \
  -f compose.yaml -f compose.dev.yaml up -d --build
docker compose --env-file .env --env-file .env.model \
  -f compose.yaml -f compose.dev.yaml ps
docker compose --env-file .env --env-file .env.model \
  -f compose.yaml -f compose.dev.yaml logs -f --tail=100
```

Para cargar el corpus:

```bash
docker compose --env-file .env --env-file .env.model \
  -f compose.yaml -f compose.dev.yaml \
  run --rm --no-deps backend python -m privateway_model.rag /corpus/manifest.json
```

Los logs de los servicios de modelo se consultan con la misma lista de archivos:

```bash
docker compose --env-file .env --env-file .env.model \
  -f compose.yaml -f compose.dev.yaml logs -f vllm embeddings
```

Detén el stack con `stop` o `down`. `down -v` elimina también las bases de datos persistentes.
