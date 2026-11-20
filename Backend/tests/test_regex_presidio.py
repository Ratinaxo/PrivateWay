"""Integración REAL con Presidio: se omite si la dependencia falta.

Al ejecutarse dentro de la imagen de backend debe pasar sin descargas ni red.
"""
from __future__ import annotations

import pytest

pytest.importorskip("presidio_analyzer")

from backend.deteccion.hallazgo import Categoria
from backend.deteccion.regex import EtapaRegex, ReconocedorRun


@pytest.fixture(scope="module")
def etapa():
    return EtapaRegex()


@pytest.mark.parametrize("texto,valor", [
    ("RUN: 12.345.678-5.", "12.345.678-5"),
    ("RUN sin separadores: 123456785.", "123456785"),
    ("RUN con espacios: 12.345.678 - 5.", "12.345.678 - 5"),
    ("RUN con K: 8.765.432-K.", "8.765.432-K"),
    ("RUN de 7 dígitos: 1000000-9.", "1000000-9"),
])
def test_run_valido(etapa, texto, valor):
    encontrados = etapa.analizar(texto)
    assert any(h.categoria is Categoria.RUN and h.valor == valor and h.verificado for h in encontrados)


@pytest.mark.parametrize("texto", [
    "RUN con DV incorrecto: 12.345.678-9.",
    "Código embebido X12.345.678-5Y.",
    "RUN pegado a letras abc123456785xyz.",
])
def test_run_invalido_no_es_aceptado(etapa, texto):
    assert not any(h.categoria is Categoria.RUN for h in etapa.analizar(texto))


@pytest.mark.parametrize("texto,valor,categoria", [
    ("Contacto ana.perez+ventas@empresa.cl", "ana.perez+ventas@empresa.cl", Categoria.CORREO),
    ("Escribe a USUARIO@EJEMPLO.COM", "USUARIO@EJEMPLO.COM", Categoria.CORREO),
    ("Correo entre signos <persona@ejemplo.cl>", "persona@ejemplo.cl", Categoria.CORREO),
    ("Móvil +56 9 1234 5678", "+56 9 1234 5678", Categoria.TELEFONO),
    ("Móvil 912345678", "912345678", Categoria.TELEFONO),
    ("Móvil +56912345678", "+56912345678", Categoria.TELEFONO),
    ("Móvil 56-9-1234-5678", "56-9-1234-5678", Categoria.TELEFONO),
])
def test_otros_patrones_y_posiciones(etapa, texto, valor, categoria):
    encontrados = etapa.analizar(texto)
    assert any(h.categoria is categoria and h.valor == valor for h in encontrados)
    assert all(texto[h.inicio:h.fin] == h.valor for h in encontrados)


def test_run_y_telefono_ambiguos_se_conservan_como_evidencias(etapa):
    encontrados = etapa.analizar("Identificador ambiguo 987654325")
    categorias = {h.categoria for h in encontrados if h.valor == "987654325"}
    assert {Categoria.RUN, Categoria.TELEFONO} <= categorias


def test_detector_no_requiere_analyzer_engine_ni_spacy_model(etapa):
    assert len(etapa.reconocedores) == 3
    assert any(isinstance(x, ReconocedorRun) for x in etapa.reconocedores)
