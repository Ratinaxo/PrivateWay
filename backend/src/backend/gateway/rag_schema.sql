CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS pw_rag_indices (
    id TEXT PRIMARY KEY, metadata JSONB NOT NULL, activo BOOLEAN NOT NULL DEFAULT false
);
CREATE UNIQUE INDEX IF NOT EXISTS pw_rag_un_activo ON pw_rag_indices ((activo)) WHERE activo;
CREATE TABLE IF NOT EXISTS pw_rag_documentos (
    indice TEXT REFERENCES pw_rag_indices(id), id TEXT NOT NULL,
    metadata JSONB NOT NULL, PRIMARY KEY(indice,id)
);
CREATE TABLE IF NOT EXISTS pw_rag_fragmentos (
    indice TEXT REFERENCES pw_rag_indices(id), id TEXT NOT NULL, texto TEXT NOT NULL,
    metadata JSONB NOT NULL, embedding vector(1024) NOT NULL, PRIMARY KEY(indice,id)
);
