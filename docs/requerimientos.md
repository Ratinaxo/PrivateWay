# Documento de requerimientos de PrivateWay

**Versión:** 1.0  
**Estado:** propuesta derivada de la tesis  
**Base:** *PrivateWay*, especialmente sus objetivos, metodología y propuesta de solución.

## 1. Propósito

Este documento convierte la propuesta de tesis en requisitos funcionales y no funcionales expresados como épicas e historias de usuario. PrivateWay es un gateway que analiza consultas textuales antes de enviarlas a un proveedor externo de modelos de lenguaje, aplica una acción de privacidad y permite auditar posteriormente el procesamiento.

La arquitectura corregida ejecuta **REGEX y el SLM local en paralelo** sobre la consulta recibida. Sus hallazgos se reúnen en una etapa de unificación; la recuperación documental aporta contexto para que el SLM formule su decisión. El flujo no espera los resultados REGEX para iniciar el análisis del SLM. La decisión unificada se valida antes de tratar o transmitir la consulta.

## 2. Actores

- **Usuario solicitante:** autentica su sesión y envía consultas por la interfaz conversacional.
- **Administrador:** configura el sistema, gestiona el corpus y consulta auditorías según sus permisos.
- **Proveedor LLM externo:** recibe consultas permitidas o seudonimizadas y devuelve respuestas.
- **Operador del sistema:** mantiene los servicios locales, modelos y conectividad dentro del perímetro administrado.
- **Sistema
## 3. Flujo funcional corregido

1. El gateway recibe la consulta, identifica solicitud y sesión, y la mantiene dentro del entorno local.
2. El orquestador inicia concurrentemente: **(a)** detección determinista mediante REGEX y validaciones de formato, y **(b)** análisis contextual del SLM local sobre la consulta original. La rama SLM puede consultar el corpus legislativo local (RAG) para justificar las decisiones.
3. La etapa de unificación espera los resultados de ambas ramas y consolida los hallazgos por segmento, categoría, posición y procedencia, conservando coincidencias coincidentes y discrepancias. La consolidación no descarta hallazgos de una rama por silencio de la otra.
4. El gateway calcula la acción y los hallazgos que requieren tratamiento mediante una política técnica explícita, versionada y revisable. El SLM recibe la unión y el contexto RAG para redactar una justificación contextual; no puede cambiar la acción ni seleccionar IDs.
5. El gateway valida los hallazgos anclados, la política aplicada, el esquema de la justificación y sus referencias al contexto recuperado. Una salida inválida o una rama requerida no disponible se registra como fallo técnico y no autoriza el envío.
6. Según la acción validada, el gateway permite la consulta, seudonimiza los segmentos seleccionados o bloquea la transmisión. Solo las dos primeras rutas contactan al proveedor externo.
7. Si aplica, el gateway restituye en la respuesta únicamente los marcadores válidos presentes que correspondan a la sesión. Registra decisión y ejecución en una bitácora separada de la tabla protegida de correspondencias.

**Esquema:** `Recepción → [REGEX ∥ SLM (+ RAG local)] → Unificación de hallazgos → Política versionada del gateway + justificación contextual SLM → Validación → Tratamiento → (proveedor externo si permitido) → Restitución si corresponde → Entrega y auditoría`.

## 4. Épicas e historias de usuario

### Épica E1 — Acceso y consulta protegida

**E1-HU01 — Autenticar usuario.** Como usuario solicitante, quiero acceder mediante la identidad corporativa para que mis solicitudes estén asociadas a una sesión autenticada.  
**Aceptación:** se valida la identidad por OpenID Connect; las rutas protegidas rechazan sesiones ausentes o inválidas; se aplican roles autorizados.

**E1-HU02 — Enviar consulta al gateway.** Como usuario autenticado, quiero conversar desde una interfaz unificada para que mis consultas pasen por los controles de PrivateWay antes de alcanzar un LLM externo.  
**Aceptación:** cada solicitud obtiene identificador de solicitud y sesión; la consulta no se envía directamente desde el cliente al proveedor; la interfaz muestra la respuesta o el resultado de bloqueo/fallo.

