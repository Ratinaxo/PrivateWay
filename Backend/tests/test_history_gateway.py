"""Aislamiento por usuario y acceso con token independiente (sin base de datos real)."""
from fastapi.testclient import TestClient
from backend.gateway.api import create_app
from backend.gateway.config import Configuracion, RutaModelo
from backend.gateway.providers import ProveedorSimulado
from backend.gateway.regex_pipeline import PipelineRegex

TOKEN = "history-only-token-largo-123456"
USER_A = "d8fc4477-f770-4808-a25d-237ff20e3f7e"
USER_B = "0ce58fd0-f840-4474-8f3e-251736c2db94"
CHAT_ID = "64ea584e-40ed-42e4-bb7f-27d5b7ec2323"
MSG_ID = "e37a7f5b-1d66-469b-99e3-289a5c22ac7e"


class DetectorNulo:
    def analizar(self, texto): return []


class Audit:
    listo = True
    async def registrar(self, datos): pass


class StoreFalso:
    def __init__(self): self.datos = {}
    async def listar(self, owner): return list(self.datos.get(owner, {}).values())
    async def guardar(self, owner, cid, body): self.datos.setdefault(owner, {})[cid] = body
    async def eliminar(self, owner, cid): self.datos.get(owner, {}).pop(cid, None)


def test_aislamiento_y_credenciales(tmp_path, monkeypatch):
    import backend.gateway.api as api
    store = StoreFalso()
    monkeypatch.setattr(api.ConversacionesPostgres, "desde_entorno", lambda: store)
    monkeypatch.setenv("GATEWAY_HISTORY_TOKEN", TOKEN)
    config = Configuracion(tokens_cliente=("chat-token-que-no-da-acceso",),
                           rutas={"pw-simulado": RutaModelo("simulado", "simulado")})
    client = TestClient(create_app(config=config, pipeline=PipelineRegex(detector=DetectorNulo()),
                 auditoria=Audit(), adaptadores={"simulado": ProveedorSimulado()}))
    endpoint = "/api/v1/conversations"
    assert client.get(endpoint).status_code == 401
    assert client.get(endpoint, headers={"Authorization": "Bearer chat-token-que-no-da-acceso",
                                             "X-PrivateWay-User-Id": USER_A}).status_code == 401
    assert client.get(endpoint, headers={"Authorization": f"Bearer {TOKEN}",
                                             "X-PrivateWay-User-Id": "invalido"}).status_code == 422
    data = {"id": CHAT_ID, "title": "Prueba", "providerId": "simulado", "modelId": "pw-simulado",
            "createdAt": 1794300000000, "updatedAt": 1794300000001,
            "messages": [{"id": MSG_ID, "role": "user", "content": "SINTETICO", "createdAt": 1794300000000}]}
    headers = {"Authorization": f"Bearer {TOKEN}", "X-PrivateWay-User-Id": USER_A}
    saved = client.put(endpoint + "/" + CHAT_ID, headers=headers, json=data)
    assert saved.status_code == 200
    assert client.get(endpoint, headers=headers).json() == {"conversations": [data]}
    assert client.get(endpoint, headers={**headers, "X-PrivateWay-User-Id": USER_B}).json() == {"conversations": []}
    assert client.delete(endpoint + "/" + CHAT_ID, headers={**headers, "X-PrivateWay-User-Id": USER_B}).status_code == 200
    assert client.get(endpoint, headers=headers).json() == {"conversations": [data]}
    assert client.delete(endpoint + "/" + CHAT_ID, headers=headers).status_code == 200
    assert client.get(endpoint, headers=headers).json() == {"conversations": []}
