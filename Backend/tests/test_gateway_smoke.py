"""Pruebas offline: catálogo, liveness y procesamiento REGEX del gateway."""
import asyncio
import httpx
from fastapi.testclient import TestClient

from backend.gateway.api import create_app
from backend.gateway.config import Configuracion, RutaModelo
from backend.gateway.contracts import Accion
from backend.gateway.pipeline import AnalisisNoDisponible, DecisionValidada
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

    def __init__(self):
        self.registros = []

    async def registrar(self, datos):
        self.registros.append(dict(datos))


def _client(*, pipeline=None, auditoria=None):
    config = Configuracion(
        tokens_cliente=("token-de-prueba-para-el-gateway-123456789",),
        rutas={"pw-simulado": RutaModelo("simulado", "modelo-demo")},
    )
    espia = ProveedorEspia()
    bitacora = auditoria or AuditoriaEnMemoria()
    app = create_app(config=config, pipeline=pipeline or PipelineRegex(detector=DetectorSinHallazgos()),
                     auditoria=bitacora, adaptadores={"simulado": espia})
    return TestClient(app), espia, bitacora


def _chat(client):
    async def enviar():
        transporte = httpx.ASGITransport(app=client.app)
        async with httpx.AsyncClient(transport=transporte, base_url="http://test") as cliente:
            return await cliente.post(
                "/api/v1/secure-chat",
                headers={"Authorization": "Bearer token-de-prueba-para-el-gateway-123456789"},
                json={"model": "pw-simulado", "messages": [{"role": "user", "content": "PROMPT SINTETICO CONFIDENCIAL"}]},
            )
    return asyncio.run(enviar())


def test_liveness_y_readiness():
    client, _, _ = _client()
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 200


def test_catalogo_exige_token():
    client, _, _ = _client()
    assert client.get("/api/v1/models").status_code == 401
    respuesta = client.get("/api/v1/models", headers={"Authorization": "Bearer token-de-prueba-para-el-gateway-123456789"})
    assert respuesta.status_code == 200
    assert respuesta.json() == {"providers": [{"id": "simulado", "label": "Simulado", "models": [{"id": "pw-simulado", "label": "pw-simulado"}]}]}


def test_prompt_sin_coincidencias_llega_al_adaptador():
    client, espia, _ = _client()
    respuesta = _chat(client)
    assert respuesta.status_code == 200
    assert respuesta.json()["decision"]["accion"] == "permitir"
    assert espia.llamadas == 1


class PipelineConFalloInterno:
    async def analizar(self, solicitud, contexto):
        raise RuntimeError("fallo con PROMPT SINTETICO CONFIDENCIAL")


class PipelineDecision:
    def __init__(self, decision):
        self.decision = decision

    async def analizar(self, solicitud, contexto):
        return self.decision


def test_excepcion_interna_se_audita_sin_prompt_y_no_se_transmite():
    client, espia, auditoria = _client(pipeline=PipelineConFalloInterno())
    respuesta = _chat(client)
    assert respuesta.status_code == 503
    assert respuesta.json()["error"]["code"] == "FALLO_VALIDACION"
    assert "PROMPT SINTETICO CONFIDENCIAL" not in respuesta.text
    assert auditoria.registros[-1]["fase"] == "fallo_analisis"
    assert auditoria.registros[-1]["motivo"] == "FALLO_INTERNO_PIPELINE"
    assert auditoria.registros[-1]["transmision"] == "no_realizada"
    assert "PROMPT SINTETICO CONFIDENCIAL" not in str(auditoria.registros)
    assert espia.llamadas == 0


def test_codigo_de_fallo_no_permitido_no_se_guarda_en_auditoria():
    class PipelineCodigoArbitrario:
        async def analizar(self, solicitud, contexto):
            raise AnalisisNoDisponible(codigo="PROMPT_SINTETICO")

    client, espia, auditoria = _client(pipeline=PipelineCodigoArbitrario())
    respuesta = _chat(client)
    assert respuesta.status_code == 503
    assert auditoria.registros[-1]["motivo"] == "ANALISIS_NO_DISPONIBLE"
    assert "PROMPT_SINTETICO" not in str(auditoria.registros)
    assert espia.llamadas == 0


def test_decision_incompleta_se_audita_y_no_se_transmite():
    decision = DecisionValidada(accion=Accion.PERMITIR, codigo_motivo="INCOMPLETA",
                                mensajes_salida=[], validacion_completa=False)
    client, espia, auditoria = _client(pipeline=PipelineDecision(decision))
    respuesta = _chat(client)
    assert respuesta.status_code == 503
    assert respuesta.json()["error"]["code"] == "FALLO_VALIDACION"
    assert auditoria.registros[-1]["motivo"] == "DECISION_NO_VALIDADA"
    assert auditoria.registros[-1]["transmision"] == "no_realizada"
    assert espia.llamadas == 0


def test_contrato_de_decision_invalido_se_audita_y_no_se_transmite():
    client, espia, auditoria = _client(pipeline=PipelineDecision(None))
    respuesta = _chat(client)
    assert respuesta.status_code == 503
    assert respuesta.json()["error"]["code"] == "FALLO_VALIDACION"
    assert auditoria.registros[-1]["motivo"] == "DECISION_CONTRATO_INVALIDO"
    assert auditoria.registros[-1]["transmision"] == "no_realizada"
    assert espia.llamadas == 0


def test_fallo_de_auditoria_durante_error_detiene_la_transmision():
    class AuditoriaCaida(AuditoriaEnMemoria):
        async def registrar(self, datos):
            raise OSError("no persistir detalle")

    client, espia, _ = _client(pipeline=PipelineConFalloInterno(), auditoria=AuditoriaCaida())
    respuesta = _chat(client)
    assert respuesta.status_code == 503
    assert respuesta.json()["error"]["code"] == "AUDITORIA_NO_DISPONIBLE"
    assert espia.llamadas == 0
