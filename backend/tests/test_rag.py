import asyncio
from unittest.mock import AsyncMock
from backend.gateway import rag
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
