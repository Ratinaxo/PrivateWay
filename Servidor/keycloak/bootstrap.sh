#!/usr/bin/env bash
# Configuración idempotente del laboratorio OIDC PrivateWay.
# Se ejecuta dentro de la imagen oficial de Keycloak. No imprime contraseñas.
set -euo pipefail

: "${KC_BOOTSTRAP_ADMIN_USERNAME:?}"
: "${KC_BOOTSTRAP_ADMIN_PASSWORD:?}"
: "${PRIVATEWAY_OIDC_CLIENT_SECRET:?}"
: "${PRIVATEWAY_KEYCLOAK_ADMIN_CLIENT_SECRET:?}"
: "${PRIVATEWAY_FIRST_ADMIN_PASSWORD:?}"
: "${PRIVATEWAY_FIRST_ADMIN_USERNAME:?}"

KC=/opt/keycloak/bin/kcadm.sh
SERVER=http://keycloak:8081
REALM=privateway
APP_URL="http://127.0.0.1:${PRIVATEWAY_HTTP_PORT:-8080}"

ready=false
for attempt in {1..90}; do
  if "$KC" config credentials --server "$SERVER" --realm master \
    --user "$KC_BOOTSTRAP_ADMIN_USERNAME" --password "$KC_BOOTSTRAP_ADMIN_PASSWORD" >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 3
done
if [[ "$ready" != true ]]; then
  printf 'Keycloak no está preparado o fallaron las credenciales de bootstrap.\n' >&2
  exit 1
fi

if ! "$KC" get "realms/$REALM" >/dev/null 2>&1; then
  "$KC" create realms -s "realm=$REALM" -s enabled=true -s registrationAllowed=false \
    -s loginWithEmailAllowed=true -s resetPasswordAllowed=false -s sslRequired=none >/dev/null
fi

for role in privateway-user privateway-admin; do
  if ! "$KC" get "roles/$role" -r "$REALM" >/dev/null 2>&1; then
    "$KC" create roles -r "$REALM" -s "name=$role" >/dev/null
  fi
done

client_uuid() {
  local result
  result=$("$KC" get clients -r "$REALM" -q "clientId=$1")
  if [[ "$result" =~ \"id\"[[:space:]]*:[[:space:]]*\"([^\"]+)\" ]]; then
    printf '%s' "${BASH_REMATCH[1]}"
  else
    return 1
  fi
}

if ! web_uuid=$(client_uuid privateway-web); then
  "$KC" create clients -r "$REALM" \
    -s clientId=privateway-web -s enabled=true -s protocol=openid-connect \
    -s publicClient=false -s standardFlowEnabled=true -s directAccessGrantsEnabled=false \
    -s serviceAccountsEnabled=false -s "secret=$PRIVATEWAY_OIDC_CLIENT_SECRET" \
    -s "rootUrl=$APP_URL" -s "baseUrl=$APP_URL/" \
    -s "redirectUris=[\"$APP_URL/api/auth/callback/privateway-oidc\"]" \
    -s "webOrigins=[\"$APP_URL\"]" \
    -s 'attributes."pkce.code.challenge.method"=S256' \
    -s "attributes.\"post.logout.redirect.uris\"=$APP_URL/login" >/dev/null
  web_uuid=$(client_uuid privateway-web)
else
  "$KC" update "clients/$web_uuid" -r "$REALM" \
    -s "secret=$PRIVATEWAY_OIDC_CLIENT_SECRET" \
    -s "redirectUris=[\"$APP_URL/api/auth/callback/privateway-oidc\"]" \
    -s "webOrigins=[\"$APP_URL\"]" \
    -s "attributes.\"post.logout.redirect.uris\"=$APP_URL/login" >/dev/null
fi

# El BFF consulta roles EN VIVO desde Keycloak. No se insertan roles en tokens JWT.

if ! admin_uuid=$(client_uuid privateway-admin-api); then
  "$KC" create clients -r "$REALM" \
    -s clientId=privateway-admin-api -s enabled=true -s protocol=openid-connect \
    -s publicClient=false -s standardFlowEnabled=false -s directAccessGrantsEnabled=false \
    -s serviceAccountsEnabled=true -s "secret=$PRIVATEWAY_KEYCLOAK_ADMIN_CLIENT_SECRET" >/dev/null
  admin_uuid=$(client_uuid privateway-admin-api)
else
  "$KC" update "clients/$admin_uuid" -r "$REALM" \
    -s serviceAccountsEnabled=true -s "secret=$PRIVATEWAY_KEYCLOAK_ADMIN_CLIENT_SECRET" >/dev/null
fi

# Servicio de administración limitado a usuarios del realm PrivateWay.
for role in query-users view-users manage-users view-realm; do
  "$KC" add-roles -r "$REALM" --uusername service-account-privateway-admin-api \
    --cclientid realm-management --rolename "$role" >/dev/null
done

# Creación inicial: NO se vuelve a sobrescribir la contraseña en los siguientes arranques.
existing=$("$KC" get users -r "$REALM" -q "username=$PRIVATEWAY_FIRST_ADMIN_USERNAME" -q exact=true)
if [[ "$existing" != *'"username"'* ]]; then
  "$KC" create users -r "$REALM" \
    -s "username=$PRIVATEWAY_FIRST_ADMIN_USERNAME" -s enabled=true \
    -s firstName=Administrador -s lastName=PrivateWay >/dev/null
  "$KC" set-password -r "$REALM" --username "$PRIVATEWAY_FIRST_ADMIN_USERNAME" \
    --new-password "$PRIVATEWAY_FIRST_ADMIN_PASSWORD" --temporary >/dev/null
  "$KC" add-roles -r "$REALM" --uusername "$PRIVATEWAY_FIRST_ADMIN_USERNAME" --rolename privateway-user >/dev/null
  "$KC" add-roles -r "$REALM" --uusername "$PRIVATEWAY_FIRST_ADMIN_USERNAME" --rolename privateway-admin >/dev/null
fi

# Auditoría administrativa sin conservar representaciones completas de cambios.
"$KC" update events/config -r "$REALM" -s adminEventsEnabled=true \
  -s adminEventsDetailsEnabled=false >/dev/null

printf 'Realm %s preparado. Cliente web, cliente administrador y usuario inicial configurados.\n' "$REALM"
