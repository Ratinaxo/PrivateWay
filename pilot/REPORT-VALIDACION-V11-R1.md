# Repetición del piloto — 2026-11-18

**Pruebas de flujo aprobadas en este lote.**

## Cambios y alcance

El SLM extrae valores literales sin calcular offsets. El programa ancla cada valor exactamente en su mensaje, expande las repeticiones y conserva REGEX. El juicio técnico recibe hallazgos verificados; una etapa posterior fundamenta la clasificación con fuentes legislativas sin cambiar la acción. El gateway sigue rechazando una acción contradictoria. No se convierten respuestas inválidas en permisos ni se sustituyen por el modo REGEX.

Modelo: `Qwen/Qwen2.5-7B-Instruct-AWQ`, revisión `b25037543e9394b818fdfca67ab2a00ecc7dd641`. Protocolo `etapas-v11`; contexto 4096 tokens. vLLM 0.10.2, AWQ-Marlin, temperatura 0, salida máxima 1024 por llamada y una generación simultánea. E5-large en CPU; pgvector exacto top-4.

Prefill: 512 tokens por lote; presupuesto GPU 75%.

Se ejecutaron doce configuraciones con 60 escenarios de validacion cada una. Detección ejecuta solo extracción; flujo incluye extracción y juicio, API ASGI, auditoría cifrada y proveedor espía simulado. La latencia ASGI excluye TCP/proxy; el smoke sí incluye el acceso HTTP local.

## Smoke real

| Esperada | HTTP | Observada | Correcta |
|---|---:|---|---|
| permitir | 200 | permitir | sí |
| seudonimizar | 200 | seudonimizar | sí |
| bloquear | 403 | POLITICA_BLOQUEA | sí |

## Comparación

| Nivel / variante | Concurrencia | n | Errores | F2 micro | p50 s | p95 s | Envíos | Acciones correctas |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| deteccion/regex | 1 | 60 | 0 | 0.439 | 0.000 | 0.000 | — | — |
| deteccion/regex | 5 | 60 | 0 | 0.439 | 0.000 | 0.000 | — | — |
| deteccion/regex | 10 | 60 | 0 | 0.439 | 0.000 | 0.000 | — | — |
| deteccion/slm | 1 | 60 | 0 | 0.864 | 2.545 | 4.025 | — | — |
| deteccion/slm | 5 | 60 | 0 | 0.864 | 9.942 | 12.620 | — | — |
| deteccion/slm | 10 | 60 | 0 | 0.864 | 20.093 | 23.249 | — | — |
| deteccion/hibrido | 1 | 60 | 0 | 0.990 | 2.520 | 4.088 | — | — |
| deteccion/hibrido | 5 | 60 | 0 | 0.990 | 10.284 | 11.841 | — | — |
| deteccion/hibrido | 10 | 60 | 0 | 0.990 | 19.893 | 23.154 | — | — |
| flujo/hibrido | 1 | 60 | 0 | 0.990 | 7.760 | 13.621 | 54 | 60 |
| flujo/hibrido | 5 | 60 | 0 | 0.990 | 39.324 | 44.027 | 54 | 60 |
| flujo/hibrido | 10 | 60 | 0 | 0.987 | 81.168 | 85.696 | 54 | 60 |

## Latencia por etapa del flujo

