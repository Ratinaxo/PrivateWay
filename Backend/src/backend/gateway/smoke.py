"""Chequeo local de readiness y disponibilidad, sin enviar prompts a proveedores.

Ejecutar dentro del contenedor backend:
    python -m backend.gateway.smoke

Si no hay proveedor utilizable, comprueba que el chat devuelve el error seguro
PROVEEDOR_NO_DISPONIBLE. Nunca envía contenido cuando hay una ruta preparada.
"""
from __future__ import annotations

import os

import httpx


_BASE = "http://127.0.0.1:8000"


def _codigo(respuesta: httpx.Response) -> str | None:
    try:
        error = respuesta.json().get("error", {})
        return error.get("code") if isinstance(error, dict) else None
    except (TypeError, ValueError):
        return None


def main() -> int:
    token = next((t.strip() for t in os.environ.get("GATEWAY_CLIENT_TOKENS", "").split(",") if t.strip()), "")
    if not token:
        print("ERROR: falta el token interno del gateway")
        return 1

    try:
        with httpx.Client(timeout=8, trust_env=False) as cliente:
            ready = cliente.get(_BASE + "/ready")
            catalogo = cliente.get(_BASE + "/api/v1/models",
                                   headers={"Authorization": "Bearer " + token})
            if catalogo.status_code == 200:
                # Catálogo utilizable: no ejecutar POST, porque podría transmitir
                # el prompt a un proveedor real.
                aliases = [modelo.get("id") for proveedor in catalogo.json().get("providers", [])
                           for modelo in proveedor.get("models", [])]
                correcto = ready.status_code == 200 and bool(aliases)
                print("Readiness:", ready.status_code, "| catálogo:", catalogo.status_code,
                      "| alias disponibles:", len(aliases))
                print("Chequeo sin envío a proveedor:", "OK" if correcto else "ERROR")
                return 0 if correcto else 1

            if catalogo.status_code != 503 or _codigo(catalogo) != "PROVEEDOR_NO_DISPONIBLE":
                print("ERROR: catálogo respondió con un estado inesperado:", catalogo.status_code)
                return 1

            # No existe ninguna ruta preparada. La API debe rechazar antes de
            # analizar/transmitir; el alias fijo no corresponde a ningún proveedor.
            respuesta = cliente.post(
                _BASE + "/api/v1/secure-chat",
                headers={"Authorization": "Bearer " + token},
                json={"model": "smoke-sin-proveedor",
                      "messages": [{"role": "user", "content": "Chequeo sintético sin PII."}],
                      "stream": False},
            )
    except (httpx.RequestError, TypeError, ValueError, KeyError, AttributeError):
        print("ERROR: no fue posible completar el chequeo HTTP local")
        return 1

    correcto = (respuesta.status_code == 503
                and _codigo(respuesta) == "PROVEEDOR_NO_DISPONIBLE")
    print("Readiness:", ready.status_code, "| catálogo:", catalogo.status_code,
          "| chat sin proveedor:", respuesta.status_code,
          "| error:", _codigo(respuesta))
    print("Fallo cerrado sin proveedor:", "OK" if correcto else "ERROR")
    return 0 if correcto else 1


if __name__ == "__main__":
    raise SystemExit(main())
