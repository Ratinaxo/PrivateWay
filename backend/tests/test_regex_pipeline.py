"""Pruebas unitarias y de integración del pipeline REGEX, con adaptador falso."""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from backend.deteccion.hallazgo import Categoria, Hallazgo, Procedencia
from backend.gateway.api import create_app
from backend.gateway.config import Configuracion, RutaModelo
from backend.gateway.contracts import RespuestaProveedor
from backend.gateway.regex_pipeline import PipelineRegex, seudonimizar_texto

TOKEN = "token-sintetico-para-pruebas-seguras-123456"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}


class DetectorFalso:
    """Inyecta evidencia sintética; prueba el cableado sin suplantar Presidio."""

    datos = {
        "12.345.678-5": Categoria.RUN,
        "persona@ejemplo.cl": Categoria.CORREO,
        "+56 9 1234 5678": Categoria.TELEFONO,
    }

    def __init__(self):
        self.falla = False
        self.llamadas = 0

    def analizar(self, texto):
        self.llamadas += 1
        if self.falla:
            raise RuntimeError("mensaje sensible de error")
        encontrados = []
        for valor, categoria in self.datos.items():
            for coincidencia in re.finditer(re.escape(valor), texto):
                encontrados.append(Hallazgo(
                    categoria=categoria, valor=coincidencia.group(),
                    inicio=coincidencia.start(), fin=coincidencia.end(),
                    reconocedor="detector_de_prueba", procedencia=Procedencia.REGEX,
                    confianza=1.0,
                ))
        return encontrados


class AdaptadorEspia:
    def __init__(self, respuesta="Respuesta simulada sin PII"):
        self.llamadas = []
        self.respuesta = respuesta

    async def completar(self, modelo, mensajes, solicitud):
        self.llamadas.append((modelo, mensajes, solicitud))
        return RespuestaProveedor(content=self.respuesta)


class AuditoriaEspia:
    listo = True

    def __init__(self):
        self.eventos = []

    async def registrar(self, datos):
        self.eventos.append(datos)


def escenario(*, respuesta="Respuesta simulada sin PII"):
    detector = DetectorFalso()
    pipeline = PipelineRegex(detector=detector)
    proveedor = AdaptadorEspia(respuesta)
    auditoria = AuditoriaEspia()
    config = Configuracion(tokens_cliente=(TOKEN,), rutas={
        "pw-test": RutaModelo("simulado", "modelo-test"),
        "pw-externo": RutaModelo("externo", "modelo-real"),
    })
    client = TestClient(create_app(
        config=config, pipeline=pipeline, auditoria=auditoria,
        adaptadores={"simulado": proveedor, "externo": proveedor},
    ))
    return client, detector, proveedor, auditoria


def enviar(client, texto="Hola sin PII", modelo="pw-test", messages=None, endpoint="/api/v1/secure-chat"):
    return client.post(endpoint, headers=HEADERS, json={
        "model": modelo,
        "messages": messages or [{"role": "user", "content": texto}],
        "stream": False,
    })


def test_sin_pii_permite_ida_y_vuelta():
    client, detector, proveedor, auditoria = escenario()
    assert client.get("/ready").status_code == 200
    r = enviar(client)
    assert r.status_code == 200
    assert r.json()["decision"]["accion"] == "permitir"
    assert proveedor.llamadas[0][1][0].content == "Hola sin PII"
    assert len(auditoria.eventos) == 2


def test_seudonimiza_todos_los_mensajes_y_reusa_etiquetas():
    client, detector, proveedor, auditoria = escenario()
    texto = "Escribí a persona@ejemplo.cl"
    r = enviar(client, messages=[
        {"role": "system", "content": "Nunca divulgar persona@ejemplo.cl"},
        {"role": "user", "content": texto},
        {"role": "assistant", "content": "Ejemplo de 12.345.678-5"},
    ])
    assert r.status_code == 200
    assert r.json()["decision"]["accion"] == "seudonimizar"
    enviados = proveedor.llamadas[0][1]
    assert len(enviados) == 3
    assert enviados[0].content == "Nunca divulgar [PW_CORREO_1]"
    assert enviados[1].content == "Escribí a [PW_CORREO_1]"
    assert enviados[2].content == "Ejemplo de [PW_RUN_1]"
    assert "persona@ejemplo.cl" not in repr(auditoria.eventos)
    assert "12.345.678-5" not in repr(auditoria.eventos)


