"""Adaptadores de transporte hacia APIs externas.

Las URLs de proveedores nativos están fijadas en el código. Las claves y los modelos
se seleccionan exclusivamente desde la configuración del backend. Ningún adaptador
realiza reintentos automáticos de POST (el proveedor podría haber recibido la petición).
"""
from __future__ import annotations

import ipaddress
import os
import re
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import quote, urlsplit

import httpx

from .contracts import Mensaje, RespuestaProveedor, SolicitudChat

_MAX_RESPONSE_BYTES = 2_000_000
_TIMEOUT = httpx.Timeout(connect=5.0, read=45.0, write=10.0, pool=5.0)
_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")


class ProveedorNoDisponible(Exception):
    """Error interno con categoría fija, nunca contenido devuelto por el proveedor."""

    def __init__(self, codigo: str = "PROVEEDOR_ERROR") -> None:
        super().__init__(codigo)
        self.codigo = codigo


class AdaptadorProveedor(Protocol):
    async def completar(
        self, modelo: str, mensajes: list[Mensaje], solicitud: SolicitudChat
    ) -> RespuestaProveedor: ...


class ProveedorSimulado:
    """Sólo para pruebas. Nunca llama a Internet."""

    async def completar(
        self, modelo: str, mensajes: list[Mensaje], solicitud: SolicitudChat
    ) -> RespuestaProveedor:
        return RespuestaProveedor(content="Respuesta simulada: no se llamó a un LLM externo.")


def _clave(variable: str) -> str:
    key = os.environ.get(variable, "").strip()
    if not key:
        raise ProveedorNoDisponible("CLAVE_NO_CONFIGURADA")
    return key


def _validar_modelo(modelo: str) -> str:
    # Impide interpolar rutas, queries o fragmentos de URL en el caso Gemini.
    if not _MODEL_ID.fullmatch(modelo):
        raise ProveedorNoDisponible("MODELO_INVALIDO")
    return modelo


async def _post_json(
    url: str,
    headers: dict[str, str],
    payload: dict,
    transport: httpx.AsyncBaseTransport | None,
) -> dict:
    # trust_env=False evita que variables como HTTPS_PROXY cambien la ruta de salida.
    # follow_redirects=False evita remisiones a destinos no autorizados.
    try:
        async with httpx.AsyncClient(
            timeout=_TIMEOUT,
            transport=transport,
            follow_redirects=False,
            trust_env=False,
        ) as cliente:
            async with cliente.stream("POST", url, headers=headers, json=payload) as respuesta:
                if respuesta.status_code in (401, 403):
                    raise ProveedorNoDisponible("CREDENCIAL_RECHAZADA")
                if respuesta.status_code == 429:
                    raise ProveedorNoDisponible("LIMITE_PROVEEDOR")
                if respuesta.status_code != 200:
                    raise ProveedorNoDisponible("HTTP_PROVEEDOR")
                chunks: list[bytes] = []
                total = 0
                async for chunk in respuesta.aiter_bytes():
                    total += len(chunk)
                    if total > _MAX_RESPONSE_BYTES:
                        raise ProveedorNoDisponible("RESPUESTA_DEMASIADO_GRANDE")
                    chunks.append(chunk)
                try:
                    datos = httpx.Response(200, content=b"".join(chunks)).json()
                except ValueError as exc:
                    raise ProveedorNoDisponible("RESPUESTA_INVALIDA") from exc
                if not isinstance(datos, dict):
                    raise ProveedorNoDisponible("RESPUESTA_INVALIDA")
                return datos
    except httpx.TimeoutException as exc:
        raise ProveedorNoDisponible("TIMEOUT_PROVEEDOR") from exc
    except httpx.RequestError as exc:
        raise ProveedorNoDisponible("RED_PROVEEDOR") from exc


def _texto(valor: object) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ProveedorNoDisponible("RESPUESTA_INVALIDA")
    return valor


