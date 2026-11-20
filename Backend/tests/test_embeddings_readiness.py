import pytest

from Model.embeddings.readiness import revision_configurada


@pytest.mark.parametrize("revision", [None, "", "   ", "no-descargado", "pending-download"])
def test_revision_embeddings_pendiente_no_esta_lista(revision):
    assert not revision_configurada(revision)


def test_revision_embeddings_inmutable_esta_lista():
    assert revision_configurada("3d7cfbdacd47fdda877c5cd8a79fbcc4f2a574f3")
