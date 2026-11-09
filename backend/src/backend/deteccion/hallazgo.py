"""Resultado de detectores locales; los desplazamientos se refieren al texto recibido.

Este contrato NO autoriza transmitir prompts. El gateway aplica la política por separado.
Evitar imprimir o serializar ``valor`` en auditoría o logs: puede contener PII.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Categoria(str, Enum):
    RUN = "run"
    CORREO = "correo"
    TELEFONO = "telefono"


class Procedencia(str, Enum):
    REGEX = "regex"
    SLM = "slm"


@dataclass(frozen=True)
class Hallazgo:
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
        if len(self.valor) != self.fin - self.inicio:
            raise ValueError("el valor del hallazgo no coincide con el tramo")
        if not 0.0 <= self.confianza <= 1.0:
            raise ValueError("la confianza debe estar entre 0 y 1")
