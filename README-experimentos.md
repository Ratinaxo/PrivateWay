# Experimentos y pruebas de PrivateWay

Guía para ejecutar las pruebas automáticas del código y evaluar el pipeline local de detección, RAG y flujo. Los comandos de Compose se ejecutan desde la raíz del repositorio. No se necesita un proveedor de chat externo para las evaluaciones directas: el flujo integra un proveedor espía local. El smoke HTTP descrito más abajo sí puede llamar a un proveedor real.

## Datos y separación de conjuntos

El benchmark ampliado está en [`Model/datasets/v2/`](Model/datasets/v2/README.md):

- `desarrollo.json`: 600 casos, 60 familias. Úsalo para iterar y refinar.
- `matriz-60/`: 60 casos, uno por familia, para cribado rápido; incluye 12 consultas RAG.
- `validacion.json`: 1.200 casos reservados. No lo uses para ajustar prompts, reglas o modelos.
- `reto.json`: 200 casos adversariales; reporta sus métricas aparte, no como muestra representativa.

Las consultas y valores del benchmark son sintéticos. No reemplaces los mensajes sintéticos por conversaciones de usuarios. Revisa los tamaños y límites de los datos en el README del benchmark antes de regenerarlos.

## 1. Pruebas automáticas

Requiere Python 3.12+, `uv` y Node.js compatible con el frontend. Desde la raíz:

```bash
uv sync --project Backend --dev
uv run --project Backend pytest -q
cd Frontend
node --run test:contracts
cd ..
```

Las pruebas del backend usan dobles locales para SLM, proveedores, persistencia y servicios externos. `test:contracts` ejecuta los contratos offline del frontend. Estos comandos no ejecutan la batería de evaluación del modelo.

## 2. Preparar el laboratorio aislado

El Compose del piloto tiene su propio gateway, base de datos, embeddings y SLM. Requiere Docker Compose, GPU NVIDIA con memoria disponible y espacio para imágenes/modelos. Prepara las credenciales locales y los modelos una vez:

```bash
uv sync --project Backend --dev
uv run --project Backend python Model/scripts/setup_pilot.py --slm 3b
uv run --project Backend python Model/scripts/download_models.py
uv run --project Backend python Model/scripts/prepare_corpus.py
```

Los archivos `.env` y `.env.pilot` son locales; no los imprimas, copies a reportes ni los agregues a Git. Para construir e iniciar el laboratorio:

```bash
docker compose --env-file .env --env-file .env.pilot -f compose.pilot.yaml build
docker compose --env-file .env --env-file .env.pilot -f compose.pilot.yaml up -d slm embeddings postgres
docker compose --env-file .env --env-file .env.pilot -f compose.pilot.yaml run --rm --no-deps backend python -m privateway_model.rag /corpus/manifest.json
docker compose --env-file .env --env-file .env.pilot -f compose.pilot.yaml -f compose.lab.yaml up -d backend proxy
docker compose --env-file .env --env-file .env.pilot -f compose.pilot.yaml ps
```

La ingesta del corpus activa una versión identificada por hash y es reutilizable. No borres volúmenes: no uses `down -v`. `/ready` del gateway también requiere una ruta de chat preparada; por eso puede responder 503 aunque el SLM, embeddings y RAG estén listos para la evaluación directa.

**GPU:** no levantes simultáneamente el SLM del Compose aislado y el vLLM del stack principal si la GPU no tiene memoria para ambos. En equipos con VRAM limitada, elige un solo stack de inferencia.

## 3. Evaluar una configuración directamente

El evaluador comprueba SLM y RAG y escribe JSON en `/pilot/results`, que está compartido con `Model/experimentos/resultados` del host. Usa una ruta de salida nueva para cada combinación; el directorio de resultados debe ser escribible por el usuario del contenedor.

Ejemplo de cribado híbrido de 60 familias, solo desarrollo:

```bash
docker compose --env-file .env --env-file .env.pilot -f compose.pilot.yaml exec -T backend \
  python -m privateway_model.evaluate \
  --datos /pilot/datasets/v2/matriz-60 \
  --modo hibrido --nivel flujo --split desarrollo --concurrencia 1 \
  --salida /pilot/results/cribado-20261119/flujo-hibrido-dev-c1.json
```

`--nivel flujo --modo hibrido` usa la API ASGI y un proveedor espía simulado, solo dentro de la evaluación. No llama a un proveedor real. Para comparar detectores, ejecuta `--nivel deteccion` con `--modo regex`, `slm` e `hibrido` sobre el mismo split y concurrencia. Para medir el flujo integral, usa `--nivel flujo --modo hibrido`.

Ejemplo para el benchmark completo de desarrollo:

```bash
docker compose --env-file .env --env-file .env.pilot -f compose.pilot.yaml exec -T backend \
  python -m privateway_model.evaluate \
  --datos /pilot/datasets/v2 \
  --modo hibrido --nivel flujo --split desarrollo --concurrencia 1 \
  --salida /pilot/results/desarrollo-600/flujo-hibrido-dev-c1.json
```

Parámetros disponibles:

