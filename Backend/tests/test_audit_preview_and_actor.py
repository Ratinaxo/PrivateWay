"""Identidad OIDC, previsualización cifrada y lectura sólo con token admin."""
from __future__ import annotations

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from backend.gateway.api import create_app
from backend.gateway.audit import AuditoriaArchivo
from backend.gateway.config import Configuracion, RutaModelo
from backend.gateway.providers import ProveedorSimulado
from backend.gateway.regex_pipeline import PipelineRegex
from backend.gateway.conversations import validar_conversacion

ADMIN_TOKEN = "token-auditoria-12345678901"
CHAT_TOKEN = "token-gateway-12345678901"
USER_ID = "d8fc4477-f770-4808-a25d-237ff20e3f7e"


class DetectorNulo:
    def analizar(self, texto):
        return []


def test_previsualizacion_cifrada_y_usuario(tmp_path, monkeypatch):
    clave = Fernet.generate_key().decode()
    monkeypatch.setenv("GATEWAY_AUDIT_READ_TOKEN", ADMIN_TOKEN)
    monkeypatch.setenv("GATEWAY_AUDIT_CONTENT_KEY", clave)
    monkeypatch.setenv("GATEWAY_AUDIT_CONTENT_DIR", str(tmp_path / "previews"))
    auditoria = AuditoriaArchivo(tmp_path / "events.jsonl")
    cfg = Configuracion(tokens_cliente=(CHAT_TOKEN,), rutas={"pw-simulado": RutaModelo("simulado", "modelo-falso")})
    app = create_app(config=cfg, pipeline=PipelineRegex(detector=DetectorNulo()), auditoria=auditoria,
                     adaptadores={"simulado": ProveedorSimulado()})
    client = TestClient(app)
    original = "PROMPT SENSIBLE SINTETICO 1234567890"
    enviado = client.post("/api/v1/secure-chat", headers={
        "Authorization": f"Bearer {CHAT_TOKEN}",
        "X-PrivateWay-User-Id": USER_ID,
        "X-PrivateWay-User-Name": "Jos%C3%A9%20A.",
    }, json={"model": "pw-simulado", "messages": [{"role": "user", "content": original}]})
    assert enviado.status_code == 200
    evento = enviado.json()["decision"]["evento"]
    lista = client.get("/api/v1/audit/events", headers={"Authorization": f"Bearer {ADMIN_TOKEN}"})
    assert lista.status_code == 200
    assert lista.json()["registros"][0]["usuario"] == "José A."
    assert lista.json()["registros"][0]["usuario_id"] == USER_ID
    assert lista.json()["registros"][0]["vista_disponible"] == "si"
    assert original not in (tmp_path / "events.jsonl").read_text()
    assert original.encode() not in (tmp_path / "previews" / f"{evento}.enc").read_bytes()

    endpoint = f"/api/v1/audit/events/{evento}/preview"
    assert client.get(endpoint).status_code == 401
    assert client.get(endpoint, headers={"Authorization": f"Bearer {CHAT_TOKEN}"}).status_code == 401
    vista = client.get(endpoint, headers={"Authorization": f"Bearer {ADMIN_TOKEN}",
        "X-PrivateWay-Auditor-Id": USER_ID, "X-PrivateWay-Auditor-Name": "Admin"})
    assert vista.status_code == 200
    assert vista.headers["cache-control"].startswith("no-store")
    assert vista.json()["mensajes"] == [{"indice": 1, "role": "user", "antes": original, "despues": original}]
    assert vista.json()["respuesta"]["despues"].startswith("Respuesta simulada:")
    consulta = client.get("/api/v1/audit/events", headers={"Authorization": f"Bearer {ADMIN_TOKEN}"}).json()
    assert consulta["total"] == 3
    assert consulta["registros"][0]["fase"] == "consulta_previsualizacion"
    assert consulta["registros"][0]["usuario_id"] == USER_ID
    assert consulta["registros"][0]["evento_consultado"] == evento


def test_historial_validacion_estricta():
    chat_id = "64ea584e-40ed-42e4-bb7f-27d5b7ec2323"
    msg_id = "e37a7f5b-1d66-469b-99e3-289a5c22ac7e"
    base = {"id": chat_id, "title": "Prueba", "providerId": "simulado", "modelId": "pw-simulado",
            "createdAt": 1794300000000, "updatedAt": 1794300000001,
            "messages": [{"id": msg_id, "role": "user", "content": "123456789", "createdAt": 1794300000000}]}
    assert validar_conversacion(base, chat_id) == base
    import pytest
    with pytest.raises(ValueError):
        validar_conversacion({**base, "owner": "otro-usuario"}, chat_id)
    with pytest.raises(ValueError):
        validar_conversacion({**base, "messages": [{**base["messages"][0], "role": "root"}]}, chat_id)
    with pytest.raises(ValueError):
        validar_conversacion({**base, "messages": base["messages"] * 501}, chat_id)


def test_previsualizacion_refleja_seudonimizacion_real(tmp_path, monkeypatch):
    import re
    from backend.deteccion.hallazgo import Hallazgo, Categoria, Procedencia

    class DetectorCorreo:
        def analizar(self, texto):
            return [Hallazgo(categoria=Categoria.CORREO, valor=m.group(),
                             inicio=m.start(), fin=m.end(), reconocedor="test",
                             procedencia=Procedencia.REGEX, confianza=1.0)
                    for m in re.finditer(r"persona@ejemplo\\.cl".replace("\\\\", "\\"), texto)]

    monkeypatch.setenv("GATEWAY_AUDIT_READ_TOKEN", ADMIN_TOKEN)
    monkeypatch.setenv("GATEWAY_AUDIT_CONTENT_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("GATEWAY_AUDIT_CONTENT_DIR", str(tmp_path / "vistas"))
    auditoria = AuditoriaArchivo(tmp_path / "events.jsonl")
    cfg = Configuracion(tokens_cliente=(CHAT_TOKEN,), rutas={"pw-simulado": RutaModelo("simulado", "modelo-falso")})
    app = create_app(config=cfg, pipeline=PipelineRegex(detector=DetectorCorreo()), auditoria=auditoria,
                     adaptadores={"simulado": ProveedorSimulado()})
    client = TestClient(app)
    contenido = "Enviar a persona@ejemplo.cl"
    r = client.post("/api/v1/secure-chat", headers={"Authorization": f"Bearer {CHAT_TOKEN}",
                                                    "X-PrivateWay-User-Id": USER_ID},
        json={"model": "pw-simulado", "messages": [{"role": "user", "content": contenido}]})
    assert r.status_code == 200
    assert r.json()["decision"]["mensaje_actual_seudonimizado"] is True
    event_id = r.json()["decision"]["evento"]
    vista = client.get(f"/api/v1/audit/events/{event_id}/preview",
        headers={"Authorization": f"Bearer {ADMIN_TOKEN}"}).json()
    assert vista["mensajes"][0]["antes"] == contenido
    assert vista["mensajes"][0]["despues"] == "Enviar a [PW_CORREO_1]"
    assert contenido not in (tmp_path / "events.jsonl").read_text()
