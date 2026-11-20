import json
from pathlib import Path
from privateway_model.evaluate import metricas
from privateway_model.metrics import (coincide_exposicion, macro_por_categoria,
                                     conteos_parciales, exposicion_solicitud)
from privateway_model.rag import vector
import pytest

ROOT = Path(__file__).resolve().parents[2] / "Model"


def test_fixture_split_y_offsets():
    familias = []
    for split in ("desarrollo", "validacion"):
        casos = json.loads((ROOT / "datasets/v1" / f"{split}.json").read_text(encoding="utf-8"))
        assert len(casos) == 60
        familias.append({c["familia"] for c in casos})
        for c in casos:
            for h in c["hallazgos"]:
                texto = c["mensajes"][h["mensaje"]]["content"]
                assert 0 <= h["inicio"] < h["fin"] <= len(texto)
    assert not familias[0] & familias[1]
    assert len(json.loads((ROOT / "datasets/v1/recuperacion.json").read_text(encoding="utf-8"))) == 24


def test_metricas_y_vector():
    assert metricas(1,0,1)["f2"] == pytest.approx(5/9)
    assert metricas(1,0,1)["f1"] == pytest.approx(2/3)
    assert metricas(0,0,0)["recall"] is None


def test_exposicion_detecta_valor_parcial_y_exige_fragmento_en_valor_corto():
    assert coincide_exposicion("RUN 12345678-9", "Se filtró 12345")
    assert not coincide_exposicion("Ana", "La respuesta menciona Anabel")
    assert coincide_exposicion("Ana", "La respuesta contiene Ana.")


def test_macro_omite_metricas_no_aplicables_por_separado():
    macro = macro_por_categoria({
        "persona": metricas(1, 0, 1),
        "limpia": metricas(0, 0, 0),
    })
    assert macro["precision"] == 1.0
    assert macro["recall"] == 0.5
    assert macro["categorias_f2"] == 1


def test_metricas_parciales_emparejan_solapamiento_sin_reutilizar_referencia():
    verdad = {(0, 4, 14, "persona"), (0, 20, 28, "salud")}
    pred = {(0, 0, 14, "persona"), (0, 21, 28, "salud"), (0, 30, 34, "run")}
    assert conteos_parciales(verdad, pred) == (2, 1, 0)


def test_exposicion_separa_coincidencia_completa_y_parcial():
    from backend.gateway.contracts import Mensaje
    original = [Mensaje(role="user", content="RUN 12345678-9 y Ana Torres")]
    enviado = [Mensaje(role="user", content="RUN 12345 y [PW_PERSONA_1]")]
    metricas_exp = exposicion_solicitud(original, enviado,
                                        [(0, 4, 14, "run"), (0, 17, 27, "persona")])
    assert metricas_exp == {"expuestas": 1, "exactas": 0, "parciales": 1,
                            "referencias": 2, "tasa": 0.5}
    with pytest.raises(ValueError):
        vector([float("nan")]*1024)
    with pytest.raises(ValueError):
        vector([0.0]*1024)


def test_corpus_procedencia_y_vigencia():
    data = json.loads((ROOT / "corpus/manifest.json").read_text(encoding="utf-8"))
    documentos = {d["id"]: d for d in data["documentos"]}
    assert set(documentos) == {"ley19628", "ley21719"}
    assert documentos["ley19628"]["estado"] == "vigente_hasta"
    assert documentos["ley19628"]["vigencia_hasta"] == "2026-11-30"
    assert documentos["ley21719"]["estado"] == "vigencia_diferida"
    assert documentos["ley21719"]["vigencia_desde"] == "2026-12-01"
    assert all(len(d["sha256"]) == 64 for d in data["documentos"])


def test_corpus_disposiciones_atomicas_de_ley21719():
    data = json.loads((ROOT / "corpus/manifest.json").read_text(encoding="utf-8"))
    por_id = {f["id"]: f for f in data["fragmentos"]}
    esperados = {
        "art2_f": (
            "Ley 19.628 art. 2 f), sustituido por Ley 21.719 art. primero numeral 5 uno",
            "Dato personal: cualquier información vinculada",
        ),
        "art2_g": (
            "Ley 19.628 art. 2 g), sustituido por Ley 21.719 art. primero numeral 5 uno",
            "Datos personales sensibles: tendrán esta condición",
        ),
        "art2_l": (
            "Ley 19.628 art. 2 l), sustituido por Ley 21.719 art. primero numeral 5 tres",
            "Seudonimización: tratamiento de datos personales",
        ),
        "art3_c": (
            "Ley 19.628 art. 3 c), sustituido por Ley 21.719 art. primero numeral 6",
            "Principio de proporcionalidad. Los datos personales que se traten",
        ),
        "art3_f": (
            "Ley 19.628 art. 3 f), sustituido por Ley 21.719 art. primero numeral 6",
            "Principio de seguridad. En el tratamiento de los datos personales",
        ),
        "art16bis": (
            "Ley 19.628 art. 16 bis, incorporado por Ley 21.719 art. primero numeral 8",
            "Artículo 16 bis.- Datos personales sensibles relativos a la salud",
        ),
    }
    assert set(esperados) <= set(por_id)
    for fragmento_id, (localizador, frase) in esperados.items():
        fragmento = por_id[fragmento_id]
        assert fragmento["documento"] == "ley21719"
        assert fragmento["archivo"] == "Ley-21719.md"
        assert fragmento["localizador"] == localizador
        assert fragmento["version"] == "2026-02-05"
        assert fragmento["vigencia_desde"] == "2026-12-01"
        assert fragmento["estado"] == "vigencia_diferida"
        assert fragmento["etapa_normativa"] == "reforma_con_vigencia_diferida"
        assert frase in fragmento["texto"]
        # Las cláusulas canónicas aparecen una vez en la capa de reforma.
        assert sum(frase in f["texto"] for f in data["fragmentos"]
                   if f["documento"] == "ley21719") == 1
