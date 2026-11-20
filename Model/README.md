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
