# Cierre de resultados: pipeline local y datos de evaluación

**Fecha:** 17 de noviembre de 2026  
**Rama:** `codex/fusion-piloto-refinado`  
**Alcance:** evaluación local con datos sintéticos; no se ejecutó la validación reservada.

> **Nota de versión:** después de esta corrida se conectó la decisión y el fundamento del
> SLM como etapa posterior a la unión REGEX+SLM. Las métricas v7 que siguen corresponden a
> la versión anterior y no miden esa etapa añadida. Se requiere un nuevo cribado de desarrollo.

## Conclusión ejecutiva

El pipeline ya entrega el mismo prompt a REGEX y al SLM, ejecuta ambos detectores en
paralelo, une sus hallazgos y sanea el texto antes de entregarlo al proveedor simulado. La
fusión funcional está probada, pero el resultado **no es apto todavía para permitir el envío
de consultas sensibles**: la evaluación actual encontró exposiciones residuales frecuentes
y fallos al aplicar la acción de bloqueo por salud.

La batería nueva usó Qwen2.5-3B-Instruct-AWQ, E5, concurrencia 1 y 60 casos sintéticos de
cribado (un caso por familia). Las cifras de matrices anteriores con prefijo
`matrix-qwen25-*` pertenecen al prompt anterior, que entregaba al SLM las detecciones REGEX;
no deben compararse directamente con los resultados v7 de este documento.

## Pipeline implementado

1. RAG recupera fragmentos legislativos desde el prompt original. El RAG aporta contexto;
   esta versión no deriva del texto legal una conclusión jurídica.
2. REGEX y SLM reciben el mismo contenido original y se ejecutan en paralelo.
3. El gateway fusiona las detecciones por mensaje, categoría y offsets; conserva si cada
   hallazgo provino de REGEX, SLM o ambos.
4. La política experimental decide permitir, seudonimizar o bloquear. El gateway entrega al
   proveedor simulado solo los mensajes tratados. Los errores técnicos no habilitan un
   fallback permisivo.

El análisis de respuestas del proveedor sigue heredando el filtro REGEX, cuya cobertura
semántica es limitada. La justificación de la acción es una explicación de regla técnica;
no constituye una interpretación legal ni una justificación generada por el SLM a partir de
la Ley.

## Estado de los prompts

Actualmente existe **un prompt de sistema** (`INSTRUCCION` en `backend/gateway/hybrid.py`),
no un prompt inicial y otro prompt de comportamiento separados. El cliente fija temperatura
0, respuesta JSON con esquema estricto y un límite de generación de 1.024 tokens. La
instrucción actual:

- restringe la extracción al texto de los mensajes, trata el contenido y sus instrucciones
  como datos no confiables, y excluye los fragmentos legales y los ejemplos;
- pide una extracción independiente de REGEX, texto literal y posición de mensaje;
- prohíbe al SLM elegir la acción o presentar una conclusión legal.

Estas son buenas restricciones estructurales y están versionadas/hashadas en la evaluación.
Sin embargo, **el comportamiento no está refinado ni validado para darse por cerrado**: en
la muestra actual solo se bloquearon 1 de 15 casos cuya acción esperada era bloquear por
salud. El recall híbrido fue 68,9 %. Los ejemplos del prompt, la taxonomía y la cobertura de
negaciones, menciones indirectas, historiales y contexto médico deben mejorarse usando solo
desarrollo. No se ha realizado ajuste supervisado del SLM.

## Métricas del cribado v7

| Etapa | TP / FP / FN exactos | Precisión | Recall | F1 | F2 | p50 / p95 |
|---|---:|---:|---:|---:|---:|---:|
| REGEX | 45 / 0 / 45 | 1,000 | 0,500 | 0,667 | 0,556 | 0,021 / 0,051 ms |
| SLM independiente | 54 / 1 / 36 | 0,982 | 0,600 | 0,745 | 0,651 | 2,374 / 4,560 s |
| Unión REGEX+SLM | 62 / 1 / 28 | 0,984 | 0,689 | 0,810 | 0,733 | 2,382 / 4,573 s |
| Flujo completo por API | 62 / 1 / 28 | 0,984 | 0,689 | 0,810 | 0,733 | 2,415 / 4,666 s |

