"""Pruebas offline: catálogo, liveness y procesamiento REGEX del gateway."""
from fastapi.testclient import TestClient

from backend.gateway.api import create_app
from backend.gateway.config import Configuracion, RutaModelo
from backend.gateway.providers import ProveedorSimulado
from backend.gateway.regex_pipeline import PipelineRegex


class ProveedorEspia(ProveedorSimulado):
    llamadas = 0

    async def completar(self, modelo, mensajes, solicitud):
        self.llamadas += 1
        return await super().completar(modelo, mensajes, solicitud)


class DetectorSinHallazgos:
    def analizar(self, texto):
        return []


class AuditoriaEnMemoria:
    listo = True

    async def registrar(self, datos):
        pass


def _client():
    config = Configuracion(
        tokens_cliente=("token-de-prueba-para-el-gateway-123456789",),
        rutas={"pw-simulado": RutaModelo("simulado", "modelo-demo")},
    )
    espia = ProveedorEspia()
    return TestClient(create_app(config=config, pipeline=PipelineRegex(detector=DetectorSinHallazgos()), auditoria=AuditoriaEnMemoria(), adaptadores={"simulado": espia})), espia


def test_liveness_y_readiness():
    client, _ = _client()
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 200


def test_catalogo_exige_token():
    client, _ = _client()
    assert client.get("/api/v1/models").status_code == 401
    respuesta = client.get("/api/v1/models", headers={"Authorization": "Bearer token-de-prueba-para-el-gateway-123456789"})
    assert respuesta.status_code == 200
    assert respuesta.json() == {"providers": [{"id": "simulado", "label": "Simulado", "models": [{"id": "pw-simulado", "label": "pw-simulado"}]}]}


def test_prompt_sin_coincidencias_llega_al_adaptador():
    client, espia = _client()
    respuesta = client.post(
        "/api/v1/secure-chat",
        headers={"Authorization": "Bearer token-de-prueba-para-el-gateway-123456789"},
        json={"model": "pw-simulado", "messages": [{"role": "user", "content": "PRUEBA SINTETICA"}], "stream": False},
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["decision"]["accion"] == "permitir"
    assert espia.llamadas == 1
