"""Prueba HTTP de ida y vuelta sobre el proveedor simulado configurado.

Ejecutar dentro del contenedor backend:
    python -m backend.gateway.smoke

No activa modos especiales ni cambia el pipeline que usa FastAPI.
"""
from __future__ import annotations

import json
import os

import httpx


def main() -> int:
    rutas = json.loads(os.environ.get("GATEWAY_ROUTES_JSON", "{}"))
    proveedores = json.loads(os.environ.get("GATEWAY_PROVIDERS_JSON", "{}"))
    simulados = [
        alias for alias, ruta in rutas.items()
        if isinstance(ruta, dict)
        and proveedores.get(ruta.get("proveedor"), {}).get("tipo") == "simulado"
    ]
    if not simulados:
        print("ERROR: no hay un adaptador simulado configurado")
        return 1
    token = next((t.strip() for t in os.environ.get("GATEWAY_CLIENT_TOKENS", "").split(",") if t.strip()), "")
    if not token:
        print("ERROR: falta el token interno del gateway")
        return 1
    try:
        r = httpx.post(
            "http://127.0.0.1:8000/api/v1/secure-chat",
            headers={"Authorization": "Bearer " + token},
            json={
                "model": simulados[0],
                "messages": [{"role": "user", "content": "RUN 12.345.678-5 y correo persona@ejemplo.cl"}],
                "stream": False,
            },
            timeout=15,
        )
        body = r.json()
        accion = body.get("decision", {}).get("accion")
        correcto = (r.status_code == 200 and accion == "seudonimizar"
                    and bool(body.get("respuesta", {}).get("choices")))
    except (httpx.RequestError, TypeError, ValueError, KeyError, AttributeError):
        print("ERROR: no fue posible completar el recorrido HTTP")
        return 1
    print("Recorrido REGEX -> gateway -> simulado -> retorno:", "OK" if correcto else "ERROR")
    print("HTTP:", r.status_code, "| accion:", accion)
    return 0 if correcto else 1


if __name__ == "__main__":
    raise SystemExit(main())
