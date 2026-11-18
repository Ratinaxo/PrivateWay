# Agentes de Codex para PrivateWay

Codex carga las instrucciones compartidas de `AGENTS.md` y los perfiles TOML de `.codex/agents/`. Los perfiles son subagentes con una responsabilidad concreta; el agente principal actúa como coordinador y consolida el resultado.

## Perfiles

| Perfil | Úsalo para |
|---|---|
| `backend_privacy` | FastAPI, pipeline de privacidad, historial, auditoría y contratos backend. |
| `frontend_oidc` | Next.js, React, BFF, UI, sesión OIDC y administración. |
| `infra_compose` | Docker Compose, Dockerfiles, scripts y documentación del entorno. |
| `pilot_evaluation` | Diseño y evaluación experimental, RAG, métricas y reportes del piloto. |
| `reviewer_privateway` | Revisión de un diff; es de solo lectura. |

No hace falta delegar cada tarea. Para cambios simples, pide al agente principal que trabaje directamente. Para trabajo paralelo, asigna tareas independientes y archivos disjuntos. El coordinador debe resolver interfaces y conflictos antes de integrar.

## Cómo pedirlo

Abre Codex en la raíz del repositorio. Puedes pedir la delegación por nombre de perfil en lenguaje natural; por ejemplo:

> Implementa este cambio en el chat. Coordina el trabajo con `frontend_oidc` para la UI y `backend_privacy` para el gateway. Antes de editar, acuerden el contrato y asignen archivos disjuntos. Integra los resultados y dime qué verificaste; no ejecutes pruebas todavía.

Para revisar después:

> Revisa el diff con `reviewer_privateway`. No edites código. Devuelve solo hallazgos accionables con archivo, línea, impacto y evidencia.

Para una tarea de infraestructura:

> Encarga a `infra_compose` actualizar la configuración local para este requisito. No levantes ni reinicies contenedores; inspecciona el diff al integrar.

Para el piloto:

> Pide a `pilot_evaluation` una propuesta de evaluación reproducible usando solo el split de desarrollo. No ejecutes inferencias ni leas validación reservada.

## Orquestación recomendada

1. Pide al agente principal que explore el cambio y lo descomponga por componentes.
2. Delega en paralelo solo las partes independientes; fija archivos y límites para cada perfil.
3. Pide a los agentes que informen contratos que necesitan modificar antes de implementarlos.
4. El agente principal integra, inspecciona el diff completo y solicita una revisión separada cuando aporte valor.
5. Solicita explícitamente la verificación que quieras ejecutar. Los perfiles no corren pruebas, Docker ni experimentos por defecto.

Codex admite establecer un máximo de cuatro subagentes simultáneos en `.codex/config.toml`. El número no incluye al agente principal.
