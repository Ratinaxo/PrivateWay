"""Pruebas offline de ida y vuelta del gateway. No usan Internet ni datos reales."""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.gateway.api import create_app
from backend.gateway.config import Configuracion, RutaModelo
from backend.gateway.contracts import Accion, Mensaje, RespuestaProveedor
from backend.gateway.pipeline import DecisionValidada, AnalisisNoDisponible
from backend.gateway.providers import ProveedorNoDisponible

TOKEN = "token-ficticio-para-pruebas-del-laboratorio-123"
ENCABEZADOS = {"Authorization": "Bearer " + TOKEN}


class AuditoriaEspia:
    listo = True

    def __init__(self):
        self.eventos = []

    async def registrar(self, datos):
        self.eventos.append(datos)


class AdaptadorEspia:
    def __init__(self):
        self.llamadas = []
        self.error = None

    async def completar(self, modelo, mensajes, solicitud):
        self.llamadas.append((modelo, mensajes, solicitud))
        if self.error:
            raise self.error
        return RespuestaProveedor(content="LISTO", finish_reason="stop")


class PipelineDePrueba:
    listo = True

    def __init__(self, accion=Accion.PERMITIR):
        self.accion = accion
        self.fallar = False
        self.fallar_respuesta = False
        self.analizados = []
        self.procesados = []

    async def analizar(self, solicitud, contexto):
        if self.fallar:
            raise AnalisisNoDisponible("motor no disponible")
        self.analizados.append(solicitud)
        if self.accion == Accion.BLOQUEAR:
            return DecisionValidada(accion=Accion.BLOQUEAR, codigo_motivo="DATOS_SENSIBLES", validacion_completa=True)
        mensajes = solicitud.messages
        if self.accion == Accion.SEUDONIMIZAR:
            mensajes = [Mensaje(role=m.role, content=m.content.replace("PERSONA_FICTICIA", "[PERSONA]")) for m in mensajes]
        return DecisionValidada(accion=self.accion, codigo_motivo="PRUEBA_SINTETICA", mensajes_salida=mensajes,
                                validacion_completa=True, cobertura_verificada=self.accion == Accion.SEUDONIMIZAR)

    async def procesar_respuesta(self, solicitud, decision, respuesta, contexto):
        if self.fallar_respuesta:
            raise AnalisisNoDisponible("salida no verificada")
        self.procesados.append(respuesta)
        return respuesta


def escenario(accion=Accion.PERMITIR):
    config = Configuracion(tokens_cliente=(TOKEN,), rutas={"pw-test": RutaModelo("prueba", "model-test")})
    motor, adaptador, auditoria = PipelineDePrueba(accion), AdaptadorEspia(), AuditoriaEspia()
    client = TestClient(create_app(config=config, pipeline=motor, adaptadores={"prueba": adaptador}, auditoria=auditoria))
    return client, motor, adaptador, auditoria


def envio(client, texto="PRUEBA SINTETICA", autorizacion=ENCABEZADOS):
    return client.post("/api/v1/secure-chat", headers=autorizacion,
                       json={"model": "pw-test", "messages": [{"role": "user", "content": texto}], "stream": False})


def test_ida_y_vuelta_validada_y_auditada():
    client, motor, adaptador, auditoria = escenario()
    assert client.get("/ready").status_code == 200
    result = envio(client)
    assert result.status_code == 200
    body = result.json()
    assert body["respuesta"]["choices"][0]["message"]["content"] == "LISTO"
    assert body["decision"]["accion"] == "permitir"
    assert len(motor.analizados) == len(motor.procesados) == len(adaptador.llamadas) == 1
    assert adaptador.llamadas[0][0] == "model-test"
    assert adaptador.llamadas[0][1][0].content == "PRUEBA SINTETICA"
    assert [e["transmision"] for e in auditoria.eventos] == ["no_iniciada", "respuesta_recibida"]
    assert "PRUEBA SINTETICA" not in repr(auditoria.eventos)


def test_seudonimizacion_antes_de_salir_y_respuesta():
    client, _, adaptador, auditoria = escenario(Accion.SEUDONIMIZAR)
    result = envio(client, "Hola PERSONA_FICTICIA")
    assert result.status_code == 200
    assert result.json()["decision"]["accion"] == "seudonimizar"
    assert adaptador.llamadas[0][1][0].content == "Hola [PERSONA]"
    assert "PERSONA_FICTICIA" not in repr(auditoria.eventos)


def test_bloqueo_no_invoca_proveedor():
    client, motor, adaptador, auditoria = escenario(Accion.BLOQUEAR)
    result = envio(client)
    assert result.status_code == 403
    assert result.json()["error"]["code"] == "POLITICA_BLOQUEA"
    assert not adaptador.llamadas and not motor.procesados
    assert auditoria.eventos[-1]["transmision"] == "no_realizada"


def test_detector_fallido_no_invoca_proveedor():
    client, motor, adaptador, auditoria = escenario()
    motor.fallar = True
    result = envio(client)
    assert result.status_code == 503
    assert result.json()["error"]["code"] == "ANALISIS_NO_DISPONIBLE"
    assert not adaptador.llamadas and not auditoria.eventos


def test_auth_y_modelo_no_autorizados_no_invocan_proveedor():
    client, motor, adaptador, _ = escenario()
    assert envio(client, autorizacion={}).status_code == 401
    r = client.post("/api/v1/secure-chat", headers=ENCABEZADOS,
                    json={"model": "pw-no-permitido", "messages": [{"role": "user", "content": "PRUEBA"}]})
    assert r.status_code == 404
    assert not adaptador.llamadas and not motor.analizados


def test_error_proveedor_se_oculta_y_no_se_reintenta():
    client, motor, adaptador, auditoria = escenario()
    adaptador.error = ProveedorNoDisponible("TIMEOUT_PROVEEDOR")
    result = envio(client)
    assert result.status_code == 502
    assert result.json()["error"]["code"] == "PROVEEDOR_NO_DISPONIBLE"
    assert len(adaptador.llamadas) == 1
    assert not motor.procesados
    assert auditoria.eventos[-1]["transmision"] == "desconocida"


def test_posprocesamiento_fallido_no_envia_respuesta_al_cliente():
    client, motor, adaptador, auditoria = escenario()
    motor.fallar_respuesta = True
    result = envio(client)
    assert result.status_code == 503
    assert result.json()["error"]["code"] == "FALLO_POSPROCESAMIENTO"
    assert len(adaptador.llamadas) == 1
    assert "LISTO" not in result.text
    assert auditoria.eventos[-1]["transmision"] == "respuesta_recibida_posprocesamiento_fallido"


def test_ruta_compatible_usa_el_mismo_pipeline_que_el_gateway():
    client, motor, adaptador, auditoria = escenario()
    result = client.post("/v1/chat/completions", headers=ENCABEZADOS,
                         json={"model": "pw-test", "messages": [{"role": "user", "content": "PRUEBA SINTETICA"}]})
    assert result.status_code == 200
    assert result.json()["choices"][0]["message"]["content"] == "LISTO"
    assert len(adaptador.llamadas) == 1
    assert len(motor.analizados) == 1
