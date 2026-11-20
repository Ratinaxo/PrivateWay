# PrivateWay

PrivateWay es un proyecto de tesis que desarrolla una interfaz conversacional unificada para utilizar proveedores externos de modelos de lenguaje (LLM) con un gateway de protección de datos. Su objetivo es analizar los mensajes antes de que salgan del entorno controlado, aplicar políticas de privacidad y examinar las respuestas antes de mostrarlas al usuario.

# Requisitos

La configuración del flujo principal está en [README-docker.md](README-docker.md). La preparación del modelo y la evaluación reproducible están en [README-experimentos.md](README-experimentos.md).

- Git
- Docker con Docker Compose o Docker Desktop.
- Python 3.12+
- Node.js 26
- OpenSSL

# Tecnologías

| Componente | Tecnología |
|---|---|
| Interfaz y BFF | Next.js, React, TypeScript, NextAuth |
| Gateway | Python, FastAPI |
| Proxy inverso | Nginx |
| Identidad y roles | Keycloak, OpenID Connect (OIDC) |
| Base de datos de identidad | PostgreSQL |
| Entorno local | Docker y Docker Compose |
| Persistencia de conversaciones | PostgreSQL |

## Organización del repositorio

- `Backend/`: FastAPI, gateway y detección REGEX.
- `Frontend/`: interfaz Next.js y BFF.
- `Servidor/`: configuración de Nginx, Keycloak y utilidades del servidor.
- `Model/`: cliente SLM, protocolo y pipeline híbrido, servicio de embeddings, RAG,
  corpus, modelos, datasets y `experimentos/resultados/`.

## Flujo principal

El único flujo del gateway es híbrido: REGEX y SLM analizan en paralelo y sus hallazgos se
fusionan. `compose.yaml` define los servicios del laboratorio local; requiere `.env.model`,
GPU y modelos descargados en `Model/models/`. Consulta [README-docker.md](README-docker.md) y
[README-experimentos.md](README-experimentos.md) para prepararlo y arrancarlo.

Los detalles y comandos están en [README-docker.md](README-docker.md) y
[README-experimentos.md](README-experimentos.md).
