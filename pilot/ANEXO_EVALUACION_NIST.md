# Anexo para la tesis: evaluación del gateway con el marco NIST

## Alcance y relación con NIST

El NIST AI Risk Management Framework (AI RMF 1.0) no fija un umbral universal que certifique
que un modelo o gateway sea «bueno». Plantea la validación como evidencia objetiva de que un
sistema satisface los requisitos de un uso concreto. También señala que las mediciones de
exactitud deben acompañarse de conjuntos de prueba realistas y representativos, de una
metodología documentada y, cuando corresponda, de resultados desglosados por segmentos. La
robustez debe considerarse frente a condiciones variadas y fallos que puedan causar daños.
[NIST AI RMF 1.0, sección 3.1](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf)

Por tanto, los umbrales y tamaños que se proponen aquí son criterios de ingeniería para el
piloto PrivateWay; no son requisitos publicados por NIST ni una certificación de conformidad.
El riesgo relevante es que un dato personal anotado llegue sin tratamiento al proveedor
simulado, junto con los falsos bloqueos, fallos técnicos, latencia y diferencias entre
categorías.

## Unidad de análisis y métricas

La evaluación usa dos unidades relacionadas:

1. **Solicitud independiente** para medir si el gateway permite, seudonimiza o bloquea la
   operación, si transmite y si ocurre una exposición.
2. **Span anotado** para medir detección exacta por categoría, precisión, recall y F1/F2
   micro y macro; el solapamiento parcial se informa por separado.

Los spans de una misma solicitud y las solicitudes generadas desde una misma plantilla no
son observaciones plenamente independientes. Los intervalos para métricas agregadas deben
remuestrear por solicitud o familia de plantilla, no tratar cada span como si procediera de
una persona o contexto independiente.

El informe debe presentar, al menos:

- precisión, recall y F1/F2 exactos y parciales por categoría, micro y macro;
- número de spans no detectados que quedaron visibles en los mensajes enviados;
- exposición por solicitud sensible transmitida y número absoluto de exposiciones;
- acierto de acción, matriz de confusión y falsos bloqueos en controles limpios;
- fallos técnicos y decisiones de cierre seguro por separado;
- latencia p50/p95/p99 y resultados por concurrencia.

Una puntuación F2 alta no compensa una exposición no detectada. Para el objetivo de
confidencialidad, una exposición anotada en el conjunto reservado es un fallo del criterio
de salida, aunque el promedio global siga siendo alto.

La implementación del piloto define como exposición exacta el valor normalizado completo
visible en el texto enviado. Se considera exposición parcial si sobrevive un token corto
completo o cualquier secuencia alfanumérica contigua de cuatro caracteres de un span más
largo. Esta regla es conservadora y puede contar coincidencias casuales; sus resultados
exactos y parciales se informan por separado. La métrica de detección parcial, a su vez,
empareja spans de igual mensaje y categoría que se solapan, con correspondencia uno a uno;
no reemplaza la coincidencia exacta como métrica primaria de protección.

Para los intervalos de métricas por categoría, el exportador usa remuestreo bootstrap por
familia cuando los resultados incluyen conteos por caso, evitando tratar spans de una misma
plantilla como réplicas independientes. Los JSON históricos carecen de esos conteos y
conservan intervalos Wilson por span como aproximación exploratoria. El bootstrap no corrige
sesgos de cobertura ni vuelve representativas las plantillas sintéticas.

## Intervalos y tamaño de muestra

Para proporciones pequeñas o con pocos fallos conviene informar intervalos binomiales, en
lugar de limitarse a la proporción observada. El NIST/SEMATECH e-Handbook describe intervalos
Wilson y exactos basados en la distribución binomial, y advierte que las aproximaciones
simétricas pueden resultar imprecisas con muestras pequeñas o pocos fallos.
[NIST/SEMATECH, intervalos de confianza binomiales](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm)

Si se observan cero exposiciones en `n` solicitudes sensibles independientes, el límite
superior unilateral del 95 % para la tasa de exposición se obtiene de `1 − 0,05^(1/n)`:

| Solicitudes sensibles sin exposición | Límite superior unilateral aproximado al 95 % |
|---:|---:|
| 60 | 4,87 % |
| 300 | 0,994 % |
| 3.000 | 0,100 % |

