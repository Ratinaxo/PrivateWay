"""Resultado de detectores locales; los desplazamientos se refieren al texto recibido.

El gateway es responsable de aplicar la política a estos hallazgos.
Evitar imprimir o serializar ``valor`` en auditoría o logs: puede contener PII.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Categoria(str, Enum):
    RUN = "run"
    CORREO = "correo"
    TELEFONO = "telefono"
    TARJETA = "tarjeta"
    PATENTE = "patente"
    PERSONA = "persona"
    DIRECCION = "direccion"
    IDENTIFICADOR = "identificador"
    ORIGEN_ETNICO = "origen_etnico"
    AFILIACION = "afiliacion"
    SOCIOECONOMICO = "socioeconomico"
    SALUD = "salud"
    CONVICCIONES = "convicciones"
    PERFIL_BIOLOGICO = "perfil_biologico"
    BIOMETRICO = "biometrico"
    SEXUALIDAD = "sexualidad"
    MENOR_DE_EDAD = "menor_de_edad"
    GEOLOCALIZACION = "geolocalizacion"
    OBLIGACIONES = "obligaciones"
    INFRACCIONES = "infracciones"


class ClaseLegal(str, Enum):
    IDENTIFICADOR = "identificador_dato_personal"
    SENSIBLE = "dato_personal_sensible"
    REGIMEN_ESPECIAL = "categoria_regimen_especial"


CLASE_POR_CATEGORIA = {
    Categoria.PERSONA: ClaseLegal.IDENTIFICADOR,
    Categoria.RUN: ClaseLegal.IDENTIFICADOR,
    Categoria.CORREO: ClaseLegal.IDENTIFICADOR,
    Categoria.TELEFONO: ClaseLegal.IDENTIFICADOR,
    Categoria.TARJETA: ClaseLegal.IDENTIFICADOR,
    Categoria.PATENTE: ClaseLegal.IDENTIFICADOR,
    Categoria.DIRECCION: ClaseLegal.IDENTIFICADOR,
    Categoria.IDENTIFICADOR: ClaseLegal.IDENTIFICADOR,
    Categoria.ORIGEN_ETNICO: ClaseLegal.SENSIBLE,
    Categoria.AFILIACION: ClaseLegal.SENSIBLE,
    Categoria.SOCIOECONOMICO: ClaseLegal.SENSIBLE,
    Categoria.CONVICCIONES: ClaseLegal.SENSIBLE,
    Categoria.SALUD: ClaseLegal.SENSIBLE,
    Categoria.PERFIL_BIOLOGICO: ClaseLegal.SENSIBLE,
    Categoria.BIOMETRICO: ClaseLegal.SENSIBLE,
    Categoria.SEXUALIDAD: ClaseLegal.SENSIBLE,
    Categoria.MENOR_DE_EDAD: ClaseLegal.REGIMEN_ESPECIAL,
    Categoria.GEOLOCALIZACION: ClaseLegal.REGIMEN_ESPECIAL,
    Categoria.OBLIGACIONES: ClaseLegal.REGIMEN_ESPECIAL,
    Categoria.INFRACCIONES: ClaseLegal.REGIMEN_ESPECIAL,
}

SUBCATEGORIAS_SENSIBLES = {
    Categoria.ORIGEN_ETNICO: frozenset({"origen étnico", "origen racial"}),
    Categoria.AFILIACION: frozenset({"afiliación política", "afiliación sindical", "afiliación gremial"}),
    Categoria.SOCIOECONOMICO: frozenset({"situación socioeconómica"}),
    Categoria.CONVICCIONES: frozenset({"convicciones ideológicas", "convicciones filosóficas", "creencias religiosas"}),
    Categoria.SALUD: frozenset({"datos relativos a la salud"}),
    Categoria.PERFIL_BIOLOGICO: frozenset({"datos genéticos", "datos proteómicos", "datos metabólicos", "muestras biológicas"}),
    Categoria.BIOMETRICO: frozenset({"huella digital", "iris", "rasgos de la mano", "rasgos faciales", "voz", "características conductuales"}),
    Categoria.SEXUALIDAD: frozenset({"vida sexual", "orientación sexual", "identidad de género"}),
}


class Procedencia(str, Enum):
    REGEX = "regex"
    SLM = "slm"
    HIBRIDA = "regex+slm"


@dataclass(frozen=True)
class Hallazgo:
    categoria: Categoria
    valor: str = field(repr=False)  # PII
    inicio: int
    fin: int
    reconocedor: str
    procedencia: Procedencia
    confianza: float | None
    verificado: bool = False
    subcategoria: str | None = None
    asociado_a: str | None = field(default=None, repr=False)
    clase_legal: ClaseLegal = field(init=False)

    def __post_init__(self) -> None:
        if self.inicio < 0 or self.fin <= self.inicio:
            raise ValueError("el tramo del hallazgo es inválido")
        if len(self.valor) != self.fin - self.inicio:
            raise ValueError("el valor del hallazgo no coincide con el tramo")
        if self.confianza is not None and not 0.0 <= self.confianza <= 1.0:
            raise ValueError("la confianza debe estar entre 0 y 1")
        object.__setattr__(self, "clase_legal", CLASE_POR_CATEGORIA[self.categoria])
