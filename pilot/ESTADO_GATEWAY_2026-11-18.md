# Estado de estabilización del gateway

**Fecha:** 18 de noviembre de 2026  
**Rama:** codex/gateway-final-e2e, creada desde codex/fusion-piloto-refinado en d964103  
**Alcance:** consolidación técnica y cableado E2E local; no es aprobación de producción ni legal.

## Estado

El gateway queda preparado para pruebas E2E desde la aplicación autenticada, con el frontend
conectado al gateway híbrido del piloto mediante una red Docker interna separada. El frontend
no comparte red con vLLM, embeddings ni PostgreSQL. El historial y la auditoría usan tokens
internos distintos del token de chat; la clave Fernet queda en el archivo local ignorado
.env.web-pilot.

El flujo de entrada ejecuta REGEX y RAG+SLM en paralelo sobre el prompt original, une los
hallazgos y aplica una política determinista. El fundamento del SLM es obligatorio, sus
referencias deben pertenecer al RAG y un error técnico o una decisión inválida detiene la
transmisión. La política técnica v2 bloquea salud asociada a una persona y seudonimiza salud
sin asociación personal. La decisión de acción sigue siendo del gateway.

## Verificación realizada

- Backend: 103 pruebas aprobadas; incluye paralelismo, unión de hallazgos, política de salud,
  validación del fundamento, cierre seguro y auditoría de fallos.
- Frontend: contratos BFF, privacidad, auditoría, OIDC y administración aprobados.
- Ambos stacks: docker compose config --quiet con los overlays de piloto y web.
- Helper de credenciales: genera .env.web-pilot con modo 0600, conserva credenciales
  existentes y rechaza enlaces simbólicos.
- Ningún contenedor se inició durante esta revisión. La apertura de la UI, el login, la
  selección de pw-simulado y el envío hasta el proveedor simulado siguen pendientes de
  ejecutarse en el host.

## Límites pendientes

- La calidad de detección del SLM no queda resuelta por la estabilización del gateway. Las
  métricas previas pertenecen a una versión anterior de la política y del protocolo; no se
  deben presentar como evaluación de esta rama.
- La taxonomía actual cubre RUN, correo, teléfono, persona, dirección y salud. Tarjeta y
  patente, nombradas en docs/requerimientos.md, siguen pendientes.
- No hay mapa persistente de correspondencias ni restitución de marcadores. La respuesta del
  proveedor solo hereda el filtro REGEX, sin cobertura semántica.
- La política es experimental y no tiene aprobación jurídica. El RAG aporta contexto
  documental, no determina la acción.
- La bitácora encadenada es local; no cuenta con anclaje externo que impida recalcular la
  cadena a quien controla el archivo.
- El proveedor E2E configurado es simulado. No se habilitó un proveedor real ni se levantó el
  modelo durante esta estabilización.

## Arranque E2E

Los comandos reproducibles están en la sección “Prueba E2E desde la web local (Linux)” de
README-pilot.md. Usa consultas sintéticas y conserva .env.web-pilot: su clave cifra el
historial persistente del piloto.

Esta rama está lista para la siguiente prueba integrada en el host; esos límites deben
resolverse o declararse fuera de alcance antes de afirmar que el producto satisface todos los
requisitos de docs/requerimientos.md.
