# PrivateWay

PrivateWay es un proyecto de tesis que desarrolla una interfaz conversacional unificada para utilizar proveedores externos de modelos de lenguaje (LLM) con un gateway de protección de datos. Su objetivo es analizar los mensajes antes de que salgan del entorno controlado, aplicar políticas de privacidad y examinar las respuestas antes de mostrarlas al usuario.

# Requisitos

El laboratorio integrado con vLLM, E5 y pgvector está documentado en [README-pilot.md](README-pilot.md).
Usa configuración y volúmenes propios. La ejecución normal requiere aliases/adaptadores de proveedores reales; los dobles simulados y espías se limitan a pruebas y evaluación local.
Los experimentos reproducibles, sus comandos y la separación de datos están descritos en [README-experimentos.md](README-experimentos.md).

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

## Compose para cada flujo

- Flujo principal local con REGEX: `compose.yaml` y `compose.dev.yaml`.
- Flujo híbrido principal con SLM/RAG: añade `compose.hybrid.yaml` y configura
  `.env.pilot`; requiere GPU y modelos descargados en `Model/models/`.
- Laboratorio aislado de evaluación: `compose.pilot.yaml`; añade `compose.lab.yaml`
  únicamente cuando el smoke o el chat deban salir a un proveedor real.
- Los overrides `compose.pilot.qwen35.yaml`, `compose.pilot.web.yaml` y
  `compose.web-pilot.yaml` habilitan variantes opcionales del modelo o pruebas E2E web.

Los detalles y comandos están en [README-docker.md](README-docker.md) y
[README-experimentos.md](README-experimentos.md).
