"""Puerto independiente del framework: integrar aquí REGEX, RAG, SLM y política."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from .contracts import Accion, Mensaje, SolicitudChat, RespuestaProveedor


class AnalisisNoDisponible(Exception):
    pass


@dataclass(frozen=True)
class DecisionValidada:
    accion: Accion
    codigo_motivo: str  # Solo códigos fijos, nunca justificaciones con PII.
    mensajes_salida: list[Mensaje] | None = None
    validacion_completa: bool = False
    cobertura_verificada: bool = False


@dataclass(frozen=True)
class ContextoEjecucion:
    """Evento único por solicitud; no almacena el token ni el prompt."""
    id_evento: str
    referencia_credencial: str


class PipelineProteccion(Protocol):
    listo: bool

    async def analizar(self, solicitud: SolicitudChat, contexto: ContextoEjecucion) -> DecisionValidada: ...

    async def procesar_respuesta(
        self, solicitud: SolicitudChat, decision: DecisionValidada,
        respuesta: RespuestaProveedor, contexto: ContextoEjecucion
    ) -> RespuestaProveedor: ...


class PipelineNoConfigurado:
    """Fail-closed: nunca autorizamos red por ausencia de detectores/política."""
    listo = False

    async def analizar(self, solicitud: SolicitudChat, contexto: ContextoEjecucion) -> DecisionValidada:
        raise AnalisisNoDisponible("pipeline pendiente")

    async def procesar_respuesta(
        self, solicitud: SolicitudChat, decision: DecisionValidada,
        respuesta: RespuestaProveedor, contexto: ContextoEjecucion
    ) -> RespuestaProveedor:
        raise AnalisisNoDisponible("restitución pendiente")
