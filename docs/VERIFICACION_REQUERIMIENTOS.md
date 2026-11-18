# Verificación de requisitos de PrivateWay

**Fecha:** 2026-11-17  
**Base revisada:** `docs/requerimientos.md`, rama `codex/fusion-piloto-refinado`  
**Alcance:** prototipo local, interfaz y gateway; no es certificación de seguridad ni cumplimiento legal.

## Resultado ejecutivo

El pipeline de análisis queda definido como **REGEX en paralelo con la rama RAG+SLM**, ambos
partiendo del prompt original. Después de unir los hallazgos, el gateway aplica la política
técnica versionada y calcula acción e IDs tratados; el SLM redacta únicamente la justificación
contextual con referencias RAG. La detección incorrecta es una limitación del SLM, mientras
que la orquestación, el contrato, la validación y los errores de integración son del sistema.

La implementación principal del flujo quedó conectada en esta revisión. No se debe fusionar
a `main` como entrega completa todavía: hay requisitos funcionales explícitos pendientes,
cambios locales sin commit y métricas anteriores que no miden la nueva etapa de juicio final.

## Trazabilidad funcional

| Requisito | Estado | Evidencia / brecha |
|---|---|---|
| E1-HU01 autenticación OIDC y roles | Parcial | El BFF usa OIDC/Keycloak, exige sesión y separa administración por rol. El gateway piloto autentica tokens internos; no valida por sí mismo los tokens OIDC. |
| E1-HU02 consulta protegida por BFF | Cumple en el flujo integrado | La interfaz envía al BFF y este al gateway; la ruta externa pasa por `PipelineProteccion` antes del adaptador. |
| E1-HU03 historial y aislamiento de sesión | Parcial | Conversaciones se separan por propietario y se cifran en PostgreSQL. No hay tabla de correspondencias por sesión ni restitución implementada. |
| E2-HU01 categorías REGEX estructuradas | Parcial | RUN con DV, correo y teléfono chileno. Faltan tarjeta y patente indicadas en el requisito. |
| E2-HU02 detección SLM contextual local | Parcial | La inferencia usa vLLM local y no sale a un proveedor; el rendimiento real por categoría sigue siendo insuficiente y la taxonomía no cubre tarjeta/patente. |
| E2-HU03 ejecución paralela | Cumple | `PipelineHibrido` lanza la rama REGEX y la rama RAG+SLM con `asyncio.gather`; ambas reciben los mensajes originales. RAG es parte de la rama SLM. Hay prueba de sincronización que comprueba solapamiento real. |
| E2-HU04 unión | Parcial | Une por mensaje, categoría y offsets y conserva procedencias coincidentes/discrepantes. El reporte expone confianza desconocida del SLM como `null`; falta especificar y probar una política de normalización de solapamientos/categorías múltiples. |
| E2-HU05 fallo de rama | Cumple en comportamiento de envío | La excepción de cualquiera de las ramas impide una decisión válida; el API falla cerrado y registra la etapa/código disponible. La salida ausente no se convierte en lista vacía. |
| E3-HU01 RAG local versionado | Cumple en el prototipo | Recupera del corpus local, conserva referencias/versiones y falla si no hay evidencia o cambia el índice durante la solicitud. |
| E3-HU02 política de acción y fundamento | Cumple en el flujo principal | La política experimental del gateway calcula acción e IDs; el SLM solo redacta el fundamento contextual con fuentes recuperadas. La política requiere aprobación y no equivale a una conclusión jurídica. |
| E3-HU03 validación antes de ejecutar | Cumple en el flujo principal | Se valida la acción frente a la política, los IDs exactos, las referencias dentro del RAG y el esquema de justificación. Una incoherencia de contrato o referencia inválida impide el envío. |
| E4-HU01 permitir | Cumple | Solo transmite después de validar la decisión; registra transmisión y resultado. |
| E4-HU02 seudonimizar | Parcial | Sustituye spans antes del proveedor y conserva roles; los marcadores son locales a la solicitud. Falta mapa protegido de sesión y restitución. |
| E4-HU03 bloquear | Cumple | Devuelve bloqueo antes de invocar el proveedor; pruebas verifican cero llamadas. |
| E4-HU04 restitución | Pendiente | El pipeline no restituye marcadores de manera controlada; el posprocesamiento REGEX rechaza PII estructurada pero no resuelve la tabla de sesión. |
| E4-HU05 fallo de proveedor | Cumple | Distingue fallo previo, transmisión desconocida y respuesta recibida con posprocesamiento fallido. |
| E5-HU01 ciclo de auditoría | Parcial | JSONL sin prompt en claro, vistas detalladas cifradas y separadas. Debe cerrarse el modelo de retención y la identidad/sesión que se audita en todos los despliegues. |
| E5-HU02 integridad | Parcial | Encadenamiento SHA-256 y verificación completa disponibles. No existe anclaje externo que impida recalcular la cadena a quien controla el archivo. |
| E5-HU03 consulta administrativa | Parcial | Hay endpoint y panel de auditoría protegidos por BFF/rol y token interno; falta revisión de seguridad de extremo a extremo para despliegue real. |
| E6-HU01 configuración | Parcial | Configuración por variables y gestión administrativa de usuarios. No hay administración completa en línea de detectores, modelos, proveedor y límites. |
| E6-HU02 corpus normativo | Parcial | Fuentes, localizadores, hashes y scripts de ingesta versionan el corpus. Falta flujo administrativo de aprobación/activación y revisión jurídica de vigencia. |
| E6-HU03 operación local | Cumple para laboratorio | Compose ejecuta inferencia, embeddings, PostgreSQL y gateway en red local aislada. Descargas de artefactos son una operación separada. |

