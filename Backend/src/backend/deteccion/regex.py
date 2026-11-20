"""Detección estructurada offline mediante reconocedores de patrones de Presidio.

No se crea ``AnalyzerEngine`` ni se descarga un modelo NLP: los
reconocedores son ``PatternRecognizer`` ejecutados localmente. Este módulo
devuelve hallazgos; el gateway orquesta su tratamiento y selecciona el
adaptador configurado.
"""
from __future__ import annotations

from collections.abc import Sequence
import re

from presidio_analyzer import Pattern, PatternRecognizer, RecognizerResult

from . import run
from .hallazgo import Categoria, Hallazgo, Procedencia

IDIOMA = "es"
_PUNTAJE_PATRON = 0.5


class ReconocedorRun(PatternRecognizer):
    """RUN/RUT chileno con dígito verificador comprobado por módulo 11."""

    def __init__(self) -> None:
        super().__init__(
            supported_entity=Categoria.RUN.name,
            name="run_chileno",
            supported_language=IDIOMA,
            patterns=[
                Pattern(
                    name="run",
                    regex=(
                        r"(?<![\w.-])"
                        r"(?:\d{1,2}(?:\.\d{3}){2}|\d{7,8})"
                        r"\s*-?\s*"
                        r"[\dkK]"
                        r"(?![\w-])"
                    ),
                    score=_PUNTAJE_PATRON,
                )
            ],
            context=["run", "rut", "rol único", "registro único", "cédula"],
        )

    def validate_result(self, pattern_text: str) -> bool:
        return run.es_valido(pattern_text)


class ReconocedorCorreo(PatternRecognizer):
    """Correos sin consultas DNS, eTLD ni validación remota."""

    def __init__(self) -> None:
        super().__init__(
            supported_entity=Categoria.CORREO.name,
            name="correo",
            supported_language=IDIOMA,
            patterns=[
                Pattern(
                    name="correo",
                    regex=(
                        r"(?<![\w.@])"
                        r"[\w+%-]+(?:\.[\w+%-]+)*"
                        r"@"
                        r"[\w-]+(?:\.[\w-]+)+"
                        r"(?![\w@-])"
                    ),
                    score=1.0,
                )
            ],
        )


class ReconocedorTelefono(PatternRecognizer):
    """Números chilenos móviles y fijos de nueve cifras, opcionalmente con prefijo 56."""

    def __init__(self) -> None:
        super().__init__(
            supported_entity=Categoria.TELEFONO.name,
            name="telefono_cl",
            supported_language=IDIOMA,
            patterns=[
                Pattern(
                    name="movil",
                    regex=(
                        r"(?<![\w+])"
                        r"(?:\+?56[\s-]?)?"
                        r"[2-9][\s-]?\d{3,4}[\s-]?\d{3,4}"
                        r"(?![\w-])"
                    ),
                    score=1.0,
                )
            ],
        )

    def validate_result(self, pattern_text: str) -> bool:
        digitos = "".join(c for c in pattern_text if c.isdigit())
        if digitos.startswith("56"):
            digitos = digitos[2:]
        return len(digitos) == 9 and digitos[0] in "23456789"


class ReconocedorTarjeta(PatternRecognizer):
    """Números de tarjeta de 13–19 dígitos con separadores opcionales y Luhn."""

    def __init__(self) -> None:
        super().__init__(
            supported_entity=Categoria.TARJETA.name,
            name="tarjeta_pago",
            supported_language=IDIOMA,
            patterns=[
                Pattern(
                    name="numero_tarjeta",
                    regex=(
                        r"(?<!\w)"
                        r"(?:\d[ -]?){12,18}\d"
                        r"(?!\w)"
                    ),
                    score=1.0,
                )
            ],
        )

    def validate_result(self, pattern_text: str) -> bool:
        digitos = "".join(c for c in pattern_text if c.isdigit())
        if not 13 <= len(digitos) <= 19:
            return False
        suma = 0
        doble = False
        for digito in reversed(digitos):
            valor = int(digito)
            if doble:
                valor *= 2
                if valor > 9:
                    valor -= 9
            suma += valor
            doble = not doble
        return suma % 10 == 0


class ReconocedorPatente(PatternRecognizer):
    """Formatos chilenos usuales de patente, confirmados por contexto vehicular."""

    def __init__(self) -> None:
        super().__init__(
            supported_entity=Categoria.PATENTE.name,
            name="patente_chilena",
            supported_language=IDIOMA,
            patterns=[Pattern(
                name="patente",
                regex=r"(?i)(?<![A-Z0-9])(?:[A-Z]{4}[ -]?\d{2}|[A-Z]{2}[ -]?\d{3,4})(?![A-Z0-9])",
                score=_PUNTAJE_PATRON,
            )],
            context=["patente", "placa patente", "vehículo", "automóvil", "auto", "motocicleta"],
        )


