"""Contratos del pipeline de PrivateWay para detección y procesamiento."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol
from .contracts import Accion, Mensaje, SolicitudChat, RespuestaProveedor


class AnalisisNoDisponible(Exception):
    def __init__(self, mensaje="analisis no disponible", *, codigo="ANALISIS_NO_DISPONIBLE"):
        super().__init__(mensaje)
        self.codigo = codigo


@dataclass(frozen=True)
class DecisionValidada:
    accion: Accion
    codigo_motivo: str  # Solo códigos fijos, nunca justificaciones con PII.
    mensajes_salida: list[Mensaje] | None = None
    validacion_completa: bool = False
    cobertura_verificada: bool = False
    traza: dict = field(default_factory=dict, repr=False)


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

