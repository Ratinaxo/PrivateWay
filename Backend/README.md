# Backend PrivateWay

FastAPI, gateway, persistencia cifrada de conversaciones, auditoría y detección REGEX.
El paquete `privateway-model`, ubicado en `../Model`, aporta el pipeline SLM/RAG opcional;
el backend conserva el contrato HTTP que consume el BFF de `../Frontend`.

## Desarrollo

Desde la raíz del repositorio, instala el proyecto y sus dependencias locales:

```bash
uv sync --project Backend --dev
uv run --project Backend pytest -q
```

El servicio se construye con `Backend/Dockerfile` usando la raíz como contexto para incluir
los paquetes `Backend/src` y `Model/src`. El flujo local normal utiliza REGEX; el override
`compose.hybrid.yaml` habilita SLM y RAG.

Consulta [README-env.md](../README-env.md) para configurar el entorno y
[README-experimentos.md](../README-experimentos.md) para reproducir las evaluaciones.
