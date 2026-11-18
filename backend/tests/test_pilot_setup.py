import importlib.util
from pathlib import Path

path=Path(__file__).resolve().parents[2]/"scripts/setup_pilot.py"
spec=importlib.util.spec_from_file_location("setup_pilot",path)
setup=importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


def test_cambiar_modelo_no_regenera_secretos_ni_claves(tmp_path):
    p=tmp_path/".env.pilot"
    p.write_text("PRIVATEWAY_DB_PASSWORD=clave-existente\nPRIVATEWAY_AUDIT_CONTENT_KEY=cifrado-existente\nPRIVATEWAY_SLM_FOLDER=qwen\n")
    setup.configurar(tmp_path,"7b")
    anterior = dict(line.split("=", 1) for line in p.read_text().splitlines())
    assert anterior["PRIVATEWAY_DB_PASSWORD"] == "clave-existente"
    assert anterior["PRIVATEWAY_SLM_FOLDER"] == "qwen7b"
    setup.configurar(tmp_path,"3b")
    assert "PRIVATEWAY_AUDIT_CONTENT_KEY=cifrado-existente" in p.read_text()
    assert p.read_text().count("PRIVATEWAY_SLM_FOLDER=") == 1
    actual = dict(line.split("=", 1) for line in p.read_text().splitlines())
    assert actual == {**anterior, "PRIVATEWAY_SLM_FOLDER": "qwen"}