- `--modo`: `regex`, `slm` o `hibrido`.
- `--nivel`: `deteccion` o `flujo`; el flujo requiere `--modo hibrido`.
- `--split`: por defecto `desarrollo`; también existen `validacion` y `reto`.
- `--concurrencia`: `1`, `5` o `10`.
- `--limite N`: evalúa solo los primeros N casos del archivo elegido. Para un cribado balanceado de 60 familias, selecciona `matriz-60`; limitar a 60 el archivo completo no equivale a esa matriz.

Para evaluar otra configuración, conserva iguales el dataset, split y tamaño de muestra, y cambia explícitamente modo, nivel, concurrencia y nombre de salida. Los fallos técnicos se cuentan como omisiones de detección; no como bloqueos correctos.

### Batería automatizada

[`Model/scripts/run_pilot.py`](Model/scripts/run_pilot.py) ejecuta los tres smoke HTTP y luego la matriz de 12 configuraciones: detección REGEX/SLM/híbrida y flujo híbrido, cada una con concurrencia 1/5/10. Por defecto usa el dataset inicial; `--dataset v2` usa los 600 casos de desarrollo. Por ejemplo:

```bash
uv run --project Backend python Model/scripts/run_pilot.py --dataset v2 --output-dir Model/experimentos/resultados/v2-desarrollo-completo
```

Para una pantalla exploratoria de prefijo, admite `--limite N`; el directorio de salida debe ser nuevo y estar bajo `Model/experimentos/resultados`. `--repeticiones N` repite la matriz completa. El proceso guarda JSON por configuración, eventos de flujo, consumo aproximado de recursos e imágenes usadas; también genera la exportación CSV.

El lanzador **espera `/ready` y ejecuta un smoke HTTP para el alias `pw-simulado` antes de iniciar la batería**. En runtime, el adaptador simulado está deshabilitado. Para usar este lanzador, ese alias debe estar asociado a un proveedor real preparado; los tres mensajes del smoke son sintéticos y sí se enviarán a ese proveedor. Si no quieres configurar o llamar a un proveedor externo, usa el evaluador directo de la sección anterior: su flujo usa un espía local y no necesita el smoke HTTP.

Para ejecutar solo ese smoke, añade `--smoke-only` y un directorio de salida nuevo. La batería devuelve código distinto de cero si falla el smoke o si el flujo no cumple sus gates de errores, acciones y exposición; conserva los JSON generados para revisar el fallo.

```bash
uv run --project Backend python Model/scripts/run_pilot.py --smoke-only --output-dir Model/experimentos/resultados/smoke-local
```

En Linux, si Docker requiere `sudo`, el lanzador permite solicitar la contraseña una vez y usar `sudo -n` para los comandos Docker:

```bash
PRIVATEWAY_DOCKER_SUDO=1 uv run --project Backend python Model/scripts/run_pilot.py --dataset v2
```

No ejecutes el conjunto reservado para iterar. Además de separar los splits, revisa que la configuración y el prompt estén congelados antes de una evaluación final. El lanzador solo usa desarrollo; la validación se invoca explícitamente con `--split validacion`.

## 4. Métricas y exportación

Cada JSON registra TP/FP/FN exactos y parciales, precisión, recall, F1/F2 micro y macro, latencias p50/p95/p99, errores y Recall@4. El nivel flujo añade matriz de acciones, falsos bloqueos, envíos y exposición exacta/parcial condicionada a transmisiones confirmadas. Las consultas y valores personales no se exportan.

Para reconstruir las tablas CSV de una corrida:

```bash
uv run --project Backend python Model/scripts/export_experiments.py \
  --resultados Model/experimentos/resultados/v2-desarrollo-completo \
  --salida Model/experimentos/resultados/v2-desarrollo-completo/export
```

La exportación contiene `experimentos.csv`, `metricas_categoria.csv`, `casos.csv`, `recuperacion.csv` y `manifest.json`. Los intervalos nuevos se calculan por bootstrap de familias; no interpretes spans correlacionados como observaciones independientes. Las métricas por familia del screen de 60 casos sirven para cribado, no para aceptación estadística.

## 5. Congelar antes de abrir la validación

La validación es una evaluación reservada de una sola configuración final, no una herramienta de ajuste. El congelador requiere una corrida de desarrollo completa y aprobada, las doce configuraciones comparables, un árbol Git limpio y hashes registrados:

```bash
uv run --project Backend python Model/scripts/freeze_pilot.py \
  --desarrollo Model/experimentos/resultados/v2-desarrollo-completo \
  --salida Model/experimentos/resultados/congelacion-v2.json
```

Solo después de congelar modelo, prompts, reglas, corpus, datos y criterios, ejecuta explícitamente el evaluador con `--split validacion`. Guarda esa corrida aparte y no uses sus resultados para cambiar la configuración. `reto` debe reportarse por separado como prueba de estrés.

## Referencias

- [README-pilot.md](README-pilot.md): instalación, corpus, API y E2E.
- [README-docker.md](README-docker.md): comandos de Compose para el piloto aislado y el stack híbrido principal.
- [Backend README](Backend/README.md): dependencias y pruebas del backend.
- [Benchmark v2](Model/datasets/v2/README.md): composición, familias y límites de cada split.