## Requisitos no funcionales

- **RNF-01/02 privacidad y seguridad:** procesamiento local y secretos separados; contenido de auditoría detallado se cifra aparte. Falta restitución y revisión de despliegue/amenazas antes de producción.
- **RNF-03 trazabilidad:** evento, decisión, referencias, procedencias, tiempos y transmisión se registran; detalles con PII quedan en almacén cifrado. La auditoría es verificable localmente, sin anclaje externo.
- **RNF-04 rendimiento:** hay mediciones por rama, p50/p95/p99 y concurrencias 1/5/10. Debe acordarse un límite de latencia antes de aceptación.
- **RNF-05 calidad:** el evaluador mide exactitud de spans, precisión/recall/F1/F2 micro y macro, exposición y utilidad. Los gates provisionales de exposición/recall/acierto no se cumplen en la última corrida v7.
- **RNF-06 fallo seguro:** la indisponibilidad, timeout, salida inválida, ausencia de evidencia o juicio contradictorio no habilitan transmisión.
- **RNF-07 reproducibilidad:** modelos, corpus, dataset y hashes se registran. Esta revisión amplía el hash de evaluación al prompt de extracción, decisión y fundamento; falta repetir la evaluación con esta configuración.
- **RNF-08 interoperabilidad:** destino seleccionado desde catálogo allowlist y se registra explícitamente.
- **RNF-09 usabilidad:** interfaz presenta estados de bloqueo/error; requiere validación de aceptación con usuarios.

## Evidencia y límites de la revisión

- Backend: `uv run --project backend pytest -q` — 96 pruebas aprobadas en esta revisión.
- Frontend: `node --run test:contracts` — contratos de catálogo, chat, privacidad, auditoría,
  autenticación y administración aprobados.
- La prueba de paralelismo verifica que REGEX comienza antes de terminar la rama contextual;
  pruebas del flujo verifican que una decisión final contradictoria no llame al proveedor.
- Las métricas del informe v7 son **anteriores** a conectar el fundamento final posterior
  a la unión y a calcular la acción en el gateway; no son evidencia de rendimiento de esta versión revisada. Repetir primero smoke
  y cribado de desarrollo con un proveedor simulado, después la matriz local con el SLM real.
- No se ejecutó validación reservada. Las anotaciones sintéticas necesitan revisión humana.

## Preparación para `main`

Antes de abrir/fusionar el cambio a `main`:

1. Revisar y separar los cambios sin commit; `Tesis-Latex/` debe quedar fuera del merge salvo
   que se decida expresamente incluirla.
2. Repetir backend y frontend tras congelar los cambios, comprobar el diff de la rama y dejar
   el árbol limpio.
3. Ejecutar smoke y evaluación de desarrollo con el nuevo juicio final; actualizar informes,
   hashes, versión de protocolo y resultados. No usar todavía validación reservada.
4. Decidir si tarjeta/patente y restitución son alcance de esta entrega o si se ajusta el
   requisito/versionado para declararlos como hitos siguientes.
5. Aprobar la política experimental y los gates de calidad/latencia; revisar RAG y citas con
   una persona competente antes de atribuir fundamento jurídico.

La rama se mantiene separada de `main` hasta cerrar esos puntos.
