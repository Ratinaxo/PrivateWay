"""Catálogo de alias y proveedores; sólo lo administra el servidor."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

from backend.gateway.providers import (
    AdaptadorProveedor, ProveedorAnthropic, ProveedorCompatibleChat,
    ProveedorGemini, ProveedorOpenAI,
)

_ALIAS = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
_NOMBRE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_VARIABLES_CREDENCIAL_NATIVAS = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
}
_VARIABLE_CREDENCIAL_COMPATIBLE = "PRIVATEWAY_COMPATIBLE_API_KEY"


def _validar_credencial(tipo: str, valor: object) -> str:
    """Limita cada adaptador a su variable de API, sin exponer otros secretos."""
    if tipo in _VARIABLES_CREDENCIAL_NATIVAS:
        variable = _VARIABLES_CREDENCIAL_NATIVAS[tipo]
        if valor != variable:
            raise RuntimeError("Nombre de variable de credencial inválido")
        return variable
    if tipo == "compatible_chat" and valor == _VARIABLE_CREDENCIAL_COMPATIBLE:
        return _VARIABLE_CREDENCIAL_COMPATIBLE
    raise RuntimeError("Nombre de variable de credencial inválido")


@dataclass(frozen=True)
class RutaModelo:
    proveedor: str
    modelo_externo: str


@dataclass(frozen=True)
class Configuracion:
    tokens_cliente: tuple[str, ...]
    rutas: dict[str, RutaModelo]

    @classmethod
    def desde_entorno(cls) -> "Configuracion":
        tokens = tuple(x.strip() for x in os.environ.get("GATEWAY_CLIENT_TOKENS", "").split(",") if x.strip())
        if not tokens or any(len(t) < 24 for t in tokens):
            raise RuntimeError("Configure GATEWAY_CLIENT_TOKENS con tokens de al menos 24 caracteres")
        rutas_json = os.environ.get("GATEWAY_ROUTES_JSON", "").strip() or "{}"
        rutas_entrada = json.loads(rutas_json)
        if not isinstance(rutas_entrada, dict):
            raise RuntimeError("GATEWAY_ROUTES_JSON debe ser un objeto")
        rutas = {}
        for alias, valor in rutas_entrada.items():
            if not isinstance(alias, str) or not _ALIAS.fullmatch(alias):
                raise RuntimeError("Alias inválido en el catálogo")
            if not isinstance(valor, dict):
                raise RuntimeError("Ruta de modelo inválida")
            proveedor, modelo = valor.get("proveedor"), valor.get("modelo_externo")
            if not isinstance(proveedor, str) or not _NOMBRE.fullmatch(proveedor):
                raise RuntimeError("Proveedor inválido en una ruta")
            if not isinstance(modelo, str) or not _ALIAS.fullmatch(modelo):
                raise RuntimeError("Nombre externo de modelo inválido")
            rutas[alias] = RutaModelo(proveedor=proveedor, modelo_externo=modelo)
        return cls(tokens_cliente=tokens, rutas=rutas)


def proveedores_desde_entorno() -> dict[str, AdaptadorProveedor]:
    proveedores_json = os.environ.get("GATEWAY_PROVIDERS_JSON", "").strip() or "{}"
    configurados = json.loads(proveedores_json)
    if not isinstance(configurados, dict):
        raise RuntimeError("GATEWAY_PROVIDERS_JSON debe ser un objeto")
    allow = tuple(x.strip().lower() for x in os.environ.get("GATEWAY_ALLOWED_PROVIDER_HOSTS", "").split(",") if x.strip())
    adaptadores: dict[str, AdaptadorProveedor] = {}
    for nombre, conf in configurados.items():
        if not isinstance(nombre, str) or not _NOMBRE.fullmatch(nombre) or not isinstance(conf, dict):
            raise RuntimeError("Configuración de proveedor inválida")
        tipo = conf.get("tipo")
        if tipo in ("openai", "anthropic", "gemini"):
            clave = _validar_credencial(tipo, conf.get("api_key_env"))
            if tipo == "openai":
                adaptadores[nombre] = ProveedorOpenAI(api_key_env=clave)
            elif tipo == "anthropic":
                adaptadores[nombre] = ProveedorAnthropic(api_key_env=clave)
            else:
                adaptadores[nombre] = ProveedorGemini(api_key_env=clave)
        elif tipo == "compatible_chat":
            clave = _validar_credencial(tipo, conf.get("api_key_env"))
            adaptadores[nombre] = ProveedorCompatibleChat(
                base_url=conf["base_url"], api_key_env=clave, allowed_hosts=allow,
            )
        elif tipo == "simulado":
            # El simulador queda reservado para pruebas con adaptadores inyectados.
            # Ignorar una ruta antigua deja que readiness/API informen el estado
            # explícito sin habilitar un proveedor ficticio en runtime.
            continue
        else:
            raise RuntimeError("Tipo de proveedor no permitido")
    return adaptadores
