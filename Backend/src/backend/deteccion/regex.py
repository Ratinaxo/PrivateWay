"""Detección estructurada offline mediante reconocedores de patrones de Presidio.

No se crea ``AnalyzerEngine`` ni se descarga un modelo NLP: los tres
reconocedores son ``PatternRecognizer`` ejecutados localmente. Este módulo
devuelve hallazgos; el gateway orquesta su tratamiento y selecciona el
adaptador configurado.
"""
from __future__ import annotations

from collections.abc import Sequence

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
    """Móviles chilenos de nueve cifras, opcionalmente con prefijo 56."""

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
                        r"9[\s-]?\d{4}[\s-]?\d{4}"
                        r"(?![\w-])"
                    ),
                    score=1.0,
                )
            ],
        )


def reconocedores_por_omision() -> list[PatternRecognizer]:
    return [ReconocedorRun(), ReconocedorCorreo(), ReconocedorTelefono()]


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
