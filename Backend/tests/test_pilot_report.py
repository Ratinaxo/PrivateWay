import importlib.util
import json
from pathlib import Path
import pytest

path = Path(__file__).resolve().parents[2]/"Model/scripts/report_pilot.py"
spec = importlib.util.spec_from_file_location("report_pilot",path)
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


def preparar(carpeta):
    for nivel,modos in [("deteccion",["regex","slm","hibrido"]),("flujo",["hibrido"])]:
        for modo in modos:
            for c in [1,5,10]:
                f = dict(nivel=nivel,modo=modo,concurrencia=c,n=1,muestras=[dict(id="caso1")],
                         versiones={"indice":"corpus1"})
                for clave in ("instrucciones_sha256","esquema_sha256","esquemas_wire_sha256",
                              "revision_modelo","contexto_tokens","dataset_sha256","protocolo"):
                    f[clave] = "version1"
                (carpeta/f"{nivel}-{modo}-dev-c{c}.json").write_text(json.dumps(f))


def test_reporte_rechaza_configuraciones_mezcladas(tmp_path):
    preparar(tmp_path)
    assert len(report.cargar_resultados(tmp_path)) == 12
    p = tmp_path/"flujo-hibrido-dev-c1.json"
    d=json.loads(p.read_text())
    d["revision_modelo"]="otro_modelo"
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError,match="revision_modelo"):
        report.cargar_resultados(tmp_path)


def test_smoke_comprueba_accion_y_codigo_de_bloqueo():
    base=dict(estado=200,esperado=200,accion_esperada="seudonimizar",accion="permitir",codigo=None)
    assert not report.smoke_correcto(base)
    assert report.smoke_correcto({**base,"accion":"seudonimizar"})
    base.update(estado=403,esperado=403,accion_esperada="bloquear",codigo="OTRO_ERROR")
    assert not report.smoke_correcto(base)
    assert report.smoke_correcto({**base,"codigo":"POLITICA_BLOQUEA"})