class ReconocedorGeolocalizacion(PatternRecognizer):
    """Pares decimales latitud/longitud, validados por rango y contexto GPS."""

    subcategoria = "coordenadas"
    _COORDENADAS = re.compile(r"^\s*([+-]?\d{1,2}(?:\.\d+)?)\s*[,; ]\s*([+-]?\d{1,3}(?:\.\d+)?)\s*$")

    def __init__(self) -> None:
        super().__init__(
            supported_entity=Categoria.GEOLOCALIZACION.name,
            name="coordenadas_geograficas",
            supported_language=IDIOMA,
            patterns=[Pattern(
                name="coordenadas_decimales",
                regex=(
                    r"(?<![\w.])"
                    r"[+-]?\d{1,2}(?:\.\d+)?\s*[,; ]\s*[+-]?\d{1,3}(?:\.\d+)?"
                    r"(?![\w.])"
                ),
                score=_PUNTAJE_PATRON,
            )],
            context=["coordenadas", "latitud", "longitud", "gps", "ubicación", "ubicacion"],
        )

    def validate_result(self, pattern_text: str) -> bool:
        match = self._COORDENADAS.fullmatch(pattern_text)
        if not match:
            return False
        latitud, longitud = map(float, match.groups())
        return -90 <= latitud <= 90 and -180 <= longitud <= 180


def reconocedores_por_omision() -> list[PatternRecognizer]:
    return [
        ReconocedorRun(), ReconocedorCorreo(), ReconocedorTelefono(), ReconocedorTarjeta(),
        ReconocedorPatente(), ReconocedorGeolocalizacion(),
    ]


class EtapaRegex:
    """Detecta entidades REGEX preservando evidencias de categorías ambiguas.

    Dos categorías pueden coincidir sobre la misma cadena, como un teléfono
    cuyo número satisface el DV de un RUN. Conservamos ambas evidencias, y
    dejamos a la política combinar tramos antes de seudonimizar.
    """

    def __init__(self, reconocedores: Sequence[PatternRecognizer] | None = None) -> None:
        self.reconocedores = (
            list(reconocedores) if reconocedores is not None else reconocedores_por_omision()
        )
        if not self.reconocedores:
            raise ValueError("EtapaRegex requiere reconocedores")

    def analizar(self, texto: str) -> list[Hallazgo]:
        if not isinstance(texto, str):
            raise TypeError("se esperaba texto")
        hallazgos: list[Hallazgo] = []
        for reconocedor in self.reconocedores:
            resultados = reconocedor.analyze(texto, reconocedor.supported_entities)
            for resultado in resultados:
                hallazgos.append(self._a_hallazgo(texto, reconocedor, resultado))
        return self._deduplicar(hallazgos)

    @staticmethod
    def _a_hallazgo(
        texto: str, reconocedor: PatternRecognizer, resultado: RecognizerResult
    ) -> Hallazgo:
        # Un resultado anómalo es un fallo, no una autorización silenciosa.
        if not (isinstance(resultado.start, int) and isinstance(resultado.end, int)
                and 0 <= resultado.start < resultado.end <= len(texto)):
            raise ValueError("tramo de detector fuera de límites")
        categoria = Categoria[resultado.entity_type]
        return Hallazgo(
            categoria=categoria,
            valor=texto[resultado.start:resultado.end],
            inicio=resultado.start,
            fin=resultado.end,
            reconocedor=reconocedor.name,
            procedencia=Procedencia.REGEX,
            confianza=resultado.score,
            verificado=isinstance(reconocedor, ReconocedorRun),
            subcategoria=getattr(reconocedor, "subcategoria", None),
        )

    @staticmethod
    def _deduplicar(hallazgos: list[Hallazgo]) -> list[Hallazgo]:
        # El mismo segmento puede ser tanto RUN como TELÉFONO; no eliminarlo.
        unicos: dict[tuple[Categoria, int, int], Hallazgo] = {}
        for h in hallazgos:
            clave = (h.categoria, h.inicio, h.fin)
            previo = unicos.get(clave)
            if previo is None or (h.verificado, h.confianza) > (previo.verificado, previo.confianza):
                unicos[clave] = h
        return sorted(unicos.values(), key=lambda h: (h.inicio, h.fin, h.categoria.value))