Esto no demuestra que el riesgo real sea cero: indica qué tasas todavía son compatibles con
la muestra y el nivel de confianza elegidos. Para recall cercano a 95 %, 300 spans positivos
por categoría dan una precisión aproximada de ±2,5 puntos porcentuales al 95 % mediante la
aproximación normal; el informe final debe usar un intervalo binomial apropiado y declarar
que esta aproximación no incorpora dependencia entre spans.

## Diseño propuesto para PrivateWay

El benchmark sintético v2 se separa por familias de redacción y valores, no por filas
aleatorias. Su manifiesto registra conteos, categorías, acciones y versión del generador.
Los archivos se encuentran en `pilot/datasets/v2/`.

| Split | Solicitudes | Diseño y uso |
|---|---:|---|
| Desarrollo | 600 | 60 familias; 150 controles limpios y 450 solicitudes con datos de dos categorías. Uso permitido para ajustar prompt y reglas. |
| Validación reservada | 1.200 | 60 familias distintas; 300 controles limpios y 900 solicitudes sensibles. Hay 300 spans positivos por cada una de las seis categorías. Se usa una vez después de congelar prompt, modelo y reglas. |
| Reto | 200 | Inyección, roles e historial, repeticiones y controles negativos. Se informa separado del conjunto representativo; no se usa para ajustar sin crear una nueva versión de validación. |

El tamaño de validación permite estimar recall por clase con una incertidumbre mucho menor
que las seis observaciones por categoría del primer benchmark. Los 900 casos sensibles también
permiten cuantificar exposiciones; aun así, cero exposiciones solo acota la tasa cerca de
0,33 % al 95 % unilateral si se consideran 900 ensayos independientes. Como existen familias
de plantilla, el análisis por clúster probablemente produzca intervalos más anchos.

La propuesta inicial de aceptación del gateway es:

- cero spans sensibles anotados visibles en mensajes transmitidos al proveedor simulado;
- recall observado ≥98 % por categoría, con límite inferior del intervalo del 95 % ≥95 %;
- acierto de acción ≥98 % y falsos bloqueos ≤5 % en los controles limpios;
- ningún fallo técnico que permita transmisión; los 503 de cierre seguro se reportan aparte;
- un objetivo de latencia p95 fijado antes de comparar modelos y hardware.

El acierto de acción se acompaña de una matriz de confusión y la tasa de falsos bloqueos se
calcula sobre controles limpios con una decisión disponible. Fallos técnicos, transmisiones
confirmadas y bloqueos sin transmisión se informan por separado. El proveedor espía confirma
si el adaptador simulado recibió el texto; no acredita la conducta de un proveedor externo ni
la utilidad de respuestas reales.

Estos son gates provisionales de ingeniería, no valores NIST. Si la muestra no permite que el
límite de confianza alcance el objetivo, el resultado debe declararse inconcluso y aumentarse
la muestra; no se debe bajar el criterio después de ver los resultados.

## Datos públicos y limitaciones del set sintético

El corpus español CoNLL-2002 puede complementar la prueba de nombres y ubicaciones: su tarea
incluye persona, organización, ubicación y miscelánea y ofrece particiones separadas de
entrenamiento, desarrollo y prueba. Su dominio son noticias de EFE del año 2000 y no cubre
RUN, correo, teléfono, dirección particular ni salud; por ello no sustituye el benchmark de
PrivateWay ni se mezcla con la validación sintética sin un protocolo separado.
[Descripción original de CoNLL-2002](https://aclanthology.org/W02-2024.pdf)

La generación sintética permite offsets exactos y valores ficticios controlados, pero no
representa por sí sola toda la variación lingüística, la ambigüedad ni la distribución de
consultas reales. Antes de usar una versión para una conclusión de tesis, se deben revisar
humanamente las plantillas, anotaciones y casos ambiguos; publicar semilla, versión y conteos;
y mantener un conjunto independiente de los ejemplos usados para ajustar el prompt.

## Referencias

1. NIST, *Artificial Intelligence Risk Management Framework (AI RMF 1.0)*, NIST AI 100-1,
   2023. [Documento oficial](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf).
2. NIST/SEMATECH, *e-Handbook of Statistical Methods*, sección 7.2.4.1, intervalos de
   confianza para proporciones binomiales. [Documento oficial](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm).
3. Erik F. Tjong Kim Sang, “Introduction to the CoNLL-2002 Shared Task: Language-Independent
   Named Entity Recognition”, 2002. [ACL Anthology](https://aclanthology.org/W02-2024.pdf).
