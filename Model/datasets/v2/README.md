# Benchmark sintético v2

Esta versión usa el formato común descrito en [el README de datasets](../README.md).

La metodología y los comandos reproducibles se documentan en
[la guía de experimentos](../../../README-experimentos.md).

Benchmark reproducible para evaluar el gateway sin usar información personal real. Los
valores de contacto usan dominios `.test`; los nombres, domicilios, RUN y textos médicos se
generan de forma determinista. Cada hallazgo lleva offsets exactos en caracteres Python.

## Archivos

- `desarrollo.json`: 600 solicitudes de 60 familias de texto.
- `validacion.json`: 1.200 solicitudes de 60 familias distintas; reservar hasta congelar el
  prompt, el modelo, la configuración y las reglas.
- `reto.json`: 200 solicitudes adversariales y de robustez; sus resultados se reportan aparte.
- `recuperacion.json`: las 24 consultas RAG sintéticas versionadas.
- `manifest.json`: versión, semilla, conteos de familias, acciones y spans.
- `matriz-60/`: pantalla exploratoria con el primer caso de cada una de las 60 familias
  de desarrollo y sus 12 consultas RAG. Mantiene todas las categorías, pero no tiene potencia
  estadística para aceptación; sirve para descartar variantes claramente peores antes de
  correr el lote completo.

La validación contiene 300 controles limpios y 900 solicitudes con datos sintéticos; cada
categoría (`run`, `correo`, `telefono`, `persona`, `direccion`, `salud`) aparece en 300 spans
anotados. Un caso puede tener varias categorías. El split se realiza por familias de
redacción y por valores, no mediante selección aleatoria de filas.

El reto contiene 120 inyecciones con datos, 20 ejemplos de persona/salud en historial,
20 ejemplos persona/domicilio en historial, 20 ejemplos con spans de correo repetidos,
20 parejas correo/teléfono y 20 controles de inyección sin PII. No se debe combinar con
las métricas representativas del split reservado.

## Regenerar

Desde la raíz del repositorio:

```bash
python Model/scripts/generate_benchmark_v2.py
```

La generación es determinista. La semilla/versionado están en `manifest.json`. La v2 no
sobrescribe los archivos de `v1/` ni sus resultados experimentales.

## Evaluar en el flujo híbrido principal

La carpeta `Model/datasets` se monta en `/model/datasets` y las salidas en
`/model/resultados`. Inicia el Compose principal y evalúa desarrollo,
por ejemplo:

```bash
docker compose --env-file .env --env-file .env.model \
  -f compose.yaml -f compose.dev.yaml exec -T backend \
  python -m privateway_model.evaluate --datos /model/datasets/v2 --modo hibrido \
  --nivel deteccion --split desarrollo --concurrencia 1 \
  --salida /model/resultados/v2-deteccion-hibrido-dev-c1.json
```

Para evaluar el flujo integral, usar `--nivel flujo --modo hibrido`; para el conjunto
reservado, usar `--split validacion` solamente después de congelar la configuración. El
conjunto `reto` se ejecuta con `--split reto` y se interpreta como estrés, no como muestra
representativa.

## Limitaciones

Es un conjunto sintético, de familias diseñadas y valores ficticios. No estima por sí solo
la distribución de datos ni el riesgo en producción. Las cifras de intervalo deben calcularse
por solicitud/familia cuando corresponda, no asumiendo que varios spans del mismo prompt son
observaciones independientes. Revisar las plantillas y anotaciones antes de usarlas en una
conclusión de tesis.