def _normalizar_fin(razon: object) -> str:
    if razon in ("length", "max_tokens", "MAX_TOKENS"):
        return "length"
    return "stop"


@dataclass(frozen=True)
class ProveedorOpenAI:
    api_key_env: str
    transport: httpx.AsyncBaseTransport | None = field(default=None, repr=False, compare=False)

    async def completar(self, modelo: str, mensajes: list[Mensaje], solicitud: SolicitudChat) -> RespuestaProveedor:
        _validar_modelo(modelo)
        payload: dict = {
            "model": modelo,
            "messages": [m.model_dump() for m in mensajes],
            "stream": False,
        }
        if solicitud.temperature is not None:
            payload["temperature"] = solicitud.temperature
        if solicitud.max_tokens is not None:
            payload["max_completion_tokens"] = solicitud.max_tokens
        datos = await _post_json(
            "https://api.openai.com/v1/chat/completions",
            {"Authorization": "Bearer " + _clave(self.api_key_env)},
            payload, self.transport,
        )
        try:
            eleccion = datos["choices"][0]
            contenido = _texto(eleccion["message"]["content"])
            return RespuestaProveedor(content=contenido, finish_reason=_normalizar_fin(eleccion.get("finish_reason")))
        except (KeyError, IndexError, TypeError) as exc:
            raise ProveedorNoDisponible("RESPUESTA_INVALIDA") from exc


@dataclass(frozen=True)
class ProveedorAnthropic:
    api_key_env: str
    transport: httpx.AsyncBaseTransport | None = field(default=None, repr=False, compare=False)

    async def completar(self, modelo: str, mensajes: list[Mensaje], solicitud: SolicitudChat) -> RespuestaProveedor:
        _validar_modelo(modelo)
        # Un rol developer no posee representación idéntica en Messages API.
        if any(m.role == "developer" for m in mensajes):
            raise ProveedorNoDisponible("ROL_NO_SOPORTADO")
        system = [m.content for m in mensajes if m.role == "system"]
        if len(system) > 1:
            raise ProveedorNoDisponible("ROL_NO_SOPORTADO")
        conversation = [m.model_dump() for m in mensajes if m.role in ("user", "assistant")]
        if not conversation:
            raise ProveedorNoDisponible("MENSAJES_INVALIDOS")
        payload: dict = {
            "model": modelo,
            "messages": conversation,
            "max_tokens": solicitud.max_tokens or 256,
        }
        if system:
            payload["system"] = system[0]
        if solicitud.temperature is not None:
            payload["temperature"] = solicitud.temperature
        datos = await _post_json(
            "https://api.anthropic.com/v1/messages",
            {"x-api-key": _clave(self.api_key_env), "anthropic-version": "2023-06-01"},
            payload, self.transport,
        )
        try:
            if datos.get("stop_reason") == "tool_use":
                raise ProveedorNoDisponible("RESPUESTA_INVALIDA")
            bloques = datos["content"]
            if not isinstance(bloques, list) or not bloques:
                raise ProveedorNoDisponible("RESPUESTA_INVALIDA")
            if any(not isinstance(b, dict) or b.get("type") != "text" for b in bloques):
                raise ProveedorNoDisponible("RESPUESTA_INVALIDA")
            contenido = _texto("".join(_texto(b["text"]) for b in bloques))
            return RespuestaProveedor(content=contenido, finish_reason=_normalizar_fin(datos.get("stop_reason")))
        except (KeyError, IndexError, TypeError) as exc:
            raise ProveedorNoDisponible("RESPUESTA_INVALIDA") from exc


