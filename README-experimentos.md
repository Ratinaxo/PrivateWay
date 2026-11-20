# Reproducción y evaluación

La reproducción usa el flujo principal de PrivateWay. El modo normal protege las consultas
con REGEX. El modo híbrido añade SLM, embeddings y recuperación RAG al mismo gateway; no hay
un segundo stack de servidor.

## Preparar el modelo

Desde la raíz del repositorio, configura primero las credenciales locales del sistema y del
modelo. Los archivos `.env` y `.env.model` contienen secretos locales e ignorados por Git.

```bash
python3 Servidor/configurar-entorno.py
uv sync --project Backend --dev
uv run --project Backend python Model/scripts/setup_model_env.py
uv run --project Backend python Model/scripts/download_models.py
uv run --project Backend python Model/scripts/prepare_corpus.py
```

Los pesos quedan en `Model/models/`, montados de solo lectura. El modelo de inferencia es
Qwen2.5-3B-Instruct-AWQ y E5-large genera embeddings. La descarga se realiza durante la
preparación; en ejecución, vLLM usa los archivos locales sin consultar el repositorio de
modelos.

## Ejecutar el flujo principal

Para el modo local REGEX:

```bash
docker compose -f compose.yaml -f compose.dev.yaml up -d --build
```

Para activar SLM y RAG en esos mismos servicios, añade `.env.model` y el override híbrido:

```bash
docker compose --env-file .env --env-file .env.model \
  -f compose.yaml -f compose.dev.yaml -f compose.hybrid.yaml \
  up -d --build
```

Con los servicios listos, carga el corpus en el PostgreSQL del flujo principal:

```bash
docker compose --env-file .env --env-file .env.model \
  -f compose.yaml -f compose.dev.yaml -f compose.hybrid.yaml \
  run --rm --no-deps backend python -m privateway_model.rag /corpus/manifest.json
```

El catálogo de chat y sus proveedores se configuran en `.env`. Al usar proveedores externos,
prueba solo con mensajes sintéticos. Las evaluaciones de detección y flujo usan el proveedor
espía local y no transmiten consultas.

## Datasets

Los benchmarks sintéticos están en `Model/datasets/`. V1 y v2 comparten el formato de
registros y manifiestos; la estructura está descrita en [Model/datasets/README.md](Model/datasets/README.md).
La validación está reservada y no debe usarse para ajustar prompts, reglas o modelos.

Para regenerar los datos sintéticos:

```bash
uv run --project Backend python Model/scripts/generate_benchmark_v1.py
uv run --project Backend python Model/scripts/generate_benchmark_v2.py
```

## Evaluar

Los resultados se escriben en `Model/experimentos/resultados/`, un directorio local ignorado
por Git. El Compose híbrido lo monta en `/model/resultados`. Ejemplo de cribado de 60 familias,
solo con desarrollo:

```bash
docker compose --env-file .env --env-file .env.model \
  -f compose.yaml -f compose.dev.yaml -f compose.hybrid.yaml exec -T backend \
  python -m privateway_model.evaluate \
  --datos /model/datasets/v2/matriz-60 --modo hibrido --nivel flujo \
  --split desarrollo --concurrencia 1 \
  --salida /model/resultados/cribado/flujo-hibrido-dev-c1.json
```

Para el conjunto completo de desarrollo, cambia `--datos` a `/model/datasets/v2` y usa un
nombre de salida nuevo. Se pueden comparar `regex`, `slm` e `hibrido` con `--nivel deteccion`;
`--nivel flujo` evalúa el flujo completo con el proveedor espía local.

Para exportar una corrida a CSV:

```bash
uv run --project Backend python Model/scripts/export_experiments.py \
  --resultados Model/experimentos/resultados/cribado \
  --salida Model/experimentos/resultados/cribado/export
```

Consulta métricas e intervalos por familia antes de interpretar resultados. El conjunto `reto`
se reporta aparte y la validación reservada se ejecuta solo después de congelar la configuración.
