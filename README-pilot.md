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

## Prueba E2E desde la web local (Linux)

Los overrides opcionales conectan el frontend autenticado del proyecto con el gateway
híbrido del piloto. Keycloak y el proveedor simulado siguen siendo los de desarrollo;
el frontend no comparte la red del SLM, embeddings ni PostgreSQL. El gateway conserva
su propia base, auditoría y claves de cifrado. Usa únicamente mensajes sintéticos.

Genera una vez los tokens de puente locales; el archivo queda ignorado por Git y con
permisos `0600`:

```bash
python3 scripts/prepare_web_pilot.py
```

Primero inicia los servicios y modelos del piloto como en la preparación anterior. Con
el corpus ya ingestado, aplica el override del gateway y después el del frontend:

```bash
docker compose --env-file .env.pilot -f compose.pilot.yaml up -d slm embeddings postgres
docker compose --env-file .env.pilot -f compose.pilot.yaml run --rm --no-deps backend python -m backend.gateway.rag /corpus/manifest.json
docker compose --env-file .env.pilot --env-file .env.web-pilot -f compose.pilot.yaml -f compose.pilot.web.yaml up -d --build backend proxy
docker compose --env-file .env --env-file .env.web-pilot -f compose.yaml -f compose.dev.yaml -f compose.web-pilot.yaml up -d --build frontend proxy
curl http://127.0.0.1:8082/ready
```

Abre `http://127.0.0.1:8080`, inicia sesión y selecciona el proveedor simulado y el
modelo `pw-simulado`. El BFF apunta a `pilot-gateway:8000` por una red Docker dedicada;
la autenticación de usuario no cambia. El historial se almacena cifrado en la base
PostgreSQL exclusiva del piloto. La respuesta del proveedor es simulada: esta prueba
recorre navegador, BFF, autenticación, gateway híbrido y persistencia, sin un LLM externo.
Conserva `.env.web-pilot`: su clave cifra el historial persistente y, si se pierde, las
conversaciones existentes ya no se podrán descifrar.

Para volver al gateway principal, recrea frontend y proxy sin el override E2E:

```bash
docker compose --env-file .env -f compose.yaml -f compose.dev.yaml up -d --force-recreate frontend proxy
```

No uses `down -v`; los volúmenes contienen el corpus indexado, auditoría e historial.

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
permite; identificadores se sustituyen por marcadores; salud asociada a una persona bloquea.
El SLM informa entidades contextuales con texto literal y mensaje; el gateway calcula sus
offsets, agrega directamente los hallazgos REGEX y aplica la regla experimental. Es una
regla del piloto, no una conclusión jurídica universal.

El SLM devuelve solo texto literal, categoría y mensaje. El gateway deriva la acción y las
posiciones, y registra los fragmentos recuperados sin pedir al modelo que los vuelva a citar.
Texto de entidad ausente, formato incompleto, colisiones de marcadores, falta de evidencia
y fallos técnicos detienen el envío. El modo híbrido nunca retrocede a REGEX automáticamente.
La pertinencia de las fuentes para cada decisión necesita evaluación humana.

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

Para ejecutar la misma matriz de 12 configuraciones sobre el benchmark ampliado, usa
`uv run python scripts/run_pilot.py --dataset v2`. La batería utiliza solo desarrollo y
guarda archivos con prefijo `v2-`; `--limite N` conserva la opción de pantalla exploratoria.
Al terminar se exportan automáticamente `pilot/results/export/experimentos.csv`,
`metricas_categoria.csv`, `casos.csv`, `recuperacion.csv` y `manifest.json`. También se
puede regenerar la exportación sin repetir inferencias con
`uv run python scripts/export_experiments.py`.

Los CSV contienen configuración, modelo/revisión, hashes del prompt y esquema, TP/FP/FN,
precisión, recall, F1/F2 micro y macro, detección exacta y parcial, latencias p50/p95/p99,
throughput, errores, decisiones, transmisiones, exposición exacta/parcial y aciertos RAG.
`metricas_categoria.csv` calcula intervalos percentiles del 95 % mediante bootstrap por
familia cuando el JSON incluye conteos por caso; resultados antiguos usan Wilson por span y
se marcan como aproximación que no corrige dependencia. Los identificadores y conteos por
caso se conservan, pero no se exporta el texto de consultas ni valores personales.

El lanzador detiene la batería si alguno de los tres casos smoke falla; corrige ese fallo
antes de consumir tiempo GPU en las comparaciones.

En Linux, si el usuario necesita `sudo` para acceder al daemon Docker, ejecuta la batería
con `PRIVATEWAY_DOCKER_SUDO=1 uv run python scripts/run_pilot.py --limite 10`. El lanzador
solicita la contraseña una vez y usa `sudo -n` solo para los comandos Docker; `uv` y Python
siguen ejecutándose como el usuario actual. El smoke test no requiere acceso al daemon.

Omitir `--limite 10` para ejecutar todos los casos de desarrollo. El conjunto de validación
solo se ejecuta explícitamente con el evaluador; el lanzador nunca lo utiliza.

Usar `--nivel deteccion` para comparar REGEX, SLM y unión híbrida sobre los mismos mensajes.
En el modo híbrido, REGEX y SLM reciben el prompt original y se ejecutan en paralelo; el
gateway fusiona sus hallazgos y filtra el texto antes del proveedor. `--nivel flujo
--modo hibrido` evalúa acciones, exposición y transmisión por API ASGI con proveedor espía.
La evaluación guarda precisión, recall, F1/F2 micro y macro, spans exactos/parciales,
Recall@4, matriz de acciones, falsos bloqueos, errores, exposición exacta/parcial condicionada
a transmisión confirmada, tiempos por etapa y latencias p50/p95/p99.
Los fallos técnicos cuentan como omisiones en detección y no como bloqueos del modelo.
Las métricas indefinidas se reportan como `null`.

Hay 60 casos de desarrollo y 60 de validación separados por familias, además de 24
consultas documentales. Las anotaciones son sintéticas y preliminares: requieren revisión
humana. El conjunto reservado no debe utilizarse para ajustar prompts; la ejecución final
de tesis requiere un corpus independiente y protocolo cerrado. No se utiliza el conjunto
reservado durante la puesta en marcha.

La versión ampliada del benchmark está en [`pilot/datasets/v2/`](pilot/datasets/v2/README.md):
600 casos de desarrollo, 1.200 de validación reservada y 200 de reto. La metodología,
los tamaños de muestra y los criterios propuestos a partir del marco NIST están en
[`pilot/ANEXO_EVALUACION_NIST.md`](pilot/ANEXO_EVALUACION_NIST.md).
El cierre de resultados del pipeline, estado de prompts y plan de adaptación de datos
externos está en [`pilot/CIERRE_RESULTADOS_PIPELINE.md`](pilot/CIERRE_RESULTADOS_PIPELINE.md).
La comparación planificada de Qwen/E5, Qwen/BGE-M3, Qwen3.5/E5 y Qwen3.5/BGE-M3 está en
[`pilot/MATRIZ_MODELOS.md`](pilot/MATRIZ_MODELOS.md); la validación reservada sigue protegida.

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
