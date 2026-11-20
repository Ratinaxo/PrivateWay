import importlib.util
from pathlib import Path

import pytest

_RUTA_READINESS = (Path(__file__).resolve().parents[2] /
                   "Model" / "embeddings" / "readiness.py")
_SPEC = importlib.util.spec_from_file_location("privateway_embeddings_readiness", _RUTA_READINESS)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError("No se pudo cargar la validación de readiness de embeddings")
_MODULO = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULO)
revision_configurada = _MODULO.revision_configurada


@pytest.mark.parametrize("revision", [None, "", "   ", "no-descargado", "pending-download"])
def test_revision_embeddings_pendiente_no_esta_lista(revision):
    assert not revision_configurada(revision)


def test_revision_embeddings_inmutable_esta_lista():
    assert revision_configurada("3d7cfbdacd47fdda877c5cd8a79fbcc4f2a574f3")
