# Verificación técnica de PrivateWay

| Requisito | Evidencia | Estado |
|---|---|---|
| Restitución acotada al usuario y la conversación | Contrato del BFF y prueba de dos conversaciones en la API con PostgreSQL real y proveedor de eco | Verificado |
| Cifrado, concurrencia, caducidad y eliminación de correspondencias | `backend.gateway.check_conversation_store` con registros sintéticos | Verificado en PostgreSQL |
| Detener el envío ante fallo previo y distinguir fallos posteriores | Pruebas del gateway y estados de la auditoría | Verificado con simulador |
| Canalización en el cliente administrado | Cliente efímero de Docker en red interna alcanzó `/ready` y no pudo establecer conexión directa con la API externa | Verificado en el cliente efímero. Pendiente la sesión con el proveedor real |
| Utilidad posterior a la restitución | `backend.gateway.evaluate_utility` con Gemini 3.1 Flash-Lite en ambos brazos | Piloto de cinco casos ejecutado, tres pares evaluables |
| Detección, exposición, rendimiento y recuperación | [Informe de desarrollo v9](REPORT-DESARROLLO-V9.md), JSON por caso y auditoría del simulador | Desarrollo aprobado en las doce configuraciones. Cero exposiciones anotadas en cada corrida de flujo |
| Validación reservada | Resultado completo con configuración congelada | Pendiente |

## Stack simulado

```powershell
backend/.venv/Scripts/python.exe scripts/setup_pilot.py --slm 7b
docker compose --env-file .env.pilot -f compose.pilot.yaml up -d --wait
docker compose --env-file .env.pilot -f compose.pilot.yaml exec -T backend python -m backend.gateway.check_conversation_store
backend/.venv/Scripts/python.exe scripts/run_pilot.py --repeticiones 2 --output-dir pilot/results/desarrollo-completo
```

El BFF necesita el mismo `GATEWAY_HISTORY_TOKEN` que el gateway y su credencial de chat habitual. El navegador pasa el identificador de conversación, el BFF agrega el sujeto de la sesión y el gateway coteja el par contra PostgreSQL. Los marcadores caducan a las 24 horas y el borrado de la conversación elimina sus filas por cascada. Las solicitudes sin ámbito autenticado usan el ciclo de vida de la solicitud.

## Laboratorio externo

Crear una clave en [Google AI Studio](https://aistudio.google.com/apikey) y guardarla en `.env.pilot` como `PRIVATEWAY_LAB_GEMINI_KEY`. El alias `pw-lab` usa `gemini-3.1-flash-lite` por defecto; se puede fijar otro modelo con `PRIVATEWAY_LAB_GEMINI_MODEL`. La clave entra exclusivamente al contenedor del gateway. Ejecutar el perfil externo solo con consultas sintéticas. La red interna aísla los servicios del piloto, mientras que restringir la salida directa de un cliente real depende de los controles de red del laboratorio.

```powershell
docker compose --env-file .env.pilot -f compose.pilot.yaml -f compose.lab.yaml up -d --wait
docker compose --env-file .env.pilot -f compose.pilot.yaml -f compose.lab.yaml exec -T backend python -m backend.gateway.evaluate_utility --salida /pilot/results/utilidad-lab.json
```

Comprobar desde el cliente administrado que el chat protegido llega a `pw-lab` y que la API externa es inaccesible directamente. Registrar códigos de estado y evidencia de red, sin copiar credenciales ni contenido. La comparación usa tareas con una respuesta de referencia, puntúa los pares evaluables y separa bloqueos y fallos.

## Criterios de evaluación

La exposición literal busca cada valor anotado en el mensaje correspondiente recibido por el simulador. La visibilidad parcial usa bloques de cuatro dígitos para RUN y teléfono, tokens de al menos tres caracteres de la parte local del correo y palabras de al menos tres caracteres para nombres, direcciones y salud. Las coincidencias parciales requieren revisión por posibles homónimos y coincidencias accidentales. Los bloqueos quedan fuera del denominador. La recuperación registra la disposición esperada y los identificadores recuperados, mientras que las citas del SLM se registran por separado.

Las seis anotaciones de salud de desarrollo seleccionan el término clínico «diabetes». Las tres configuraciones con SLM solo devolvieron un segmento de salud diferente en cada caso. Se conserva el criterio de coincidencia exacta y se evalúa también la acción de bloqueo.

En la primera configuración híbrida de desarrollo se observaron además tres omisiones de nombres en consultas que mezclaban persona, correo y teléfono. Esto deja pendiente revisar la posible exposición antes de congelar la configuración. Esa corrida obtuvo F2 exacto de 0,891 y cero fallos técnicos de detección.

El flujo inicial con 60 consultas confirmó tres apariciones literales transmitidas en cada nivel de concurrencia, aunque acertó las 60 acciones y registró cero fallos técnicos en cada nivel. El ajuste `etapas-v7` recuperó los nombres omitidos y alineó el segmento de salud con la anotación en las doce consultas dirigidas.

El primer ensayo de utilidad con Gemini mostró que el proveedor podía devolver solo el sufijo del marcador. La restitución exigió el marcador completo. En la segunda corrida se pidió copiar literalmente el valor y conservar los corchetes en ambos brazos. Los tres pares evaluables (nombre, correo y control negativo) fueron correctos en ambos brazos. La dirección se restituyó correctamente, pero la referencia falló con `HTTP_PROVEEDOR`. La consulta de salud se detuvo antes de transmitir por `SLM_SALUD_AMBIGUA`. La evidencia está en `pilot/results/utilidad-gemini-20261118-v7-copia.json` y su archivo de auditoría. Tres pares permiten verificar el recorrido, pero el tamaño del ensayo y las exclusiones limitan las conclusiones de utilidad.

La revisión `etapas-v9` verifica asociaciones de salud dudosas en una tarea específica que solo acepta identificadores de diagnósticos ya anclados. Pasaron 108 pruebas de backend. En el flujo con simulador pasaron los seis casos combinados sin exposición literal o parcial, los seis casos de salud de desarrollo y el caso de salud del ensayo de utilidad. Los siete casos de salud se bloquearon correctamente sin llamar al simulador. El detalle está en `pilot/results/ajuste-v9-focalizado.json`. El primer arranque de la batería completa se interrumpió por codificación de consola. La repetición se inició bajo `pilot/results/20261118-desarrollo-60-v9-repeticion`.

Tras aprobar desarrollo y guardar el commit limpio, generar el manifiesto con `scripts/freeze_pilot.py --desarrollo pilot/results/20261118-desarrollo-60-v9-repeticion --salida pilot/results/congelacion.json`. El manifiesto registra las huellas del corpus, datasets, modelo, instrucciones y resultados de desarrollo. Ejecutar `scripts/run_pilot.py --split validacion --repeticiones 2` desde esa configuración. Comparar la recuperación con las citas del juicio mediante `backend.gateway.evaluate_citations --split validacion`.