| Concurrencia | Etapa | Observaciones | p50 s | p95 s |
|---:|---|---:|---:|---:|
| 1 | posprocesamiento_ms | 54 | 0.000 | 0.000 |
| 1 | proveedor_ms | 54 | 0.000 | 0.000 |
| 1 | rag_ms | 60 | 0.315 | 0.384 |
| 1 | regex_ms | 60 | 0.000 | 0.000 |
| 1 | slm_ms | 60 | 7.426 | 13.295 |
| 1 | transformacion_ms | 60 | 0.000 | 0.000 |
| 5 | posprocesamiento_ms | 54 | 0.000 | 0.000 |
| 5 | proveedor_ms | 54 | 0.000 | 0.000 |
| 5 | rag_ms | 60 | 0.323 | 0.732 |
| 5 | regex_ms | 60 | 0.000 | 0.000 |
| 5 | slm_ms | 60 | 38.981 | 43.691 |
| 5 | transformacion_ms | 60 | 0.000 | 0.000 |
| 10 | posprocesamiento_ms | 54 | 0.000 | 0.000 |
| 10 | proveedor_ms | 54 | 0.000 | 0.000 |
| 10 | rag_ms | 60 | 0.332 | 2.231 |
| 10 | regex_ms | 60 | 0.000 | 0.001 |
| 10 | slm_ms | 60 | 80.817 | 85.320 |
| 10 | transformacion_ms | 60 | 0.000 | 0.000 |

Rendimiento del flujo por concurrencia: 1: 0.12 solicitudes/s, 5: 0.13 solicitudes/s, 10: 0.13 solicitudes/s.

Los errores cuentan como omisiones; las categorías y spans deben coincidir exactamente. Detección no exige un juicio de tratamiento y nunca transmite consultas.

## Recuperación, exposición y fallos

- Concurrencia 1: 54 envíos, 6 bloqueos del SLM, 0 fallos técnicos; 0/66 apariciones literales, 0/66 parcialmente visibles.
- Concurrencia 5: 54 envíos, 6 bloqueos del SLM, 0 fallos técnicos; 0/66 apariciones literales, 0/66 parcialmente visibles.
- Concurrencia 10: 54 envíos, 6 bloqueos del SLM, 0 fallos técnicos; 0/66 apariciones literales, 0/66 parcialmente visibles.

Recall@4: 0.917, en doce preguntas jurídicas de validacion. Esta métrica mide recuperación documental. La pertinencia de citas y fundamentos requiere revisión aparte. La comprobación de exposición se limita a las apariciones anotadas.

Códigos técnicos (incluido calentamiento): ninguno registrado.

## Recursos observados

VRAM total: media 7123 MiB; máximo muestreado 7129 MiB (incluye escritorio y otras cargas).
- `privateway-pilot-backend-1`: RAM media 202 MiB, máximo 245 MiB; CPU media 4.5 %.
- `privateway-pilot-embeddings-1`: RAM media 1723 MiB, máximo 1785 MiB; CPU media 15.0 %.
- `privateway-pilot-postgres-1`: RAM media 53 MiB, máximo 55 MiB; CPU media 0.9 %.
- `privateway-pilot-proxy-1`: RAM media 15 MiB, máximo 15 MiB; CPU media 0.0 %.
- `privateway-pilot-slm-1`: RAM media 2924 MiB, máximo 2934 MiB; CPU media 95.1 %.
Muestreo aproximado cada diez segundos; no mide picos breves ni energía.

## Reproducibilidad y límites

- Corpus: `ea2b48b25a674191461aa5dbe14355568b311119e724c4596d651aa36c85edc7`.
- Instrucciones SHA-256: `83c481064ed16ef91b39691ad1538de5062a1a85679f264619d61fbf54d3679f`.
- Esquemas de inferencia SHA-256: `7101d234e173a91ba22235c73da19ca4359e84d5ebb02ca113c39007ea7123a5`.
- Dataset SHA-256: `6a454c596a30de2c8da02981c1795aa23ec9f31d96f798e7e02ee41d77b6dc77`.
- Evidencias locales: `pilot/results/20261118-validacion-v11/repeticion-1`.
- Cada repetición usa una carpeta independiente; no se acumulan eventos de ejecuciones anteriores.
- Se conservaron el informe del 14 de noviembre, el modelo anterior y sus revisiones.
- Una pasada por configuración con datos sintéticos no demuestra generalización ni resistencia a toda inyección.
- La utilidad con proveedor externo y la restitución requieren sus propias pruebas.

- Commit base: `ba3f4eda853c39ab096b6bc0df4a21ebf77b9721`. Árbol de trabajo limpio.
