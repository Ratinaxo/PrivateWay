import asyncio
from unittest.mock import AsyncMock
import pytest
from privateway_model import rag
from backend.gateway.contracts import Mensaje


def test_identidad_fragmento_no_colisiona_con_unidad_legal(monkeypatch):
    class Conexion:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, sql, parametros):
            return [("art2_f_0", "texto legal", {"id":"art2_f", "localizador":"2 f"}, 0.1)]
    monkeypatch.setattr(rag, "conexion", Conexion)
    emb = type("Emb", (), {})()
    emb.segmentos = AsyncMock(return_value=["consulta"])
    emb.codificar = AsyncMock(return_value=[[1.0]+[0.0]*1023])
    emb.llamar = AsyncMock(return_value={"ready":True,"revision":"test"})
    r = rag.RecuperadorPostgres(emb)
    r.versiones = AsyncMock(return_value={"indice":"v1","embeddings":{"ready":True,"revision":"test"}})
    fs = asyncio.run(r.buscar([Mensaje(role="user",content="hola")], []))
    assert fs[0]["id"] == "art2_f_0"
    assert fs[0]["indice"] == "v1"
    emb.segmentos.assert_awaited_once_with("hola")


def test_codificar_en_lotes_conserva_orden_y_concatena_respuestas():
    class Embeddings:
        def __init__(self):
            self.llamadas = []

        async def codificar(self, textos, tipo):
            self.llamadas.append((list(textos), tipo))
            return [f"vector:{texto}" for texto in textos]

    emb = Embeddings()
    textos = [f"pasaje-{i}" for i in range(70)]
    vectores = asyncio.run(rag.codificar_en_lotes(emb, textos, "passage"))

    assert [len(lote) for lote, _ in emb.llamadas] == [32, 32, 6]
    assert all(tipo == "passage" for _, tipo in emb.llamadas)
    assert vectores == [f"vector:{texto}" for texto in textos]


def test_codificar_en_lotes_rechaza_respuesta_incompleta():
    class Embeddings:
        async def codificar(self, textos, tipo):
            return ["vector-incompleto"]

    with pytest.raises(ValueError, match="embeddings incompletos"):
        asyncio.run(rag.codificar_en_lotes(Embeddings(), ["pasaje-1", "pasaje-2"], "passage"))
