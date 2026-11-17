# PrivateWay

PrivateWay es un proyecto de tesis que desarrolla una interfaz conversacional unificada para utilizar proveedores externos de modelos de lenguaje (LLM) con un gateway de protección de datos. Su objetivo es analizar los mensajes antes de que salgan del entorno controlado, aplicar políticas de privacidad y examinar las respuestas antes de mostrarlas al usuario.

# Requisitos

El laboratorio integrado con vLLM, E5 y pgvector está documentado en [README-pilot.md](README-pilot.md).
Usa configuración y volúmenes propios, datos sintéticos y proveedor simulado.
El resumen de implementación, resultados y pendientes está en [README-CAMBIOS-PILOTO.md](README-CAMBIOS-PILOTO.md).
La corrección y repetición de pruebas del 17 de noviembre está documentada en [README-CORRECCIONES-PRUEBAS.md](README-CORRECCIONES-PRUEBAS.md).

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
