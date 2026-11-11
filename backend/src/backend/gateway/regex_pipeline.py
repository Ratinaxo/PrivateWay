"""Pipeline REGEX: detección, seudonimización y revisión del retorno.

Se usa con cualquier adaptador configurado en el catálogo; la etapa REGEX
solo cubre entidades estructuradas y no reemplaza la detección semántica.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from backend.deteccion.hallazgo import Categoria, Hallazgo

from .contracts import Accion, Mensaje, RespuestaProveedor, SolicitudChat
from .pipeline import AnalisisNoDisponible, ContextoEjecucion, DecisionValidada

_MAX_TEXTO_TOTAL = 120_000
_CATEGORIAS_PRIORIDAD = (Categoria.RUN, Categoria.CORREO, Categoria.TELEFONO)


class DetectorEstructurado(Protocol):
    def analizar(self, texto: str) -> list[Hallazgo]: ...


@dataclass(frozen=True)
class _Tramo:
    inicio: int
    fin: int
    categorias: frozenset[Categoria]


def _fusionar_tramos(texto: str, hallazgos: list[Hallazgo]) -> list[_Tramo]:
    """Unifica intervalos solapados sin dejar fragmentos de PII en el texto."""
    ordenados = sorted(hallazgos, key=lambda h: (h.inicio, h.fin))
    tramos: list[_Tramo] = []
    for hallazgo in ordenados:
        if (not isinstance(hallazgo.categoria, Categoria)
            or not isinstance(hallazgo.inicio, int)
            or not isinstance(hallazgo.fin, int)
            or hallazgo.inicio < 0
            or hallazgo.fin > len(texto)
            or hallazgo.fin <= hallazgo.inicio
            or texto[hallazgo.inicio:hallazgo.fin] != hallazgo.valor):
            raise AnalisisNoDisponible("detector devolvió una evidencia inválida")
        if tramos and hallazgo.inicio < tramos[-1].fin:
            previo = tramos[-1]
            tramos[-1] = _Tramo(
                previo.inicio, max(previo.fin, hallazgo.fin),
                previo.categorias | frozenset((hallazgo.categoria,)),
            )
        else:
            tramos.append(_Tramo(
                hallazgo.inicio, hallazgo.fin, frozenset((hallazgo.categoria,))
            ))
    return tramos


def seudonimizar_texto(
    texto: str, hallazgos: list[Hallazgo], etiquetas: dict[tuple[Categoria, str], str]
) -> str:
    """Sustituye cada tramo detectado usando marcadores locales de la solicitud.

    Los valores originales solo residen en ``etiquetas`` durante la ejecución.
    No se almacenan en la auditoría ni se restituyen automáticamente.
    """
    tramos = _fusionar_tramos(texto, hallazgos)
    partes: list[str] = []
    cursor = 0
    for tramo in tramos:
        categoria = next(c for c in _CATEGORIAS_PRIORIDAD if c in tramo.categorias)
        valor = texto[tramo.inicio:tramo.fin]
        clave = (categoria, valor)
        if clave not in etiquetas:
            contador = 1 + sum(c == categoria for c, _ in etiquetas)
            etiquetas[clave] = f"[PW_{categoria.name}_{contador}]"
        partes.extend((texto[cursor:tramo.inicio], etiquetas[clave]))
        cursor = tramo.fin
    partes.append(texto[cursor:])
    return "".join(partes)


class PipelineRegex:
    """Pipeline REGEX activo por defecto para los proveedores configurados.

    ``listo`` indica que esta etapa de REGEX fue inicializada, no que
    el sistema tenga cobertura semántica o protección integral de privacidad.
    """
    listo = True

    def __init__(self, *, detector: DetectorEstructurado | None = None) -> None:
        if detector is None:
            from backend.deteccion.regex import EtapaRegex
            detector = EtapaRegex()
        self._detector = detector

    def _detectar(self, texto: str) -> list[Hallazgo]:
        try:
            return self._detector.analizar(texto)
        except Exception:
            # Nunca interpolar textos o errores de Presidio en logs/respuestas.
            raise AnalisisNoDisponible("detección REGEX no disponible") from None

    async def analizar(
        self, solicitud: SolicitudChat, contexto: ContextoEjecucion
    ) -> DecisionValidada:
        if sum(len(m.content) for m in solicitud.messages) > _MAX_TEXTO_TOTAL:
            return DecisionValidada(
                accion=Accion.BLOQUEAR, codigo_motivo="REGEX_LIMITE_TEXTO",
                validacion_completa=True,
            )

        etiquetas: dict[tuple[Categoria, str], str] = {}
        nuevos: list[Mensaje] = []
        hubo_deteccion = False
        for mensaje in solicitud.messages:
            hallazgos = self._detectar(mensaje.content)
            if hallazgos:
                hubo_deteccion = True
            saneado = seudonimizar_texto(mensaje.content, hallazgos, etiquetas)
            # Si el detector sigue encontrando coincidencias en la salida,
            # la cobertura NO está comprobada y no se enviará la solicitud.
            if self._detectar(saneado):
                raise AnalisisNoDisponible("seudonimización incompleta")
            try:
                nuevos.append(Mensaje(role=mensaje.role, content=saneado))
            except Exception:
                raise AnalisisNoDisponible("mensaje seudonimizado inválido") from None

        if not hubo_deteccion:
            return DecisionValidada(
                accion=Accion.PERMITIR, codigo_motivo="REGEX_SIN_COINCIDENCIAS",
                mensajes_salida=nuevos, validacion_completa=True,
            )
        return DecisionValidada(
            accion=Accion.SEUDONIMIZAR, codigo_motivo="REGEX_SEUDONIMIZADO",
            mensajes_salida=nuevos, validacion_completa=True, cobertura_verificada=True,
        )

    async def procesar_respuesta(
        self, solicitud: SolicitudChat, decision: DecisionValidada,
        respuesta: RespuestaProveedor, contexto: ContextoEjecucion
    ) -> RespuestaProveedor:
        # No restitución (no hay mecanismo validado). Rechazar respuestas que
        # introduzcan nueva PII estructurada antes de mostrarlas al navegador.
        if not isinstance(respuesta.content, str) or len(respuesta.content) > _MAX_TEXTO_TOTAL:
            raise AnalisisNoDisponible("respuesta no procesable")
        if self._detectar(respuesta.content):
            raise AnalisisNoDisponible("respuesta con PII estructurada")
        return respuesta
