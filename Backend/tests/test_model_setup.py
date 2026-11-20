import importlib.util
from pathlib import Path

path=Path(__file__).resolve().parents[2]/"Model/scripts/setup_model_env.py"
spec=importlib.util.spec_from_file_location("setup_model_env",path)
setup=importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


def test_conserva_tokens_existentes_y_agrega_configuracion_modelo(tmp_path):
    p=tmp_path/".env.model"
    p.write_text("PRIVATEWAY_SLM_TOKEN=token-existente\n")
    setup.configurar(tmp_path)
    anterior = dict(line.split("=", 1) for line in p.read_text().splitlines())
    assert anterior["PRIVATEWAY_SLM_TOKEN"] == "token-existente"
    assert anterior["PRIVATEWAY_EMBEDDINGS_TOKEN"]
    assert anterior["PRIVATEWAY_SLM_MODEL_DIR"] == "/models/qwen"
    assert p.stat().st_mode & 0o777 == 0o600
