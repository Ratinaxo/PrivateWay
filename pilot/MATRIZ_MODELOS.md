# Plan de comparación: SLM y embeddings

## Variantes

| SLM | Embeddings | Identificador local | Carpeta del índice |
|---|---|---|---|
| Qwen2.5-3B-Instruct-AWQ | multilingual-e5-large | `qwen-e5` | `/models/e5` |
| Qwen2.5-3B-Instruct-AWQ | BGE-M3 | `qwen-bge-m3` | `/models/bge-m3` |
| Qwen3.5-4B-AWQ | multilingual-e5-large | `qwen35-e5` | `/models/e5` |
| Qwen3.5-4B-AWQ | BGE-M3 | `qwen35-bge-m3` | `/models/bge-m3` |

La candidata Qwen3.5 usa por ahora el checkpoint AWQ comunitario
[`QuantTrio/Qwen3.5-4B-AWQ`](https://huggingface.co/QuantTrio/Qwen3.5-4B-AWQ), no pesos
cuantizados publicados por Qwen. El script de descarga registra el commit y hashes en
`pilot/models.lock.json`. El override usa vLLM 0.17.0, versión mínima indicada por la receta
oficial para Qwen3.5; el tag debe convertirse en digest antes de congelar resultados
([receta vLLM](https://github.com/vllm-project/recipes/blob/main/models/Qwen/Qwen3.5-9B.yaml),
[modelos soportados](https://docs.vllm.ai/en/latest/models/supported_models/)).

BGE-M3 da vectores densos de 1024 dimensiones como E5 y permite evaluar búsqueda densa
manteniendo el esquema pgvector. Sus modos disperso y multi-vector no están implementados en
este gateway y no se incluirán en esta comparación
([ficha BGE-M3](https://huggingface.co/BAAI/bge-m3)). Cambiar de encoder exige reindexar
el corpus: nunca consultar embeddings E5 contra el índice BGE-M3.

## Protocolo

1. Descargar modelos y verificar hashes; comprobar espacio libre y fijar la imagen vLLM.
2. Revisar manualmente las anotaciones y las consultas RAG de desarrollo. La revisión offline
   de estructura/offsets/política encontró 0 inconsistencias en 2.000 filas. No sustituye
   la revisión semántica humana.
3. Para cada embedding, iniciar servicios, ingerir de nuevo `/corpus/manifest.json` y registrar
   el ID del índice activo y su metadata.
4. Para cada una de las cuatro combinaciones, ejecutar en `desarrollo` y concurrencia 1:
   `deteccion/slm`, `deteccion/hibrido` y `flujo/hibrido`. Correr `deteccion/regex` una vez
   como referencia. No usar el split reservado.
5. Comparar F2/precisión/recall por categoría, spans filtrados expuestos, acierto de acción,
   fallos técnicos, Recall@4, latencia p50/p95 y memoria. No declarar ganador por latencia
   o F2 solamente si aumenta una exposición.
6. La explicación añadida a la traza usa motivos deterministas del gateway y registra por
   separado las referencias recuperadas y su estado temporal. Indica expresamente que son
   contexto y que la acción no deriva de ellas; no es una justificación jurídica.
7. La validación jurídica de la regla requiere revisión de una persona competente. La
   validación estadística reservada permanece sin ejecutar hasta congelar política, prompt,
   modelos, versiones, índices y umbrales.

La pauta para esa revisión está en [`REVISION_POLITICA.md`](REVISION_POLITICA.md); el
documento queda pendiente de aprobación externa.

## Resultados ejecutados

### Pipeline anterior a la fusión independiente

Los JSON `matrix-qwen25-*` y las filas históricas previas corresponden al prompt anterior,
que pasaba los hallazgos REGEX al SLM. Se conservan como referencia, pero **no se comparan
con la versión actual**: cambió la arquitectura de detección y el hash de instrucciones.
Tampoco sirven para afirmar que E5 vence a BGE-M3 en la arquitectura ya unificada.

### Pipeline paralelo y fusión v7

En el cribado `matriz-60` (60 casos, un caso por cada familia) se ejecutaron REGEX, SLM
independiente, unión híbrida y el flujo completo. Se usó Qwen2.5+E5, concurrencia 1 y
proveedor espía local. REGEX y SLM recibieron el prompt original; la salida de cada uno se
unió por offsets/categoría y el flujo aplicó el tratamiento antes de enviar.

| Etapa | TP / FP / FN exactos | Precisión | Recall | F1 | F2 | p50 / p95 ms |
|---|---:|---:|---:|---:|---:|---:|
| REGEX | 45 / 0 / 45 | 1.000 | 0.500 | 0.667 | 0.556 | 0.021 / 0.051 |
| SLM independiente | 54 / 1 / 36 | 0.982 | 0.600 | 0.745 | 0.651 | 2374 / 4560 |
| Unión REGEX+SLM | 62 / 1 / 28 | 0.984 | 0.689 | 0.810 | 0.733 | 2382 / 4573 |
| Flujo completo | 62 / 1 / 28 | 0.984 | 0.689 | 0.810 | 0.733 | 2415 / 4666 |

El flujo tuvo cero errores técnicos, Recall@4 1.00 en las 12 preguntas documentales de
desarrollo, y 46/60 acciones correctas (76.7 %). La matriz de acciones es:

| Esperada \ observada | Permitir | Seudonimizar | Bloquear | Error |
|---|---:|---:|---:|---:|
| Permitir | 15 | 0 | 0 | 0 |
| Seudonimizar | 0 | 30 | 0 | 0 |
| Bloquear | 0 | 14 | 1 | 0 |

No hubo falsos bloqueos en los 15 controles limpios (0 % observado), aunque una muestra de
15 controles no basta para afirmar que la tasa real está por debajo del 5 %.

De 60 casos, 59 se transmitieron y uno se bloqueó. Entre las 44 solicitudes sensibles
transmitidas se observaron 88 apariciones de referencia: 28 completas y 22 parcialmente
visibles, 50/88 en total (56.8 % de apariciones). Hubo al menos una exposición en 37/44
solicitudes sensibles transmitidas (84.1 %). **La versión actual falla el gate de cero
exposición y está lejos de los gates provisionales de recall ≥98 % y acción ≥98 %.** Catorce
de quince casos esperados como bloqueos por salud terminaron seudonimizados; este debe ser
el primer conjunto de errores a corregir.

No se fijó un límite de latencia p95 antes del experimento, por lo que no se puede declarar
aprobado ese gate. El p95 de 4.67 s corresponde a ejecución local por API ASGI y simulador;
no incluye conexión TCP del proxy ni un proveedor externo. El resultado RAG es un cribado
pequeño y no demuestra pertinencia legal ni calidad de justificaciones.

Resultados nuevos completos en `pilot/results/recheck-v7-*-screen60-c1.json`. Los CSV
exportados y los intervalos por bootstrap de familia están en
`/tmp/privateway-recheck-v7-export/`; los intervalos son exploratorios por el tamaño y
carácter sintético del conjunto. El validador reservado no se ejecutó.

### Qwen3.5 en el hardware disponible

Se descargó y fijó el checkpoint comunitario `QuantTrio/Qwen3.5-4B-AWQ` y se intentó
servirlo con vLLM 0.17.0, con la GPU RTX 4050 libre al inicio. La carga no pudo reservar
memoria suficiente para los bloques de caché KV (`No available memory for the cache
blocks`). Reducir el lote de tokens no resolvió el problema. También se probó el offload
a CPU, pero esa ruta terminó en una aserción interna de vLLM al reinicializar el lote.
Por tanto, no hay resultados válidos de Qwen3.5 con E5 ni con BGE-M3; ambas combinaciones
quedan pendientes de hardware con más VRAM o una cuantización/runtime compatible. El
contenedor SLM se restauró a Qwen2.5 y el backend al índice E5 para dejar el piloto en la
configuración estable conocida.

## Preparación y ejecución en el host Docker

La ejecución local usó Docker con privilegios y una GPU NVIDIA RTX 4050 Laptop de 6 GiB.
Los artefactos de modelos e imágenes descargados se registraron localmente; los JSON de
resultados viven en `pilot/results/` y no se deben subir si no se desea conservarlos en el
repositorio.

```bash
uv run --project backend python scripts/download_models.py
```

Para cada pareja, exportar las variables de la tabla siguiente al entorno de Compose (si se
usa `sudo`, pasarlas explícitamente con `sudo env VAR=valor ...`). Después levantar el override
solo para Qwen3.5, esperar `/ready`, reingerir el corpus y reiniciar backend/proxy. Las órdenes
no deben ejecutar `validacion`.

```text
Qwen2.5: PRIVATEWAY_SLM_MODEL_DIR=/models/qwen
         PRIVATEWAY_SLM_MODEL_KIND=qwen
         PRIVATEWAY_SLM_QUANTIZATION=awq_marlin
         compose: compose.pilot.yaml
Qwen3.5: PRIVATEWAY_SLM_MODEL_DIR=/models/qwen35
         PRIVATEWAY_SLM_MODEL_KIND=qwen35
         PRIVATEWAY_SLM_QUANTIZATION=awq
         compose: compose.pilot.yaml + compose.pilot.qwen35.yaml
E5:      PRIVATEWAY_EMBEDDINGS_MODEL=/models/e5
         PRIVATEWAY_EMBEDDINGS_MODEL_ID=intfloat/multilingual-e5-large
         PRIVATEWAY_EMBEDDINGS_KIND=e5
BGE-M3:  PRIVATEWAY_EMBEDDINGS_MODEL=/models/bge-m3
         PRIVATEWAY_EMBEDDINGS_MODEL_ID=BAAI/bge-m3
         PRIVATEWAY_EMBEDDINGS_KIND=bge-m3
```

El evaluador existente acepta `--datos /pilot/datasets/v2`, `--split desarrollo`,
`--concurrencia 1`, `--modo` y `--nivel`; los JSON de salida deben nombrar la combinación,
por ejemplo `qwen35-bge-m3-flujo-dev-c1.json`. Antes de usar el conjunto reservado, validar
manualmente los errores de desarrollo y aprobar el protocolo con la revisión jurídica.
