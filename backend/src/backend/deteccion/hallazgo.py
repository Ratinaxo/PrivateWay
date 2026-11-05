"""Tipos que entrega cada etapa de análisis a la siguiente"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Categoria(str, Enum):
    """Clasificación de los datos detectados."""

    RUN = "run"
    CORREO = "correo"
    TELEFONO = "telefono"


class Procedencia(str, Enum):
    """Etapa que produjo el hallazgo."""

    REGEX = "regex"
    SLM = "slm"


@dataclass(frozen=True)
class Hallazgo:
    """Una ocurrencia detectada en la consulta.

    `inicio` y `fin` son índices sobre el texto original, de modo que podamos volver a buscar dentro del prompt
    `verificado` lo usamos para comprobar el digito verificador con modulo 11 por ahora.
    
    """

    categoria: Categoria
    valor: str
    inicio: int
    fin: int
    reconocedor: str
    procedencia: Procedencia
    confianza: float
    verificado: bool = False

    def __post_init__(self) -> None:
        if self.inicio < 0 or self.fin <= self.inicio:
            raise ValueError("el tramo del hallazgo es inválido")
        if not 0.0 <= self.confianza <= 1.0:
            raise ValueError("la confianza debe estar entre 0 y 1")
