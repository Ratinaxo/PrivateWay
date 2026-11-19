# Repetición del piloto — 2026-11-18

**Pruebas de flujo aprobadas en este lote.**

## Cambios y alcance

El SLM extrae valores literales sin calcular offsets. El programa ancla cada valor exactamente en su mensaje, expande las repeticiones y conserva REGEX. El juicio técnico recibe hallazgos verificados; una etapa posterior fundamenta la clasificación con fuentes legislativas sin cambiar la acción. El gateway sigue rechazando una acción contradictoria. No se convierten respuestas inválidas en permisos ni se sustituyen por el modo REGEX.

Modelo: `Qwen/Qwen2.5-7B-Instruct-AWQ`, revisión `b25037543e9394b818fdfca67ab2a00ecc7dd641`. Protocolo `etapas-v11`; contexto 4096 tokens. vLLM 0.10.2, AWQ-Marlin, temperatura 0, salida máxima 1024 por llamada y una generación simultánea. E5-large en CPU; pgvector exacto top-4.

Prefill: 512 tokens por lote; presupuesto GPU 75%.

Se ejecutaron doce configuraciones con 60 escenarios de desarrollo cada una. Detección ejecuta solo extracción; flujo incluye extracción y juicio, API ASGI, auditoría cifrada y proveedor espía simulado. La latencia ASGI excluye TCP/proxy; el smoke sí incluye el acceso HTTP local.

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
| deteccion/slm | 1 | 60 | 0 | 0.938 | 2.276 | 5.176 | — | — |
| deteccion/slm | 5 | 60 | 0 | 0.938 | 11.064 | 13.559 | — | — |
| deteccion/slm | 10 | 60 | 0 | 0.938 | 22.866 | 26.270 | — | — |
| deteccion/hibrido | 1 | 60 | 0 | 1.000 | 2.838 | 5.181 | — | — |
| deteccion/hibrido | 5 | 60 | 0 | 1.000 | 11.394 | 14.314 | — | — |
| deteccion/hibrido | 10 | 60 | 0 | 1.000 | 23.017 | 24.865 | — | — |
| flujo/hibrido | 1 | 60 | 0 | 1.000 | 7.738 | 10.532 | 54 | 60 |
| flujo/hibrido | 5 | 60 | 0 | 1.000 | 37.254 | 40.904 | 54 | 60 |
| flujo/hibrido | 10 | 60 | 0 | 1.000 | 77.323 | 82.301 | 54 | 60 |

## Latencia por etapa del flujo

| Concurrencia | Etapa | Observaciones | p50 s | p95 s |
|---:|---|---:|---:|---:|
| 1 | posprocesamiento_ms | 54 | 0.000 | 0.000 |
| 1 | proveedor_ms | 54 | 0.000 | 0.000 |
| 1 | rag_ms | 60 | 0.311 | 0.369 |
| 1 | regex_ms | 60 | 0.000 | 0.000 |
| 1 | slm_ms | 60 | 7.397 | 10.229 |
| 1 | transformacion_ms | 60 | 0.000 | 0.000 |
| 5 | posprocesamiento_ms | 54 | 0.000 | 0.000 |
| 5 | proveedor_ms | 54 | 0.000 | 0.000 |
| 5 | rag_ms | 60 | 0.322 | 0.781 |
| 5 | regex_ms | 60 | 0.000 | 0.000 |
| 5 | slm_ms | 60 | 36.920 | 40.577 |
| 5 | transformacion_ms | 60 | 0.000 | 0.000 |
| 10 | posprocesamiento_ms | 54 | 0.000 | 0.000 |
| 10 | proveedor_ms | 54 | 0.000 | 0.000 |
| 10 | rag_ms | 60 | 0.323 | 2.186 |
| 10 | regex_ms | 60 | 0.000 | 0.000 |
| 10 | slm_ms | 60 | 76.977 | 81.969 |
| 10 | transformacion_ms | 60 | 0.000 | 0.000 |

Rendimiento del flujo por concurrencia: 1: 0.12 solicitudes/s, 5: 0.14 solicitudes/s, 10: 0.14 solicitudes/s.

Los errores cuentan como omisiones; las categorías y spans deben coincidir exactamente. Detección no exige un juicio de tratamiento y nunca transmite consultas.

## Recuperación, exposición y fallos

- Concurrencia 1: 54 envíos, 6 bloqueos del SLM, 0 fallos técnicos; 0/66 apariciones literales, 0/66 parcialmente visibles.
- Concurrencia 5: 54 envíos, 6 bloqueos del SLM, 0 fallos técnicos; 0/66 apariciones literales, 0/66 parcialmente visibles.
- Concurrencia 10: 54 envíos, 6 bloqueos del SLM, 0 fallos técnicos; 0/66 apariciones literales, 0/66 parcialmente visibles.

Recall@4: 1.000, en doce preguntas jurídicas de desarrollo. Esta métrica mide recuperación documental. La pertinencia de citas y fundamentos requiere revisión aparte. La comprobación de exposición se limita a las apariciones anotadas.

Códigos técnicos (incluido calentamiento): ninguno registrado.

## Recursos observados

VRAM total: media 7151 MiB; máximo muestreado 7240 MiB (incluye escritorio y otras cargas).
- `privateway-pilot-backend-1`: RAM media 197 MiB, máximo 232 MiB; CPU media 4.8 %.
- `privateway-pilot-embeddings-1`: RAM media 1593 MiB, máximo 1620 MiB; CPU media 15.2 %.
- `privateway-pilot-postgres-1`: RAM media 53 MiB, máximo 54 MiB; CPU media 0.7 %.
- `privateway-pilot-proxy-1`: RAM media 15 MiB, máximo 15 MiB; CPU media 0.0 %.
- `privateway-pilot-slm-1`: RAM media 2895 MiB, máximo 2903 MiB; CPU media 93.5 %.
Muestreo aproximado cada diez segundos; no mide picos breves ni energía.

## Reproducibilidad y límites

- Corpus: `ea2b48b25a674191461aa5dbe14355568b311119e724c4596d651aa36c85edc7`.
- Instrucciones SHA-256: `83c481064ed16ef91b39691ad1538de5062a1a85679f264619d61fbf54d3679f`.
- Esquemas de inferencia SHA-256: `7101d234e173a91ba22235c73da19ca4359e84d5ebb02ca113c39007ea7123a5`.
- Dataset SHA-256: `50e7c31e3bc380c88fb40a0ca114d061ea8342599507ea2706293297425b9ab1`.
- Evidencias locales: `pilot/results/20261118-desarrollo-60-v11`.
- Cada repetición usa una carpeta independiente; no se acumulan eventos de ejecuciones anteriores.
- Se conservaron el informe del 14 de noviembre, el modelo anterior y sus revisiones.
- Una pasada por configuración con datos sintéticos no demuestra generalización ni resistencia a toda inyección.
- La utilidad con proveedor externo y la restitución requieren sus propias pruebas.

- Commit base: `9b9af1269b7801f7b87e6af0bd3e3ebe451fc56d`. Árbol de trabajo con cambios locales al iniciar.
