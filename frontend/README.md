# PrivateWay — Frontend/BFF

Next.js 16 + React 19 + NextAuth (OIDC de Keycloak). Este frontend **no** maneja claves de proveedores LLM en el navegador. Las rutas `/api/privateway/*` requieren sesión corporativa válida y confirman el estado de la cuenta en Keycloak.

## Rutas principales

- `/`: chat, catálogo y conversaciones persistentes por sujeto OIDC.
- `/login`: autenticación.
- `/admin`: administración de usuarios por rol `privateway-admin`.
- `/admin/auditoria`: bitácora con columna de usuario y previsualización de contenido original y seudonimizado para administradores.
- `GET /api/privateway/conversations` y `PUT|DELETE /api/privateway/conversations/[id]`: historial a través del gateway interno, sin exponer el token de almacenamiento ni aceptar un identificador de usuario suministrado desde el navegador.

La interfaz envía un contexto deslizante de los últimos **29 mensajes** más el nuevo al gateway. El historial, protegido mediante una clave de cifrado en el backend, se recupera de PostgreSQL después de recargar. Cuando no está disponible el servicio, se muestra un error y no se simula persistencia local.

## Ejecución

Utilizar Docker Compose desde la raíz del repositorio (`compose.yaml` y `compose.dev.yaml`). No abrir directamente el puerto interno `3000` para un inicio de sesión que espera `NEXTAUTH_URL=http://127.0.0.1:8080`.

Para pruebas de contratos sin conexión:

```sh
npm run test:contracts
```

Las pruebas de contratos no sustituyen la compilación ni las pruebas de integración con Keycloak y PostgreSQL.

Consulta `../README-env.md` y `../README-ACTUALIZACION-HISTORIAL-AUDITORIA.md`.
