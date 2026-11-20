# Datasets sintéticos

Los conjuntos están separados por generación bajo `v1/` y `v2/`. Cada archivo de casos
usa el mismo formato JSON: una lista de registros con `id`, `familia`, `split`, `accion`,
`hallazgos` y `mensajes`. Cada hallazgo conserva offsets por mensaje; cada mensaje tiene
`role` y `content`. Los conjuntos RAG usan `id`, `split`, `consulta` y `esperado`.

Cada generación incluye `manifest.json` con conteos y hashes SHA-256. `v1` es el benchmark
inicial de 60 casos por split y 24 consultas RAG; `v2` amplía los datos y mantiene la
validación reservada y el conjunto de reto separados. `v2/matriz-60` es un cribado de
desarrollo, no una tercera generación del benchmark.

Todos los datos son sintéticos. No sustituyas los mensajes por conversaciones reales. Para
composición, tamaños y reglas de uso consulta los README de cada versión y
[`README-experimentos.md`](../../README-experimentos.md).
