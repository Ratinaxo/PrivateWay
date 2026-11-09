"""Etapa REGEX: patrones de identificadores estructurados.

Es la primera etapa de análisis del diagrama. Cada reconocedor es un
`PatternRecognizer` de Presidio, de modo que la etapa del SLM pueda reutilizar
el mismo registro de reconocedores más adelante.

No se usan los reconocedores de correo y URL que trae Presidio porque dependen
de `tldextract`, que descarga la lista de sufijos públicos desde internet en su
primer uso. Eso contradice el requisito de que el análisis no transmita nada
fuera del entorno local.
"""

from __future__ import annotations

from collections.abc import Sequence

from presidio_analyzer import Pattern, PatternRecognizer, RecognizerResult

from . import run
from .hallazgo import Categoria, Hallazgo, Procedencia

IDIOMA = "es"

# Puntaje que Presidio asigna a una coincidencia antes de validarla. Si
# `validate_result` la confirma, Presidio la sube a 1.0; si la rechaza, la
# descarta.
_PUNTAJE_PATRON = 0.5


class ReconocedorRun(PatternRecognizer):
    """RUN con puntos y guion, con guion solamente o sin separadores."""

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
    """Dirección de correo electrónico, sin validar el dominio en línea."""

    def __init__(self) -> None:
        super().__init__(
            supported_entity=Categoria.CORREO.name,
            name="correo",
            supported_language=IDIOMA,
            patterns=[
                Pattern(
                    name="correo",
                    regex=r"(?<![\w.])[\w.+-]+@[\w-]+(?:\.[\w-]+)+(?![\w.])",
                    score=1.0,
                )
            ],
        )


class ReconocedorTelefono(PatternRecognizer):
    """Móvil chileno: +56 seguido de 9 y ocho cifras, o el número de nueve cifras."""

    def __init__(self) -> None:
        super().__init__(
            supported_entity=Categoria.TELEFONO.name,
            name="telefono_cl",
            supported_language=IDIOMA,
            patterns=[
                Pattern(
                    name="movil",
                    regex=r"(?<![\w+])(?:\+?56[\s-]?)?9[\s-]?\d{4}[\s-]?\d{4}(?![\w-])",
                    score=1.0,
                )
            ],
        )


def reconocedores_por_omision() -> list[PatternRecognizer]:
    return [ReconocedorRun(), ReconocedorCorreo(), ReconocedorTelefono()]


class EtapaRegex:
    """Ejecuta los reconocedores y entrega hallazgos sin solapamientos."""

    def __init__(self, reconocedores: Sequence[PatternRecognizer] | None = None) -> None:
        self.reconocedores = (
            list(reconocedores) if reconocedores is not None else reconocedores_por_omision()
        )

    def analizar(self, texto: str) -> list[Hallazgo]:
        hallazgos: list[Hallazgo] = []
        for reconocedor in self.reconocedores:
            resultados = reconocedor.analyze(texto, reconocedor.supported_entities)
            hallazgos.extend(self._a_hallazgo(texto, reconocedor, r) for r in resultados)
        return self._resolver_solapamientos(hallazgos)

    @staticmethod
    def _a_hallazgo(
        texto: str, reconocedor: PatternRecognizer, resultado: RecognizerResult
    ) -> Hallazgo:
        return Hallazgo(
            categoria=Categoria[resultado.entity_type],
            valor=texto[resultado.start : resultado.end],
            inicio=resultado.start,
            fin=resultado.end,
            reconocedor=reconocedor.name,
            procedencia=Procedencia.REGEX,
            confianza=resultado.score,
            # Solo el RUN tiene una rutina aritmética; Presidio la ejecutó y
            # descartó los que no la superan.
            verificado=isinstance(reconocedor, ReconocedorRun),
        )

    @staticmethod
    def _resolver_solapamientos(hallazgos: list[Hallazgo]) -> list[Hallazgo]:
        """Ante dos hallazgos que se solapan, conserva el de mayor confianza.

        Si empatan en confianza, conserva el más largo: un RUN completo debe
        prevalecer sobre un número contenido en él.
        """
        ordenados = sorted(hallazgos, key=lambda h: (-h.confianza, -(h.fin - h.inicio), h.inicio))
        conservados: list[Hallazgo] = []
        for candidato in ordenados:
            solapa = any(
                candidato.inicio < existente.fin and existente.inicio < candidato.fin
                for existente in conservados
            )
            if not solapa:
                conservados.append(candidato)
        return sorted(conservados, key=lambda h: h.inicio)
