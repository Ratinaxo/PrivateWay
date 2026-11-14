# Informe del piloto local — 14 de noviembre de 2026

**Infraestructura e integración implementadas; esta configuración del SLM todavía no es apta para el flujo funcional.**

## Configuración y alcance

RTX 3070 de 8 GB; aproximadamente 16 GB de RAM en Windows y 7,72 GiB disponibles para Docker/WSL2. vLLM 0.10.2 con Qwen2.5-3B-Instruct-AWQ, kernel AWQ-Marlin, float16, contexto 4096, salida máxima 1024, temperatura 0, una generación simultánea y presupuesto GPU 75 %. E5-large opera en CPU y pgvector realiza búsqueda exacta top-4.

Se prepararon 120 consultas (60 desarrollo y 60 validación) y 24 preguntas de recuperación. Esta primera ejecución utiliza los diez escenarios iniciales de desarrollo, con las seis categorías, combinaciones, repeticiones e historial. No se ejecutó validación reservada. Cada configuración tiene un calentamiento previo y una sola pasada: estas muestras no permiten concluir capacidad sostenida ni generalización.

Corpus oficial: 11 unidades legislativas, divididas en 12 fragmentos del índice activo. Las disposiciones reformadas se extraen de la Ley 21.719, con su versión XML real y estado temporal; el servicio XML de BCN no entregó un consolidado futuro de la Ley 19.628. Los localizadores, hashes, fuentes y revisiones están en `corpus/manifest.json` y `models.lock.json`.

## Comprobaciones técnicas

- Backend: 76 pruebas automatizadas aprobadas; una advertencia de deprecación de TestClient/httpx.
- Frontend: batería de contratos offline aprobada; no se modificó la interfaz.
- Docker reconoce la GPU y vLLM carga el modelo; E5 y PostgreSQL están disponibles.
- La ingesta repetida conserva el mismo identificador de índice y los 12 fragmentos.
- Readiness interno verificado. Entrada local mediante proxy en `127.0.0.1:8082`.
- Conexión directa del gateway a 1.1.1.1:443 rechazada con código 101 (sin ruta). Es una comprobación puntual, además del aislamiento definido en Compose.
- Fallos de esquema, offsets, referencias, servicios, timeout y auditoría se prueban con dobles controlados; no habilitan envío. Eso no garantiza que el modelo detecte toda PII o toda inyección.

## Pruebas reales de las tres acciones

| Acción esperada | HTTP esperado | HTTP observado | Acción recibida | Tiempo (s) |
|---|---:|---:|---|---:|
| permitir | 200 | 503 | ANALISIS_NO_DISPONIBLE | 8.967 |
| seudonimizar | 200 | 503 | ANALISIS_NO_DISPONIBLE | 4.449 |
| bloquear | 403 | 403 | POLITICA_BLOQUEA | 7.262 |

Una detención técnica (503) no es un bloqueo decidido por el SLM. Una seudonimización requiere además la acción esperada: HTTP 200 por sí solo no acredita protección.

## Comparación medida

Detección compara spans y categorías exactos; no transmite al proveedor. Flujo ejecuta la API ASGI real, validación, auditoría cifrada, proveedor espía simulado y posprocesamiento. Su latencia excluye la conexión TCP y el proxy; la prueba anterior sí los incluye. Los fallos técnicos cuentan como omisiones en detección y se informan separadamente de bloqueos.

| Nivel / variante | Concurrencia | n | Fallos técnicos | F2 micro | p50 (s) | p95 (s) | Transmitidas | Aciertos de acción |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| deteccion/regex | 1 | 10 | 0 | 0.439 | 0.000 | 0.002 | — | — |
| deteccion/regex | 5 | 10 | 0 | 0.439 | 0.000 | 0.000 | — | — |
| deteccion/regex | 10 | 10 | 0 | 0.439 | 0.000 | 0.000 | — | — |
| deteccion/slm | 1 | 10 | 9 | 0.000 | 6.547 | 11.130 | — | — |
| deteccion/slm | 5 | 10 | 9 | 0.000 | 24.372 | 34.019 | — | — |
| deteccion/slm | 10 | 10 | 9 | 0.000 | 33.741 | 68.229 | — | — |
| deteccion/hibrido | 1 | 10 | 5 | 0.439 | 6.820 | 11.153 | — | — |
| deteccion/hibrido | 5 | 10 | 5 | 0.439 | 29.715 | 39.871 | — | — |
| deteccion/hibrido | 10 | 10 | 5 | 0.439 | 37.598 | 71.649 | — | — |
| flujo/hibrido | 1 | 10 | 9 | 0.000 | 6.406 | 11.806 | 1 | 1 |
| flujo/hibrido | 5 | 10 | 9 | 0.000 | 31.617 | 36.967 | 1 | 1 |
| flujo/hibrido | 10 | 10 | 9 | 0.000 | 35.668 | 71.428 | 1 | 1 |

