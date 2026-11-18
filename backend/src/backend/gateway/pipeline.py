"""Contratos del pipeline de PrivateWay para detección y procesamiento."""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Protocol
from cryptography.fernet import Fernet
from .contracts import Accion, Mensaje, SolicitudChat, RespuestaProveedor

PATRON_MARCADOR = re.compile(r"\[PW_[A-Z]+_[a-p]{32}\]")


class AnalisisNoDisponible(Exception):
    def __init__(self, mensaje="analisis no disponible", *, codigo="ANALISIS_NO_DISPONIBLE"):
        super().__init__(mensaje)
        self.codigo = codigo


def aplicar_correspondencias(texto: str, valores: dict[str, str]) -> str:
    longitud = len(texto)

    def sustituir(coincidencia: re.Match[str]) -> str:
        nonlocal longitud
        marcador = coincidencia.group()
        valor = valores.get(marcador, marcador)
        longitud += len(valor) - len(marcador)
        if longitud > 120_000:
            raise AnalisisNoDisponible("respuesta restaurada demasiado larga")
        return valor

    return PATRON_MARCADOR.sub(sustituir, texto)


@dataclass(frozen=True)
class DecisionValidada:
    accion: Accion
    codigo_motivo: str  # Solo códigos fijos, nunca justificaciones con PII.
    mensajes_salida: list[Mensaje] | None = None
    validacion_completa: bool = False
    cobertura_verificada: bool = False
    traza: dict = field(default_factory=dict, repr=False)
    restitucion: Restitucion | None = field(default=None, repr=False)


@dataclass(frozen=True)
class ContextoEjecucion:
    """Evento único por solicitud; no almacena el token ni el prompt."""
    id_evento: str
    referencia_credencial: str


class Restitucion:
    """Correspondencias cifradas, limitadas al ciclo de una solicitud."""

    def __init__(self, contexto: ContextoEjecucion, valores: dict[str, str]):
        self._contexto = contexto
        self._cifrador = Fernet(Fernet.generate_key())
        self._valores = {
            marcador: self._cifrador.encrypt(valor.encode("utf-8"))
            for marcador, valor in valores.items()
        }

    def valores(self, contexto: ContextoEjecucion) -> dict[str, str]:
        if contexto != self._contexto:
            raise AnalisisNoDisponible("contexto de restitución inválido")
        return {k: self._cifrador.decrypt(v).decode("utf-8") for k, v in self._valores.items()}

    def aplicar(self, texto: str, contexto: ContextoEjecucion) -> str:
        return aplicar_correspondencias(texto, self.valores(contexto))


class PipelineProteccion(Protocol):
    listo: bool

    async def analizar(self, solicitud: SolicitudChat, contexto: ContextoEjecucion) -> DecisionValidada: ...

    async def procesar_respuesta(
        self, solicitud: SolicitudChat, decision: DecisionValidada,
        respuesta: RespuestaProveedor, contexto: ContextoEjecucion
    ) -> RespuestaProveedor: ...

