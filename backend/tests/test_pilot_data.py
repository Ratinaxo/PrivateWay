import json
from pathlib import Path
from backend.gateway.evaluate import metricas
from backend.gateway.rag import vector
import pytest

ROOT = Path(__file__).resolve().parents[2] / "pilot"


def test_fixture_split_y_offsets():
    familias = []
    for split in ("desarrollo", "validacion"):
        casos = json.loads((ROOT / "datasets" / f"{split}.json").read_text(encoding="utf-8"))
        assert len(casos) == 60
        familias.append({c["familia"] for c in casos})
        for c in casos:
            for h in c["hallazgos"]:
                texto = c["mensajes"][h["mensaje"]]["content"]
                assert 0 <= h["inicio"] < h["fin"] <= len(texto)
    assert not familias[0] & familias[1]
    assert len(json.loads((ROOT / "datasets/recuperacion.json").read_text(encoding="utf-8"))) == 24


def test_metricas_y_vector():
    assert metricas(1,0,1)["f2"] == pytest.approx(5/9)
    assert metricas(0,0,0)["recall"] is None
    with pytest.raises(ValueError):
        vector([float("nan")]*1024)
    with pytest.raises(ValueError):
        vector([0.0]*1024)


def test_corpus_procedencia_y_vigencia():
    data = json.loads((ROOT / "corpus/manifest.json").read_text(encoding="utf-8"))
    assert {"art2_f", "art2_g", "art2_l", "art16bis"} <= {f["id"] for f in data["fragmentos"]}
    assert all(f["documento"] == "ley21719" and f["estado"] == "vigencia_diferida" for f in data["fragmentos"])
    assert all(len(d["sha256"]) == 64 for d in data["documentos"])
