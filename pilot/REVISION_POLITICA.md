# Revisión pendiente de política y explicación

Documento de preparación para revisión por una persona competente en protección de datos y
derecho chileno. No expresa una conclusión jurídica ni sustituye esa revisión.

## Regla técnica actualmente evaluada

| Hallazgos del detector | Acción del piloto |
|---|---|
| Ninguno de los seis tipos cubiertos | Permitir |
| RUN, correo, teléfono, persona o dirección | Reemplazar por marcadores locales |
| Salud asociada explícitamente a una persona | Bloquear |
| Salud sin asociación personal | Reemplazar por marcador local |

La regla experimental v2 se aplica después de combinar REGEX y SLM. La decisión es del
gateway; el SLM informa si un dato de salud está asociado a una persona y redacta el
fundamento, pero no cambia la acción. La recuperación de artículos es contextual y no deriva
esta regla. El resultado del sistema no determina si un tratamiento es lícito.

## Preguntas para la revisión

1. ¿La regla experimental v2 —bloquear salud asociada a una persona y seudonimizar salud
   genérica— es adecuada como control de riesgo del producto? ¿Qué evidencia permite
   establecer esa asociación y qué revisión humana requiere?
2. ¿Qué condiciones debe cumplir el reemplazo con marcadores para llamarlo
   «seudonimización»? El piloto no implementa restitución y no conserva una tabla persistente
   de correspondencias; validar si el término debe cambiarse en interfaces e informe.
3. ¿Qué consecuencias operativas corresponden a las demás categorías y qué casos legítimos
   requieren permitir, transformar o derivar a revisión humana?
4. ¿Qué texto y referencias pueden mostrarse al usuario sin presentar la política del piloto
   como mandato legal ni confundir normas futuras con el texto aplicable en la fecha?
5. ¿Qué fuentes, versiones, fecha de vigencia, jurisdicción y responsable deben quedar
   registrados para cada regla aprobada?

## Material revisado por el piloto

El manifiesto [`corpus/manifest.json`](corpus/manifest.json) registra XML de BCN para la Ley
19.628 como texto base y la Ley 21.719 con reformas seleccionadas marcadas con vigencia
diferida al 2026-12-01. Los fragmentos tienen localizadores, versión, estado y hash. El
revisor debe verificar las versiones y vigencias aplicables a la fecha en que se evalúe o
despliegue el producto.

## Aprobación pendiente

| Campo | Estado |
|---|---|
| Revisor/a y competencia | Pendiente |
| Fecha de revisión | Pendiente |
| Regla aprobada y alcance | Pendiente |
| Fuentes y versiones confirmadas | Pendiente |
| Texto de explicación autorizado | Pendiente |

Hasta completar esta revisión, la traza del gateway califica su explicación como regla
técnica experimental, marca `fundamento_juridico: false` y separa las referencias RAG como
contexto documental.
