import asyncio
import httpx
import pytest
from privateway_model.slm import ClienteVLLM
from privateway_model.hybrid import JuicioSLM


def cliente(handler, contexto=4096):
    slm = ClienteVLLM(url="http://interno", token="sintetico", modelo="test", contexto=contexto)
    slm.cliente = lambda: httpx.AsyncClient(base_url="http://interno", transport=httpx.MockTransport(handler))
    return slm


def test_exceso_contexto_no_genera_ni_trunca():
    llamadas = []
    def manejar(r):
        llamadas.append(r.url.path)
        return httpx.Response(200, json={"count": 3100})
    with pytest.raises(ValueError, match="CONTEXTO_EXCEDIDO"):
        asyncio.run(cliente(manejar).juzgar("sistema", {"texto": "entrada completa"}, JuicioSLM.model_json_schema()))
    assert llamadas == ["/tokenize"]


@pytest.mark.parametrize("tipo", ["timeout", "incompleta", "http"])
def test_fallos_sin_reintento(tipo):
    llamadas = []
    def manejar(r):
        llamadas.append(r.url.path)
        if r.url.path == "/tokenize":
            return httpx.Response(200, json={"count": 20})
        if tipo == "timeout":
            raise httpx.ReadTimeout("fallo")
        if tipo == "http":
            return httpx.Response(503)
        return httpx.Response(200, json={"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]})
    with pytest.raises((ValueError, httpx.HTTPError)):
        asyncio.run(cliente(manejar).juzgar("sistema", {}, JuicioSLM.model_json_schema()))
    assert llamadas == ["/tokenize", "/v1/chat/completions"]


def test_esquema_estricto_y_temperatura():
    import json
    def manejar(r):
        if r.url.path == "/tokenize":
            return httpx.Response(200, json={"count": 20})
        payload = json.loads(r.content)
        assert payload["temperature"] == 0
        assert payload["max_tokens"] == 1024
        assert payload["response_format"]["json_schema"]["strict"]
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]})
    assert asyncio.run(cliente(manejar).juzgar("sistema", {}, JuicioSLM.model_json_schema())) == "{}"