def test_adaptador_externo_configurado_recibe_mensajes_seudonimizados():
    client, detector, proveedor, auditoria = escenario()
    r = enviar(client, "Escribe a persona@ejemplo.cl", modelo="pw-externo")
    assert r.status_code == 200
    assert r.json()["decision"]["accion"] == "seudonimizar"
    assert len(proveedor.llamadas) == 1
    assert proveedor.llamadas[0][1][0].content == "Escribe a [PW_CORREO_1]"
    assert detector.llamadas > 0
    assert auditoria.eventos[-1]["transmision"] == "respuesta_recibida"


def test_ruta_compatible_admite_adaptador_externo_configurado():
    client, _, proveedor, _ = escenario()
    r = enviar(client, modelo="pw-externo", endpoint="/v1/chat/completions")
    assert r.status_code == 200
    assert r.json()["choices"][0]["message"]["content"] == "Respuesta simulada sin PII"
    assert len(proveedor.llamadas) == 1


def test_un_fallo_de_detector_es_fail_closed_y_no_audita_el_prompt():
    client, detector, proveedor, auditoria = escenario()
    detector.falla = True
    r = enviar(client, "persona@ejemplo.cl")
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "ANALISIS_NO_DISPONIBLE"
    assert "persona@ejemplo.cl" not in r.text
    assert not proveedor.llamadas and not auditoria.eventos


def test_respuesta_con_datos_estructurados_se_bloquea_en_retorno():
    client, _, proveedor, auditoria = escenario(respuesta="El correo es persona@ejemplo.cl")
    r = enviar(client)
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "FALLO_POSPROCESAMIENTO"
    assert "persona@ejemplo.cl" not in r.text
    assert len(proveedor.llamadas) == 1
    assert auditoria.eventos[-1]["transmision"] == "respuesta_recibida_posprocesamiento_fallido"


def test_protege_fragmentos_solapados_sin_descubrir_subcadenas():
    texto = "Dato 987654325 y repetido 987654325"
    hallazgos = []
    for m in re.finditer("987654325", texto):
        for categoria in (Categoria.RUN, Categoria.TELEFONO):
            hallazgos.append(Hallazgo(
                categoria=categoria, valor=m.group(), inicio=m.start(), fin=m.end(),
                reconocedor="falso", procedencia=Procedencia.REGEX, confianza=1,
            ))
    assert seudonimizar_texto(texto, hallazgos, {}) == "Dato [PW_RUN_1] y repetido [PW_RUN_1]"


def test_error_si_detector_entrega_hallazgo_fuera_del_texto():
    texto = "abc RUN"
    hallazgos = [Hallazgo(
        categoria=Categoria.RUN, valor="123", inicio=1, fin=4,
        reconocedor="falso", procedencia=Procedencia.REGEX, confianza=1,
    )]
    from backend.gateway.pipeline import AnalisisNoDisponible
    with pytest.raises(AnalisisNoDisponible):
        seudonimizar_texto(texto, hallazgos, {})


def test_registro_de_hallazgo_no_muestra_dato_en_repr():
    h = Hallazgo(Categoria.CORREO, "persona@ejemplo.cl", 0, 18, "prueba", Procedencia.REGEX, 1)
    assert "persona@ejemplo.cl" not in repr(h)


def test_gran_entrada_se_bloquea_antes_de_llamar_al_proveedor():
    client, detector, proveedor, _ = escenario()
    r = enviar(client, messages=[{"role": "user", "content": "x" * 20000} for _ in range(7)])
    assert r.status_code == 403
    assert not proveedor.llamadas and detector.llamadas == 0