**E1-HU03 — Mantener contexto de sesión.** Como usuario, quiero conservar el contexto de mi conversación dentro de la sesión para continuar la tarea.  
**Aceptación:** el alcance de historial se limita a la sesión autorizada; las correspondencias de seudónimos no se comparten entre sesiones. El soporte de archivos y respuestas progresivas queda fuera del alcance inicial.

### Épica E2 — Detección concurrente y unificación

**E2-HU01 — Detectar identificadores estructurados.** Como responsable de privacidad, quiero que REGEX identifique datos con formatos reconocibles para localizar identificadores antes del envío.  
**Aceptación:** se reconocen las categorías estructuradas definidas para el prototipo (RUN, correo, teléfono, tarjeta y patente); se registran límites, categoría, procedencia y verificaciones aplicables; las validaciones de RUN y tarjeta verifican consistencia de formato, no existencia ni titularidad.

**E2-HU02 — Detectar datos contextuales.** Como responsable de privacidad, quiero que un SLM ejecutado localmente identifique datos personales y sensibles dependientes del contexto.  
**Aceptación:** el SLM analiza la consulta aunque REGEX no encuentre coincidencias; cubre las categorías definidas en la taxonomía de la tesis; emite hallazgos estructurados y no transmite la consulta a servicios externos durante la inferencia.

**E2-HU03 — Ejecutar detectores en paralelo.** Como operador, quiero que REGEX y SLM comiencen a analizar la misma consulta de forma concurrente para reducir la dependencia secuencial entre detectores.  
**Aceptación:** ambos detectores reciben la consulta original desde la recepción; el inicio de una rama no depende de que la otra termine; se miden duración por rama y latencia total; ninguna rama modifica la entrada de la otra.

**E2-HU04 — Unificar hallazgos.** Como decisor del tratamiento, quiero consolidar los resultados de REGEX y SLM para decidir con evidencia de ambas técnicas.  
**Aceptación:** la salida conserva offsets, categoría, confianza disponible y procedencia; coincidencias superpuestas se normalizan con reglas documentadas; se preservan discrepancias y hallazgos exclusivos de cada rama; una coincidencia REGEX no se elimina por ausencia en SLM ni viceversa.

**E2-HU05 — Gestionar fallos de detección.** Como operador, quiero detectar si una rama falla o excede su tiempo límite para impedir que una ejecución incompleta se trate como análisis satisfactorio.  
**Aceptación:** se registra rama, tipo de fallo y tiempo; no se interpreta salida ausente como lista vacía; el comportamiento de detención ante fallo es seguro y queda configurado/documentado; no se transmite contenido sin una decisión válida.

### Épica E3 — Contexto normativo y decisión

**E3-HU01 — Recuperar fuentes normativas.** Como componente de justificación, quiero recibir fragmentos pertinentes del corpus local para contextualizar los hallazgos sin convertir una clasificación en una conclusión jurídica.
**Aceptación:** cada fragmento incluye identificador, localizador y versión/estado temporal; la recuperación solo utiliza el corpus administrado; corpus vacío o recuperación sin resultados se indica explícitamente.

**E3-HU02 — Aplicar acción de tratamiento.** Como gateway, quiero calcular una decisión estructurada sobre la unión de hallazgos para aplicar una política consistente sin delegar una regla determinista al SLM.
**Aceptación:** las acciones admitidas son `permitir`, `seudonimizar` y `bloquear`; la política versionada determina acción e IDs tratados; el SLM no decide ni selecciona IDs; la justificación breve distingue el criterio técnico del fundamento jurídico y cita solo referencias recuperadas; la clasificación de un dato por sí sola no determina automáticamente la acción.

