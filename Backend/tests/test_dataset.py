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
    assert {"art2_f", "art2_g", "art2_l", "art16bis"} <= {f["id"] for f in data["fragmentos"]}
    assert all(f["documento"] == "ley21719" and f["estado"] == "vigencia_diferida" for f in data["fragmentos"])
    assert all(len(d["sha256"]) == 64 for d in data["documentos"])
