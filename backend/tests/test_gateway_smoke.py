"""Pruebas offline: catálogo, liveness y bloqueo sin pipeline."""
from fastapi.testclient import TestClient

from backend.gateway.api import create_app
from backend.gateway.config import Configuracion, RutaModelo
from backend.gateway.providers import ProveedorSimulado


class ProveedorEspia(ProveedorSimulado):
    llamadas = 0

    async def completar(self, modelo, mensajes, solicitud):
        self.llamadas += 1
        return await super().completar(modelo, mensajes, solicitud)


def _client():
    config = Configuracion(
        tokens_cliente=("token-de-prueba-para-el-gateway-123456789",),
        rutas={"pw-simulado": RutaModelo("simulado", "modelo-demo")},
    )
    espia = ProveedorEspia()
    return TestClient(create_app(config=config, adaptadores={"simulado": espia})), espia


def test_liveness_no_es_readiness():
    client, _ = _client()
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 503


def test_catalogo_exige_token():
    client, _ = _client()
    assert client.get("/api/v1/models").status_code == 401
    respuesta = client.get("/api/v1/models", headers={"Authorization": "Bearer token-de-prueba-para-el-gateway-123456789"})
    assert respuesta.status_code == 200
    assert respuesta.json() == {"providers": [{"id": "simulado", "label": "Simulado", "models": [{"id": "pw-simulado", "label": "pw-simulado"}]}]}


def test_no_sale_prompt_sin_proteccion():
    client, espia = _client()
    respuesta = client.post(
        "/api/v1/secure-chat",
        headers={"Authorization": "Bearer token-de-prueba-para-el-gateway-123456789"},
        json={"model": "pw-simulado", "messages": [{"role": "user", "content": "PRUEBA SINTETICA"}], "stream": False},
    )
    assert respuesta.status_code == 503
    assert respuesta.json()["error"]["code"] == "ANALISIS_NO_DISPONIBLE"
    assert espia.llamadas == 0
