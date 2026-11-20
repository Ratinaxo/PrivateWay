# Model

Contiene los componentes de inferencia y recuperación locales de PrivateWay:

- `src/privateway_model/`: SLM, protocolo de extracción, fusión híbrida, recuperación RAG
  y evaluadores.
- `embeddings/`: servicio local de embeddings.
- `models/`: destino local ignorado por Git para pesos descargados.
- `corpus/`: manifiesto versionado y fragmentos preparados desde las fuentes normativas
  Markdown de `../docs/`.
- `datasets/`: benchmarks sintéticos v1 y v2 con manifiestos y hashes.
- `experimentos/resultados/`: salida local de ejecuciones, ignorada por Git.
- `scripts/`: preparación del entorno, modelos, corpus, evaluación y exportación.

La selección de PostgreSQL con pgvector, preparación del corpus y los comandos están en
[README-experimentos.md](../README-experimentos.md) y [datasets/README.md](datasets/README.md).

El protocolo híbrido registra las categorías de la taxonomía del gateway, deriva la clase
operativa de cada categoría y conserva las subcategorías sensibles con su término en español.
REGEX y SLM extraen en paralelo; después, RAG recibe las categorías y subcategorías para
recuperar contexto documental sin añadir los valores detectados a las consultas de categoría.
