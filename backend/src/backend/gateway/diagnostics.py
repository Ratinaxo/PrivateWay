"""Prueba manual de conectividad con un prompt fijo, SIN HTTP y SIN datos de usuarios.

AVISO: este comando deliberadamente no invoca el pipeline. NO debe servir como
endpoint público ni recibir prompts por argumentos. Uso únicamente por operador.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time


from .config import Configuracion, proveedores_desde_entorno
from .contracts import Mensaje, SolicitudChat
from .providers import ProveedorNoDisponible

_PROMPT = "Responde con una sola palabra: LISTO."


async def diagnosticar(alias: str) -> int:
    config = Configuracion.desde_entorno()
    adaptadores = proveedores_desde_entorno()
    ruta = config.rutas.get(alias)
    if ruta is None or ruta.proveedor not in adaptadores:
        print("ERROR: alias no autorizado o adaptador no configurado")
        return 2
    solicitud = SolicitudChat(model=alias, messages=[Mensaje(role="user", content=_PROMPT)])
    inicial = time.monotonic()
    try:
        resultado = await adaptadores[ruta.proveedor].completar(
            ruta.modelo_externo, solicitud.messages, solicitud
        )
    except ProveedorNoDisponible as exc:
        print(f"ERROR: {exc.codigo} (envío potencialmente realizado; revisar consola del proveedor)")
        return 1
    except Exception:
        print("ERROR: FALLO_NO_CLASIFICADO (no se imprime la excepción por privacidad)")
        return 1
    if not resultado.content.strip():
        print("ERROR: RESPUESTA_VACIA")
        return 1
    print(f"OK proveedor={ruta.proveedor} alias={alias} tiempo_ms={int((time.monotonic()-inicial)*1000)} respuesta_valida=true")
    print("Nota: prueba exclusiva del transporte. NO acredita protección ni precisión de la respuesta.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnóstico de transporte con prompt sintético fijo")
    parser.add_argument("--alias", required=True, help="Alias configurado en GATEWAY_ROUTES_JSON")
    args = parser.parse_args()
    try:
        codigo = asyncio.run(diagnosticar(args.alias))
    except (RuntimeError, ValueError, KeyError):
        print("ERROR: CONFIGURACION_INVALIDA")
        codigo = 2
    sys.exit(codigo)


if __name__ == "__main__":
    main()