def test_configuracion_no_necesita_demo_mode(monkeypatch):
    """El adaptador simulado debe estar disponible si figura en el catálogo."""
    import json
    from backend.gateway.config import proveedores_desde_entorno
    from backend.gateway.providers import ProveedorSimulado

    monkeypatch.setenv("GATEWAY_PROVIDERS_JSON", json.dumps({"simulado": {"tipo": "simulado"}}))
    monkeypatch.delenv("GATEWAY_DEMO_MODE", raising=False)
    adaptadores = proveedores_desde_entorno()
    assert isinstance(adaptadores["simulado"], ProveedorSimulado)


def test_pipeline_regex_se_conecta_por_defecto(monkeypatch, tmp_path):
    """No hay que activar banderas para construir el pipeline de REGEX."""
    import json
    import sys
    import types

    modulo = types.ModuleType("backend.deteccion.regex")
    modulo.EtapaRegex = DetectorFalso
    monkeypatch.setitem(sys.modules, "backend.deteccion.regex", modulo)
    monkeypatch.setenv("GATEWAY_CLIENT_TOKENS", TOKEN)
    monkeypatch.setenv("GATEWAY_ROUTES_JSON", json.dumps({
        "pw-simulado": {"proveedor": "simulado", "modelo_externo": "modelo-demo"}
    }))
    monkeypatch.setenv("GATEWAY_PROVIDERS_JSON", json.dumps({
        "simulado": {"tipo": "simulado"}
    }))
    monkeypatch.setenv("GATEWAY_AUDIT_FILE", str(tmp_path / "audit.jsonl"))
    monkeypatch.delenv("GATEWAY_DEMO_MODE", raising=False)
    monkeypatch.delenv("GATEWAY_REGEX_LAB_MODE", raising=False)

    app = create_app()
    client = TestClient(app)
    assert client.get("/ready").status_code == 200
    resultado = client.post("/api/v1/secure-chat", headers=HEADERS, json={
        "model": "pw-simulado",
        "messages": [{"role": "user", "content": "Escribe a persona@ejemplo.cl"}],
        "stream": False,
    })
    assert resultado.status_code == 200
    assert resultado.json()["decision"]["accion"] == "seudonimizar"


def test_indicadores_distinguen_mensaje_actual_de_historial():
    client, _, proveedor, _ = escenario()
    primero = [{"role": "user", "content": "Saludo sin datos"}]
    r1 = enviar(client, messages=primero)
    assert r1.status_code == 200
    assert r1.json()["decision"]["mensaje_actual_seudonimizado"] is False
    assert r1.json()["decision"]["historial_seudonimizado"] is False

    segundo = primero + [
        {"role": "assistant", "content": "Respuesta simulada sin PII"},
        {"role": "user", "content": "Escribí a persona@ejemplo.cl"},
    ]
    r2 = enviar(client, messages=segundo)
    assert r2.status_code == 200
    assert r2.json()["decision"]["accion"] == "seudonimizar"
    assert r2.json()["decision"]["mensaje_actual_seudonimizado"] is True
    assert r2.json()["decision"]["historial_seudonimizado"] is False

    tercero = segundo + [
        {"role": "assistant", "content": "Respuesta simulada sin PII"},
        {"role": "user", "content": "Otro texto sin datos"},
    ]
    r3 = enviar(client, messages=tercero)
    assert r3.status_code == 200
    decision = r3.json()["decision"]
    assert decision["accion"] == "seudonimizar"  # Se protege la solicitud completa
    assert decision["mensaje_actual_seudonimizado"] is False
    assert decision["historial_seudonimizado"] is True
    assert proveedor.llamadas[-1][1][-1].content == "Otro texto sin datos"
    assert "persona@ejemplo.cl" not in [m.content for m in proveedor.llamadas[-1][1]]
