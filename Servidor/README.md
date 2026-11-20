# Servidor

Configuración local de infraestructura que acompaña al backend y frontend:

- `nginx/local.conf`: proxy inverso del flujo principal.
- `nginx/pilot.conf`: proxy de entrada del laboratorio aislado.
- `keycloak/bootstrap.sh`: inicialización idempotente de realm y clientes OIDC.
- `configurar-entorno.py`: preparación local de variables de entorno.

Los servicios y puertos se declaran en los Compose de la raíz. El flujo principal usa
`compose.yaml`; no necesita un Compose separado para Nginx o Keycloak.