**E3-HU03 — Validar tratamiento antes de ejecutarlo.** Como operador, quiero que el gateway valide la acción calculada y la justificación antes de aplicarlas para evitar ejecutar una respuesta mal formada o incongruente.
**Aceptación:** se valida la acción e IDs calculados por la política, los segmentos con respecto a la consulta y el esquema y referencias de la justificación; una salida inválida produce fallo técnico, no una acción implícita.

### Épica E4 — Aplicar protección y conectar con proveedores

**E4-HU01 — Permitir consulta.** Como usuario, quiero que una consulta sin tratamiento adicional pueda enviarse al proveedor cuando la decisión validada sea permitir.  
**Aceptación:** se transmite solo tras validación; se registra destino y resultado de transmisión; se conserva la distinción entre decisión y acción efectivamente ejecutada.

**E4-HU02 — Seudonimizar consulta.** Como usuario, quiero que los segmentos seleccionados se sustituyan por marcadores tipados antes del envío para limitar la exposición de valores originales.  
**Aceptación:** los marcadores mantienen categoría y unicidad dentro de la sesión; la tabla de correspondencias queda local, protegida y separada de auditoría; solo se transmite el texto transformado.

**E4-HU03 — Bloquear consulta.** Como responsable de privacidad, quiero impedir el envío cuando la decisión validada sea bloquear.  
**Aceptación:** no hay llamada al proveedor externo; se comunica el resultado al usuario y se registra el motivo sin guardar la consulta original en claro en la bitácora.

**E4-HU04 — Restituir respuesta.** Como usuario, quiero recibir los valores de mi sesión donde la respuesta externa reproduzca marcadores válidos.  
**Aceptación:** solo se restituyen marcadores presentes, válidos y pertenecientes a la sesión; los desconocidos, alterados o de otra sesión no se resuelven; la ausencia de un marcador no impide entregar el resto de la respuesta.

**E4-HU05 — Gestionar fallos de proveedor.** Como usuario, quiero recibir una indicación clara si el proveedor falla después de una consulta autorizada.  
**Aceptación:** el fallo y el destino quedan auditados; no se confunde con un bloqueo emitido por el SLM; no se restituyen marcadores inválidos.

### Épica E5 — Auditoría y trazabilidad

**E5-HU01 — Registrar eventos de ciclo de vida.** Como auditor, quiero reconstruir qué decidió y ejecutó el gateway para revisar el procesamiento.  
**Aceptación:** se registran solicitud/sesión seudonimizadas, tiempos por etapa, procedencia de hallazgos, decisión, referencias normativas, tratamiento ejecutado, transmisión, restitución y fallos; se distinguen decisión del SLM y resultado real; no se almacenan consultas completas originales en claro.

**E5-HU02 — Proteger integridad de la bitácora.** Como administrador, quiero que los eventos sean de solo inserción y verificables para detectar alteración o eliminación.  
**Aceptación:** los registros se encadenan mediante resúmenes criptográficos; existe mecanismo de verificación que informa inconsistencias.

**E5-HU03 — Consultar auditoría.** Como administrador autorizado, quiero filtrar y revisar eventos desde un panel para analizar decisiones y fallos.  
**Aceptación:** acceso basado en rol; filtros por periodo, acción, estado y destino; la vista evita exponer valores personales originales y mantiene separado el acceso a correspondencias.

### Épica E6 — Administración y operación local

**E6-HU01 — Configurar componentes.** Como administrador, quiero gestionar la configuración de detectores, SLM, proveedor y límites operativos para adaptar la instalación.  
**Aceptación:** cambios se restringen por rol y se registran; secretos no aparecen en auditoría; se informa estado de disponibilidad de dependencias.

**E6-HU02 — Gestionar corpus normativo.** Como administrador, quiero actualizar y versionar documentos oficiales para mantener trazable la base de recuperación.  
**Aceptación:** cada versión registra fuente y fecha; los fragmentos son identificables; la activación de una versión permite conocer qué texto respaldó cada decisión.