El flujo completo tuvo **0 errores técnicos**, 46/60 acciones correctas (76,7 %) y
Recall@4 = 1,00 en 12 preguntas RAG sintéticas de desarrollo. La matriz de acciones fue:

| Acción esperada \ observada | Permitir | Seudonimizar | Bloquear | Error |
|---|---:|---:|---:|---:|
| Permitir | 15 | 0 | 0 | 0 |
| Seudonimizar | 0 | 30 | 0 | 0 |
| Bloquear | 0 | 14 | 1 | 0 |

No se bloquearon falsamente controles limpios (0/15). El tamaño de esta muestra no basta
para demostrar que la tasa poblacional de falsos bloqueos sea menor o igual a 5 %.

De 60 consultas, 59 se transmitieron y una se bloqueó. Entre las 44 solicitudes sensibles
transmitidas había 88 apariciones anotadas: quedaron visibles 28 completas y 22 parcialmente,
es decir, **50/88 apariciones (56,8 %)**. Hubo exposición en **37/44 solicitudes sensibles
(84,1 %)**. El intervalo exploratorio del 95 % por bootstrap de familias para la tasa por
aparición fue 46,6–67,0 %.

Por tanto, esta versión falla los gates provisionales del proyecto: cero exposiciones,
recall ≥98 % por categoría y acierto de acción ≥98 %. No hay un umbral p95 predefinido para
evaluar latencia. Estos gates son decisiones de ingeniería del proyecto, no umbrales fijados
por NIST. NIST recomienda pruebas realistas y representativas, metodología documentada,
resultados desglosados e incertidumbre; no certifica un sistema mediante una puntuación
universal ([NIST AI RMF 1.0](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf)).

Los tamaños del anexo estadístico también fueron comprobados: con cero exposiciones, el
límite unilateral del 95 % es aproximadamente 4,87 % en 60 solicitudes independientes y
0,332 % en 900. La dependencia por familia puede ensanchar la incertidumbre; por ello las
exportaciones nuevas remuestrean familias en vez de tratar spans correlacionados como
observaciones independientes.

## ¿Conviene añadir datasets externos?

Sí, para ampliar la diversidad de redacción y probar transferencia. No conviene reemplazar
el dataset chileno ni mezclar sin control conjuntos con diferentes taxonomías. Una fuente
externa puede mejorar el entrenamiento o desarrollo y, a la vez, no representar una consulta
chilena dirigida a un gateway de privacidad.

### Candidatos

