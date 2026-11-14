# Piloto vLLM + RAG

El laboratorio usa Qwen2.5-3B-Instruct-AWQ en GPU, E5-large en CPU y PostgreSQL/pgvector.
Un proxy de entrada publica el gateway en `127.0.0.1:8082`. Los demás servicios operan en una red Docker
interna. Las descargas se hacen antes del arranque y los modelos se montan de solo lectura.
Este laboratorio no transmite consultas a proveedores reales.

## Preparación (PowerShell, desde la raíz)

Requiere Docker Desktop iniciado, backend WSL2 y GPU NVIDIA disponible.
Las imágenes y los modelos requieren varios GB de disco. No ejecutar `down -v`:
eliminaría la base y las evidencias del piloto.

```powershell
uv sync --project backend --dev
backend/.venv/Scripts/python.exe scripts/setup_pilot.py
backend/.venv/Scripts/python.exe scripts/download_models.py
backend/.venv/Scripts/python.exe scripts/prepare_corpus.py
backend/.venv/Scripts/python.exe scripts/generate_pilot_data.py
docker compose --env-file .env.pilot -f compose.pilot.yaml build
docker compose --env-file .env.pilot -f compose.pilot.yaml up -d slm embeddings postgres
docker compose --env-file .env.pilot -f compose.pilot.yaml run --rm --no-deps backend python -m backend.gateway.rag /corpus/manifest.json
docker compose --env-file .env.pilot -f compose.pilot.yaml up -d backend proxy
curl.exe http://127.0.0.1:8082/ready
```

`.env.pilot` contiene claves propias, ignoradas por Git. El script no cambia `.env`
ni regenera claves existentes. `models.lock.json` conserva revisión de pesos y tokenizer,
licencias y hashes. Qwen 3B usa licencia `qwen-research`: este es un piloto académico.

Si el arranque indica falta de memoria, reducir `PRIVATEWAY_SLM_CONTEXT` a 2048 en
`.env.pilot`, recrear `slm` y `backend` y repetir el diagnóstico. Eso reduce el presupuesto
disponible para contexto legislativo y puede impedir analizar solicitudes que antes cabían.
Registrar cualquier cambio de memoria GPU/contexto antes de comparar ejecuciones.

La API conserva `/api/v1/secure-chat` y `/v1/chat/completions`; usar el token de gateway
de `.env.pilot` mediante `Authorization: Bearer …`. No copiarlo en tickets, reportes o Git.
El piloto no incluye frontend ni Keycloak duplicados: prueba la misma API del proyecto
y permite conectar un BFF existente configurando `GATEWAY_INTERNAL_URL` y su token.

## Corpus y criterios

BCN `obtxml` devuelve la versión vigente, no un consolidado futuro. Por ello se conserva
la Ley 19.628 como texto base y se recuperan disposiciones reformadas desde el texto
oficial de la Ley 21.719: art. primero, definiciones 2 f/g/l, principios del art. 3 y
art. 16 bis. Se conserva la versión real del XML y se identifica la vigencia diferida
del escenario estudiado (2026-12-01). No se etiqueta la versión antigua como reformada.
Los archivos originales están en `pilot/corpus/raw`, con hashes en el manifiesto.

La extracción conserva artículo/letra/inciso y el servicio E5 subdivide unidades que
exceden 448 tokens, preservando el localizador. Los prefijos E5 y tokens especiales
caben dentro de 512 tokens. No se truncan entradas de embeddings o de inferencia.
La ingesta activa una versión completa dentro de una transacción y no modifica versiones
previas. Repetirla con el mismo manifiesto y encoder no duplica fragmentos.

Cobertura inicial: RUN, correo, teléfono, persona, dirección y salud. Sin hallazgos se
permite; identificadores se sustituyen por marcadores; salud asociada a persona se bloquea.
Es una regla experimental del proyecto, no una conclusión jurídica universal.

El modelo propone y el código valida. No puede descartar hallazgos REGEX. Citas ajenas al
contexto, incoherencia de acción, offsets incorrectos, formato incompleto, colisiones de
marcadores, falta de evidencia y fallos técnicos detienen el envío. El modo híbrido nunca
retrocede a REGEX automáticamente. La pertenencia de una cita no certifica su pertinencia:
esa dimensión necesita evaluación humana.

Los mensajes del historial también se analizan. Las instrucciones dentro de cualquier rol
son datos para el analizador. No se implementa restitución todavía. La respuesta conserva
el control REGEX existente, cuya cobertura semántica es limitada.

## Pruebas y mediciones

```powershell
cd backend
uv run pytest -q
cd ../frontend
node --run test:contracts
cd ..
docker compose --env-file .env.pilot -f compose.pilot.yaml exec backend python -m backend.gateway.evaluate --modo hibrido --split desarrollo --concurrencia 1 --salida /pilot/results/hibrido-dev-c1.json
```

Repetir para `--modo regex`, `slm`, `hibrido` y concurrencias `1`, `5`, `10`.
Para reproducir la batería inicial y capturar recursos del stack:

```powershell
backend/.venv/Scripts/python.exe scripts/run_pilot.py --limite 10
backend/.venv/Scripts/python.exe scripts/report_pilot.py
```

Omitir `--limite 10` para ejecutar todos los casos de desarrollo. El conjunto de validación
solo se ejecuta explícitamente con el evaluador; el lanzador nunca lo utiliza.

Usar `--nivel deteccion` para comparar los tres detectores y `--nivel flujo --modo hibrido`
para evaluar decisiones, exposición y transmisión. El primer caso calienta los servicios y no integra las métricas. La evaluación guarda
precisión, recall y F2 por categoría, coincidencia exacta de spans, Recall@4, errores,
bloqueos, transmisiones, exposición literal, tiempos por etapa y p50/p95/p99.
Los fallos técnicos cuentan como omisiones en detección y no como bloqueos del modelo.
Las métricas indefinidas se reportan como `null`.

Hay 60 casos de desarrollo y 60 de validación separados por familias, además de 24
consultas documentales. Las anotaciones son sintéticas y preliminares: requieren revisión
humana. El conjunto reservado no debe utilizarse para ajustar prompts; la ejecución final
de tesis requiere un corpus independiente y protocolo cerrado. No se utiliza el conjunto
reservado durante la puesta en marcha.

Para observar recursos durante una ejecución:

```powershell
docker stats --no-stream
nvidia-smi --query-gpu=timestamp,memory.used,utilization.gpu --format=csv
```

La justificación, los hallazgos y las referencias se guardan en vistas cifradas de auditoría;
el JSONL contiene códigos de operación. Hay eventos de fallo de análisis sin contenido.
`/health` mide liveness; `/ready` exige modelo, embeddings y corpus activo. Una caída
no habilita el proveedor simulado ni un proveedor externo.

## Límites de este hito

No incluye restitución por sesión, cobertura de toda la taxonomía, ajuste supervisado,
proveedor real ni evaluación final de utilidad. Los resultados locales no prueban
cumplimiento legal ni ausencia de datos personales. Consultar `pilot/REPORT.md` para
el estado y las evidencias de la ejecución efectivamente realizada.

Para detener el laboratorio y liberar la GPU conservando datos y evidencias:

```powershell
docker compose --env-file .env.pilot -f compose.pilot.yaml stop
```
