# Backend PrivateWay

FastAPI, gateway, persistencia cifrada de conversaciones, auditoría y protección híbrida.
El pipeline único de ejecución combina REGEX/Presidio y SLM/RAG; el backend conserva el
contrato HTTP que consume el BFF de `../Frontend`.

## Desarrollo

Desde la raíz del repositorio, instala el proyecto y sus dependencias locales:

```bash
uv sync --project Backend --dev
uv run --project Backend pytest -q
```

El servicio se construye con `Backend/Dockerfile` usando la raíz como contexto para incluir
los paquetes `Backend/src` y `Model/src`. El gateway arranca el flujo híbrido por defecto y
rechaza cualquier valor de `PRIVATEWAY_PIPELINE` distinto de `hibrido`. Requiere la
configuración de SLM, embeddings y RAG descrita en `README-experimentos.md` y activada en
Compose mediante `compose.yaml`; `compose.hybrid.yaml` queda como overlay de compatibilidad.
REGEX y SLM se ejecutan como etapas del mismo flujo; no son modos alternativos de ejecución
del gateway.

La taxonomía operativa incluye identificadores, datos sensibles y categorías de régimen
especial. REGEX cubre RUN, correo, teléfonos chilenos, tarjeta, patente y coordenadas; el
SLM extrae las categorías contextuales restantes. Cada hallazgo conserva su clase operativa,
el término legal sensible cuando corresponda y la relación de titular de edad. Estas
etiquetas son criterios del prototipo y no determinaciones jurídicas.

La auditoría conserva la acción y un código de motivo en los metadatos verificables. La
justificación en lenguaje natural y la traza del análisis, que pueden reflejar contenido del
prompt, se guardan solo en la previsualización cifrada y separada del JSONL. El BFF de
administración muestra la decisión y la justificación al abrir el detalle; cada lectura queda
registrada y las previsualizaciones tienen retención limitada.

Consulta [README-env.md](../README-env.md) para configurar el entorno y
[README-experimentos.md](../README-experimentos.md) para reproducir las evaluaciones.