**E6-HU03 — Operar análisis localmente.** Como operador, quiero ejecutar detección, inferencia y recuperación dentro del perímetro local para limitar la exposición.  
**Aceptación:** consultas, hallazgos y correspondencias no salen a servicios auxiliares externos; solo se transmite al destino configurado el contenido posterior al tratamiento; las descargas/actualizaciones se distinguen del procesamiento de solicitudes.

## 5. Requisitos no funcionales

- **RNF-01 Privacidad por diseño:** no persistir texto original completo en la bitácora; proteger correspondencias y restringirlas a la sesión autorizada.
- **RNF-02 Seguridad:** autenticar usuarios, aplicar autorización por rol, proteger secretos y cifrar las correspondencias almacenadas.
- **RNF-03 Trazabilidad:** poder relacionar evento, hallazgos, juicio, fuentes recuperadas y ejecución mediante identificadores, sin revelar valores originales.
- **RNF-04 Rendimiento medible:** informar latencia p50 y p95 del flujo completo y por etapa, incluida la concurrencia de detectores; evaluar configuración con 1, 5 y 10 consultas concurrentes. La tesis no fija un umbral de aceptación, por lo que debe acordarse antes de la evaluación final.
- **RNF-05 Calidad de detección:** evaluar precisión, recall, F1 y F2, agregados micro y macro, con coincidencia exacta de límites y categoría; reportar exposición residual y utilidad por separado.
- **RNF-06 Disponibilidad y fallo seguro:** errores de formato, indisponibilidad, timeout o ausencia de evidencia deben ser distinguibles y no habilitar transmisión de forma implícita.
- **RNF-07 Mantenibilidad y reproducibilidad:** versionar configuración, modelo, corpus e índice usados en cada evaluación; documentar parámetros y taxonomía.
- **RNF-08 Interoperabilidad:** encapsular la integración con destinos LLM para identificar explícitamente qué proveedor recibe cada consulta.
- **RNF-09 Usabilidad:** presentar al usuario respuesta, bloqueo o fallo de forma comprensible; no exponer detalles internos sensibles.

## 6. Fuera de alcance de la primera entrega

- Interceptar tráfico de aplicaciones ajenas a las integraciones configuradas.
- Procesar archivos adjuntos o garantizar compatibilidad con respuestas progresivas.
- Aprobación humana previa de cada consulta.
- Afirmar cumplimiento jurídico integral o que una detección garantiza anonimización o ausencia de reidentificación.
- Usar datos institucionales reales sin definir procedencia, base de licitud, acceso y eliminación.

## 7. Criterios de evaluación y trazabilidad

La evaluación debe separar la calidad intrínseca de cada detector del comportamiento del flujo completo. Comparará REGEX, SLM e híbrido sobre consultas y anotaciones comunes; la variante híbrida corresponde a la unión/unificación de detectores concurrentes. Para el flujo se reportarán detección, exposición residual, utilidad, latencia, errores, bloqueos y consultas efectivamente transmitidas. Las métricas de privacidad no se inferirán solo de las decisiones del modelo.

Cada historia deberá vincularse a pruebas funcionales y evidencia. Como mínimo, se probarán: ejecución paralela verificable; hallazgos coincidentes, superpuestos y discrepantes; consulta sin coincidencias REGEX; falla de cada rama; referencias inexistentes; salida inválida; cada una de las tres acciones; restitución válida/ausente/alterada/cruzada entre sesiones; y eventos de auditoría correspondientes.

## 8. Supuestos y decisiones pendientes

La tesis describe una propuesta conceptual y no acredita por sí sola eficacia experimental. Los umbrales de latencia/calidad, estrategia de solapamientos, timeout y conducta exacta ante fallo de una rama, plazos de conservación, retención de correspondencias, reglas operativas para elegir acción y versiones definitivas de modelo e infraestructura deben fijarse antes de la evaluación final. La ejecución paralela es el requisito arquitectónico de esta especificación y reemplaza la secuencia REGEX → RAG → SLM presentada en partes de la tesis.