@dataclass(frozen=True)
class ProveedorGemini:
    api_key_env: str
    transport: httpx.AsyncBaseTransport | None = field(default=None, repr=False, compare=False)

    async def completar(self, modelo: str, mensajes: list[Mensaje], solicitud: SolicitudChat) -> RespuestaProveedor:
        _validar_modelo(modelo)
        if any(m.role == "developer" for m in mensajes):
            raise ProveedorNoDisponible("ROL_NO_SOPORTADO")
        system = [m.content for m in mensajes if m.role == "system"]
        if len(system) > 1:
            raise ProveedorNoDisponible("ROL_NO_SOPORTADO")
        contents = [
            {"role": "model" if m.role == "assistant" else "user", "parts": [{"text": m.content}]}
            for m in mensajes if m.role in ("assistant", "user")
        ]
        if not contents:
            raise ProveedorNoDisponible("MENSAJES_INVALIDOS")
        payload: dict = {"contents": contents}
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system[0]}]}
        generation: dict = {}
        if solicitud.temperature is not None:
            generation["temperature"] = solicitud.temperature
        if solicitud.max_tokens is not None:
            generation["maxOutputTokens"] = solicitud.max_tokens
        if generation:
            payload["generationConfig"] = generation
        datos = await _post_json(
            "https://generativelanguage.googleapis.com/v1beta/models/" + quote(modelo, safe="") + ":generateContent",
            {"x-goog-api-key": _clave(self.api_key_env)},
            payload, self.transport,
        )
        try:
            candidato = datos["candidates"][0]
            motivo = candidato.get("finishReason")
            if motivo not in ("STOP", "MAX_TOKENS"):
                raise ProveedorNoDisponible("RESPUESTA_INVALIDA")
            partes = candidato["content"]["parts"]
            if not isinstance(partes, list) or not partes:
                raise ProveedorNoDisponible("RESPUESTA_INVALIDA")
            if any(not isinstance(p, dict) or "text" not in p for p in partes):
                raise ProveedorNoDisponible("RESPUESTA_INVALIDA")
            contenido = _texto("".join(_texto(p["text"]) for p in partes))
            return RespuestaProveedor(content=contenido, finish_reason=_normalizar_fin(motivo))
        except (KeyError, IndexError, TypeError) as exc:
            raise ProveedorNoDisponible("RESPUESTA_INVALIDA") from exc


@dataclass(frozen=True)
class ProveedorCompatibleChat:
    """Para un servicio compatible con chat completions, autorizando el host explícitamente."""
    base_url: str
    api_key_env: str
    allowed_hosts: tuple[str, ...] = ()
    transport: httpx.AsyncBaseTransport | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        p = urlsplit(self.base_url)
        if (p.scheme != "https" or not p.hostname or p.username or p.password
                or p.query or p.fragment or p.port not in (None, 443)):
            raise ValueError("La URL del proveedor debe ser HTTPS administrada")
        try:
            ipaddress.ip_address(p.hostname)
        except ValueError:
            pass
        else:
            raise ValueError("No se aceptan IP literales como destino externo")
        if p.hostname not in self.allowed_hosts:
            raise ValueError("El host no pertenece a la lista de egreso permitida")

    async def completar(self, modelo: str, mensajes: list[Mensaje], solicitud: SolicitudChat) -> RespuestaProveedor:
        _validar_modelo(modelo)
        payload: dict = {
            "model": modelo,
            "messages": [m.model_dump() for m in mensajes],
            "stream": False,
        }
        if solicitud.temperature is not None:
            payload["temperature"] = solicitud.temperature
        if solicitud.max_tokens is not None:
            payload["max_tokens"] = solicitud.max_tokens
        datos = await _post_json(
            self.base_url.rstrip("/") + "/chat/completions",
            {"Authorization": "Bearer " + _clave(self.api_key_env)},
            payload, self.transport,
        )
        try:
            eleccion = datos["choices"][0]
            return RespuestaProveedor(
                content=_texto(eleccion["message"]["content"]),
                finish_reason=_normalizar_fin(eleccion.get("finish_reason")),
            )
        except (KeyError, IndexError, TypeError) as exc:
            raise ProveedorNoDisponible("RESPUESTA_INVALIDA") from exc