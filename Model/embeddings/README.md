# Servicio de embeddings

`/ready` permanece en HTTP 503 mientras `PRIVATEWAY_E5_REVISION` esté vacío o tenga
un valor provisional (`pending-download` o `no-descargado`). Para habilitar la ingesta,
el operador debe completar la preparación local de modelos desde la raíz del repositorio:

```bash
uv run --project Backend python Model/scripts/setup_model_env.py
uv run --project Backend python Model/scripts/download_models.py
```

La descarga fija la revisión E5 en `Model/models.lock.json` y actualiza
`PRIVATEWAY_E5_REVISION` en la configuración local ignorada por Git. El valor debe coincidir
con la revisión del registro `intfloat/multilingual-e5-large` en el lock. Después de completar
la preparación, recrear el servicio de embeddings para que reciba la revisión y confirmar que
`/ready` responda correctamente antes de ingerir o activar un índice. No reemplazar el valor
provisional manualmente por una revisión que no corresponda a los pesos locales.