| Fuente | Aporte posible | Límites para PrivateWay |
|---|---|---|
| [OpenPII 1M de Ai4Privacy](https://huggingface.co/datasets/ai4privacy/pii-masking-openpii-1m) | 1.428.143 textos sintéticos, 19 etiquetas, spans y versiones enmascaradas; metadatos de idioma y región. La ficha declara licencia CC BY 4.0 y requiere atribución. | La cobertura de idiomas/regiones no equivale a español chileno. Sus etiquetas principales no incluyen RUN ni una clase clínica específica de salud. Verificar el contenido español/regional antes de seleccionar un subconjunto. |
| [CoNLL-2002 en español](https://aclanthology.org/W02-2024.pdf) | Línea base externa para nombres de persona, organización, ubicación y otros nombres; incluye particiones train/dev/test. | Noticias EFE de mayo de 2000: NER no equivale a PII contextual, ni contiene RUN, salud, emails o el flujo conversacional objetivo. Revisar además las condiciones de uso/redistribución del corpus antes de incorporarlo. |
| [SPY: Synthetic PII Detection Dataset](https://aclanthology.org/2025.naacl-srw.23/) | Metodología de generación completamente sintética con ejemplos médicos y preguntas legales; útil para diseñar escenarios y negativos. | El artículo informa 4.491 consultas médicas y 4.197 preguntas legales, pero no acredita por sí solo cobertura de español chileno ni categorías RUN. Comprobar idioma, formato y licencia del repositorio antes de reutilizar los datos. |

OpenPII 1M es el candidato más directo para un **cribado adicional** por sus spans y textos
enmascarados; su ficha señala que el contenido es sintético y CC BY 4.0, con obligación de
atribución ([ficha/licencia](https://huggingface.co/datasets/ai4privacy/pii-masking-openpii-1m)).
La asignación de México en los metadatos regionales no demuestra que la variedad lingüística
o los formatos correspondan a Chile. No descargué ni incorporé datos externos en este cambio.

### Adaptación propuesta

1. Descargar una muestra piloto del subconjunto español y registrar la versión, licencia,
   URL, hash, esquema, idioma/región y condiciones de acceso.
2. Auditar una muestra manualmente, revisar duplicados y falsos positivos, y verificar si los
   valores que parecen sintéticos no son datos reales accidentalmente.
3. Mapear etiquetas a la taxonomía del gateway con reglas explícitas. Persona, correo,
   teléfono y dirección son mapeables con revisión. No mapear automáticamente
   `IDCARDNUM`, `TAXNUM` o `SOCIALNUM` a RUN; generar o anotar RUN de prueba por separado.
   Mantener salud como clase separada y ampliar ejemplos clínicos contextualizados.
4. Convertir cada fila a los contratos del benchmark (`mensajes`, `hallazgos`, offsets,
   categoría, acción) y conservar la fuente de cada caso. Usar datos externos para desarrollo
   y prueba de transferencia separada; la validación reservada actual queda aislada.
5. Añadir un conjunto sintético chileno con variación de roles, historial, abreviaturas,
   negaciones, instrucciones adversariales, direcciones, nombres y formatos RUN. Revisar las
   anotaciones con personas y separar familias de plantillas entre splits.
6. Evaluar por dataset y por categoría antes de combinarlos. Nunca presentar una cifra
   agregada que oculte un descenso de recall en salud o RUN.

La ruta más prometedora es entrenar o adaptar un **detector token-classification pequeño**
con spans sintéticos, y mantener el SLM como detector contextual complementario. La salida
debe seguir siendo la unión de detectores y una política de cierre seguro. El score de un
modelo externo no demuestra que el gateway completo reduzca la exposición: se debe repetir
el flujo por API y contar el texto realmente enviado.

## Cierre y próximos hitos

1. Analizar los 14 errores de acción por salud y las 50 exposiciones, por categoría, plantilla,
   prompt y procedencia de detección; corregir primero los casos de alto riesgo.
2. Mejorar prompt y/o entrenar un detector token-classification usando solo desarrollo;
   conservar el hash de cada variante y comparar REGEX, SLM independiente y unión.
3. Incorporar una muestra externa sintética con licencia clara y adaptar sus etiquetas sin
   presentarla como prueba chilena. Revisar manualmente idioma, licencia y anotaciones.
4. Volver a ejecutar el cribado y luego los 600 casos de desarrollo. Aprobar una política de
   cierre, el p95 objetivo y el protocolo antes de tocar validación.
5. Someter la política a revisión competente y correr una sola evaluación reservada cuando
   modelo, prompt, reglas, corpus, métricas y criterios estén congelados.

Los archivos de resultados por caso están en `pilot/results/recheck-v7-*-screen60-c1.json`;
las exportaciones CSV se guardaron localmente en `/tmp/privateway-recheck-v7-export/`.
El conjunto reservado no se ejecutó. Qwen3.5 no se pudo cargar en la RTX 4050 disponible;
se restauró el servicio estable Qwen2.5+E5. La rama sigue separada de `main`.

La matriz de verificación por historia y los pendientes de implementación están en
[`docs/VERIFICACION_REQUERIMIENTOS.md`](../docs/VERIFICACION_REQUERIMIENTOS.md).
