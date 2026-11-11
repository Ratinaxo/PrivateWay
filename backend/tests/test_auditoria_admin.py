"""Auditoría: autorización independiente, verificación de cadena y salida sin PII."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from backend.gateway.api import create_app
from backend.gateway.audit import AuditoriaArchivo
from backend.gateway.config import Configuracion, RutaModelo
from backend.gateway.regex_pipeline import PipelineRegex
from backend.gateway.providers import ProveedorSimulado


class DetectorSinHallazgos:
    def analizar(self, texto):
        return []


def escenario(tmp_path, monkeypatch):
    ruta = tmp_path / "audit.jsonl"
    monkeypatch.setenv("GATEWAY_AUDIT_READ_TOKEN", "token-de-auditoria-separado-123456")
    config = Configuracion(
        tokens_cliente=("token-normal-chat-123456789",),
        rutas={"pw-simulado": RutaModelo("simulado", "modelo-sintetico")},
    )
    app = create_app(config=config, pipeline=PipelineRegex(detector=DetectorSinHallazgos()),
                     auditoria=AuditoriaArchivo(ruta), adaptadores={"simulado": ProveedorSimulado()})
    return TestClient(app), ruta


def test_bitacora_solo_token_admin_y_muestra_metadatos(tmp_path, monkeypatch):
    client, ruta = escenario(tmp_path, monkeypatch)
    endpoint = "/api/v1/audit/events"
    assert client.get(endpoint).status_code == 401
    assert client.get(endpoint, headers={"Authorization": "Bearer token-normal-chat-123456789"}).status_code == 401
    acceso = {"Authorization": "Bearer token-de-auditoria-separado-123456"}
    assert client.get(endpoint, headers=acceso).json() == {
        "integridad": "verificada", "total": 0, "registros": []
    }
    prompt = "PRUEBA PRIVADA QUE NO PUEDE ESTAR EN LA AUDITORIA"
    envio = client.post("/api/v1/secure-chat", headers={"Authorization": "Bearer token-normal-chat-123456789"},
        json={"model": "pw-simulado", "messages": [{"role": "user", "content": prompt}]})
    assert envio.status_code == 200
    auditoria = client.get(endpoint, headers=acceso)
    assert auditoria.status_code == 200
    assert auditoria.headers.get("cache-control") == "no-store"
    datos = auditoria.json()
    assert datos["integridad"] == "verificada"
    assert datos["total"] == 2
    assert datos["registros"][0]["fase"] == "completada"
    assert datos["registros"][0]["fecha_utc"].endswith("+00:00")
    assert prompt not in auditoria.text
    assert prompt not in ruta.read_text()
    assert client.get(endpoint + "?limit=1", headers=acceso).json()["registros"].__len__() == 1


def test_cadena_alterada_no_se_muestra_parcialmente(tmp_path, monkeypatch):
    client, ruta = escenario(tmp_path, monkeypatch)
    acceso = {"Authorization": "Bearer token-de-auditoria-separado-123456"}
    r = client.post("/api/v1/secure-chat", headers={"Authorization": "Bearer token-normal-chat-123456789"},
        json={"model": "pw-simulado", "messages": [{"role": "user", "content": "dato de prueba"}]})
    assert r.status_code == 200
    contenido = ruta.read_text()
    assert '"accion": "permitir"' in contenido
    ruta.write_text(contenido.replace('"accion": "permitir"', '"accion": "bloquear"', 1))
    consulta = client.get("/api/v1/audit/events", headers=acceso)
    assert consulta.status_code == 503
    assert consulta.json()["error"]["code"] == "AUDITORIA_NO_DISPONIBLE"
    assert "bloquear" not in consulta.text