Recall@4 documental: **1.000**, sobre las doce preguntas de desarrollo. Se considera acierto recuperar un fragmento del artículo/letra esperado. Son preguntas jurídicas directas, distintas de las consultas empresariales analizadas por el gateway; no mide pertinencia de las fuentes en esas decisiones, de la justificación ni corrección jurídica.

## Exposición y errores

- Concurrencia 1: 1 consultas transmitidas, 0 bloqueadas por decisión, 9 fallos técnicos y 0 apariciones literales anotadas aún visibles en los envíos.
- Concurrencia 5: 1 consultas transmitidas, 0 bloqueadas por decisión, 9 fallos técnicos y 0 apariciones literales anotadas aún visibles en los envíos.
- Concurrencia 10: 1 consultas transmitidas, 0 bloqueadas por decisión, 9 fallos técnicos y 0 apariciones literales anotadas aún visibles en los envíos.

Códigos de fallo del flujo (incluyen calentamiento): `SLM_ACCION_INCOHERENTE`: 12, `SLM_OFFSET_INVALIDO`: 15

La exposición se estima por coincidencia literal de valores anotados y solo sobre consultas enviadas. No mide inferencia ni reidentificación. Cero envíos no implica protección útil y no permite definir una tasa de exposición sobre transmisiones. En esta ejecución, el único envío de cada configuración fue un control negativo sin PII; por ello cero exposición no demuestra eficacia del tratamiento.

## Recursos observados

VRAM total observada: media 7542 MiB, máximo 7553 MiB. Incluye otras cargas del escritorio; no es consumo atribuible exclusivamente al modelo.

Utilización GPU media 26.2 %, máximo muestreado 100.0 %.

- `privateway-pilot-backend-1`: RAM media 192 MiB; máximo muestreado 219 MiB. CPU media 8.7 %; máximo 167.5 %.
- `privateway-pilot-embeddings-1`: RAM media 1696 MiB; máximo muestreado 1738 MiB. CPU media 21.3 %; máximo 193.4 %.
- `privateway-pilot-postgres-1`: RAM media 43 MiB; máximo muestreado 45 MiB. CPU media 1.4 %; máximo 14.4 %.
- `privateway-pilot-proxy-1`: RAM media 11 MiB; máximo muestreado 11 MiB. CPU media 0.0 %; máximo 0.0 %.
- `privateway-pilot-slm-1`: RAM media 2598 MiB; máximo muestreado 2629 MiB. CPU media 84.9 %; máximo 108.2 %.

Muestreo aproximadamente cada diez segundos; los máximos pueden omitir picos breves. No se midió energía.

## Criterio de cierre y siguiente trabajo

La infraestructura, el RAG, los contratos y la instrumentación quedan disponibles para continuar pruebas. La configuración actual del SLM no se acepta para el flujo funcional: hubo nueve fallos técnicos de diez consultas en cada nivel de concurrencia. El detector híbrido no mejoró el F2 de REGEX en este lote y añadió latencia. Las pruebas automatizadas no sustituyen la evaluación del modelo. No se acredita protección integral ni cumplimiento legal.

Antes de ampliar las pruebas: revisar anotaciones y cada fallo de extracción/coherencia, contrastar simplificación del contrato o un modelo candidato con mayor capacidad, y usar exclusivamente desarrollo para ajustar. Después ejecutar los 60 casos completos de desarrollo y reservar validación para una configuración cerrada. Restitución, proveedor real y taxonomía completa siguen en el hito posterior.

Evidencias detalladas y mediciones por categoría: `results/` (local, ignorado por Git). El conjunto reservado permanece sin ejecutar. Las instrucciones de reproducción están en `../README-pilot.md`.
