# PrivateWay: instrucciones para agentes

## Contexto

PrivateWay es un proyecto de tesis para proteger datos antes de enviar mensajes a proveedores LLM. El repositorio contiene un frontend/BFF Next.js y TypeScript, un gateway FastAPI, autenticación Keycloak/OIDC, persistencia PostgreSQL y un piloto de detección local con Presidio, vLLM, embeddings y RAG.

Antes de cambiar un área, lee el README correspondiente y los contratos o pruebas de esa área. Para el piloto, consulta `README-pilot.md` y la documentación dentro de `pilot/`.

## Límites importantes

- Mantén los secretos fuera de Git, respuestas, logs y artefactos. No leas ni muestres `.env` ni `.env.pilot`; usa `.env.example` para conocer nombres de variables.
- No transmitas consultas del proyecto a proveedores reales. El piloto está pensado para datos sintéticos y proveedor simulado.
- No uses el conjunto reservado de validación para ajustar prompts, modelos o reglas. Conserva su separación de desarrollo.
- No afirmes que las reglas experimentales del piloto son conclusiones legales generales.
- Conserva los contratos públicos entre frontend/BFF y gateway salvo que el usuario apruebe explícitamente un cambio coordinado.
- Evita que dos agentes editen simultáneamente los mismos archivos. El coordinador define propiedad de archivos y consolida cambios.
- No borres volúmenes Docker ni ejecutes comandos destructivos de infraestructura.

## Desarrollo y verificación

- Backend: Python 3.12+, FastAPI; dependencias y comandos en `backend/pyproject.toml` y `backend/README.md`.
- Frontend: Next.js, React y TypeScript; scripts en `frontend/package.json`.
- Entorno: Docker Compose; revisa los README antes de modificar servicios o volúmenes.
- No ejecutes pruebas ni añadas pruebas salvo que el usuario pida verificar o probar el cambio. Cuando se solicite, prefiere la comprobación más acotada relevante y reporta el comando y resultado.
- No declares verificado un comportamiento que no hayas ejecutado o inspeccionado.

## Entrega

Resume archivos y comportamiento cambiados, evidencia de verificación, riesgos y cualquier pregunta abierta. Señala explícitamente cambios de contrato o impacto en privacidad.
