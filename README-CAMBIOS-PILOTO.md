# Cambios del piloto vLLM + RAG

Actualización posterior: ver [correcciones y repetición de pruebas del 17 de noviembre](README-CORRECCIONES-PRUEBAS.md).

Estado al 14 de noviembre de 2026: infraestructura e integración implementadas y probadas.
La configuración actual del modelo todavía no alcanza calidad suficiente para el flujo funcional.

## Qué se agregó

- Laboratorio Docker Compose independiente con vLLM, embeddings E5 en CPU, PostgreSQL/pgvector,
  gateway y proxy de entrada en `127.0.0.1:8082`.
- Qwen2.5-3B-Instruct-AWQ con kernel AWQ-Marlin, contexto de 4096 tokens, salida máxima de
  1024 tokens, temperatura 0 y una generación simultánea, probado en una RTX 3070 de 8 GB.
- Descarga previa de modelos con revisiones y hashes registrados; operación en red interna
  con pesos de solo lectura y proveedor de destino exclusivamente simulado.
- Corpus legislativo oficial de BCN, con fuente, localizador, versión, hash y estado temporal.
  La preparación conserva el texto base de la Ley 19.628 y extrae las disposiciones reformadas
  desde la Ley 21.719, sin presentar el XML antiguo como un consolidado futuro.
- Ingesta idempotente y activación transaccional del índice; recuperación exacta top-4 mediante
  embeddings normalizados multilingual-e5-large de 1024 dimensiones.
- Pipeline `REGEX → RAG → SLM → validación → tratamiento`, aplicado también al historial.
- Cobertura inicial de RUN, correo, teléfono, persona, dirección y salud. El SLM propone
  entidades contextuales; el gateway calcula offsets, agrega REGEX y aplica el criterio experimental.
- Controles de esquema, offsets derivados por código, registro de fragmentos y conservación de hallazgos REGEX. Los errores
  detienen el envío; el modo híbrido no vuelve automáticamente al modo REGEX.
- Motivos y trazas en auditoría cifrada, con reglas experimentales diferenciadas de las
  referencias jurídicas contextuales; códigos de fallo técnico y readiness que
  comprueba modelo, embeddings, base de datos y corpus activo.
- Evaluador de detección y de flujo por la API, proveedor espía simulado y captura de recursos.
  Se prepararon 120 consultas sintéticas y 24 preguntas de recuperación.

Las interfaces públicas de chat se mantienen. El laboratorio no duplica frontend ni Keycloak;
expone la API del gateway para las pruebas. El despliegue anterior continúa usando REGEX
cuando no se activa expresamente el laboratorio híbrido.

## Validación y resultados

- **76 pruebas del backend aprobadas** y batería de contratos del frontend aprobada.
- Ingesta repetida verificada: mismo índice y 12 fragmentos derivados de 11 unidades legislativas.
- Doce configuraciones medidas sobre diez escenarios de desarrollo: tres detectores y flujo
  híbrido, con concurrencias 1, 5 y 10. La validación reservada permanece sin ejecutar.
- Recuperación: artículo/letra esperado presente en el top-4 de las doce preguntas jurídicas
  de desarrollo. Esta medición no valida la pertinencia de las fuentes en cada decisión del gateway.
- Detección híbrida: F2 micro de 0,439, igual a REGEX en este lote, con mayor latencia.
- Flujo completo: **9 fallos técnicos de 10 consultas en cada concurrencia**, por offsets
  inválidos o acciones incoherentes. El único envío de cada configuración fue un control
  negativo sin PII. No corresponde interpretar esto como eficacia de protección demostrada.

El detalle de latencias, recursos y errores está en [el informe del piloto](pilot/REPORT.md).
Los resultados son preliminares, con datos sintéticos y una pasada por configuración.
Después de esa medición se simplificó el contrato de salida. En una corrida posterior del
contrato `piloto-v3` sobre los diez primeros casos de desarrollo, regex obtuvo F2 0,439,
SLM 0,238 e híbrido 0,397. El flujo híbrido tuvo cinco transmisiones, cuatro bloqueos y un
fallo técnico por configuración; una aparición anotada quedó visible en el envío de
`desarrollo_7_0`. Los tres smoke tests por HTTP devolvieron 503. Esta corrida confirma que
esa versión todavía no es apta para uso funcional.

La iteración `piloto-v4` eliminó la asociación de salud y las citas y justificaciones que
generaba el SLM, causas registradas como `SLM_SALUD_AMBIGUA`, `SLM_ASOCIACION_INVALIDA` y
`SLM_SALIDA_INCOMPLETA`. `piloto-v5` añadió ejemplos de formato para nombre y salud y se midió
en la corrida siguiente.

## Corrida de desarrollo del contrato `piloto-v5`

En los primeros diez casos, y con cero errores técnicos, REGEX obtuvo F2 0,439; SLM F2
0,431 (precisión 0,833; recall 0,385); e híbrido F2 0,873 (precisión 1,000; recall 0,846).
El flujo híbrido transmitió los diez casos, acertó ocho acciones y dejó dos spans anotados
visibles: una dirección en `desarrollo_5_0` y el dato de salud en `desarrollo_6_0`. El smoke
HTTP pasó sus tres ejemplos, pero el conjunto también muestra que el contexto «Resume este
texto» degrada la extracción de dirección y salud. La validación reservada sigue intacta.

El prompt `piloto-v6` añade ejemplos sintéticos de dirección y de hallazgos con ese prefijo.
Es una hipótesis de mejora aún sin medir; el flujo no se considera listo mientras no se
reduzca a cero la exposición en desarrollo y mejore la exactitud de acciones.

## Cómo reproducirlo

Seguir [README-pilot.md](README-pilot.md) para preparar los secretos locales, descargar los
modelos, obtener el corpus, construir los servicios, indexar y ejecutar las pruebas.

Archivos principales:

| Área | Ubicación |
|---|---|
| Despliegue del laboratorio | `compose.pilot.yaml` |
| Pipeline, clientes, RAG y evaluadores | `backend/src/backend/gateway/` |
| Servicio de embeddings | `services/embeddings/` |
| Preparación y ejecución | `scripts/` |
| Corpus, datos sintéticos y versiones | `pilot/` |
| Pruebas nuevas | `backend/tests/test_hybrid.py`, `test_slm.py`, `test_rag.py`, `test_pilot_data.py` |

Los secretos `.env.pilot`, pesos de modelos, entornos virtuales, dependencias instaladas,
XML originales descargados y resultados detallados permanecen fuera de Git. Se versionan
los manifiestos, hashes, datos sintéticos, código, pruebas y resumen de resultados.
Las correcciones del informe académico `main-9.md` están fuera de este repositorio.

## Punto para retomar

1. Revisar los fallos de extracción y coherencia del SLM con datos de desarrollo.
2. Contrastar simplificación del contrato y otro modelo candidato que quepa en el equipo.
3. Evaluar las fuentes recuperadas para consultas empresariales, además de preguntas jurídicas.
4. Revisar las anotaciones y ampliar a los 60 casos de desarrollo antes de usar validación reservada.

La restitución de valores por sesión, el proveedor externo real, la taxonomía completa y la
evaluación final de utilidad corresponden al siguiente hito. La configuración actual no se
acepta todavía para uso funcional con datos reales.
