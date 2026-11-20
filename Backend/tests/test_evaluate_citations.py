import asyncio
import json
from types import SimpleNamespace

from privateway_model import evaluate_citations
from backend.gateway.pipeline import AnalisisNoDisponible


def test_recuperar_disposicion_no_equivale_a_citarla(tmp_path, monkeypatch):
    class Evaluador:
        slm = SimpleNamespace(revision="revision-sintetica")

        @property
        def recuperador(self):
            return self

        async def comprobar(self):
            return True

        async def versiones(self):
            return {"indice": "indice-sintetico"}

        def _detectar(self, texto):
            return []

        async def buscar(self, mensajes, regex):
            return [
                {"id": "ley21719_fragmento_0", "identificador_normativo": "art2_f",
                 "localizador": "Ley 19.628 art. 2 f)"},
                {"id": "ley21719_fragmento_1", "identificador_normativo": "art2_g",
                 "localizador": "Ley 19.628 art. 2 g)"},
            ]

        async def analizar(self, solicitud, contexto):
            pregunta = solicitud.messages[0].content
            if pregunta == "11":
                raise AnalisisNoDisponible()
            fragmentos = await self.buscar([], [])
            return SimpleNamespace(traza={
                "fragmentos": fragmentos,
                "referencias": [fragmentos[0]["id"] if pregunta == "0" else fragmentos[1]["id"]],
                "justificacion": "Fundamento sintético",
            })

    datos = tmp_path / "preguntas.json"
    datos.write_text(json.dumps([
        dict(id=f"dev-{i}", split="desarrollo", consulta=str(i), esperado="art2_f")
        for i in range(12)
    ] + [dict(id="reservada", split="validacion", consulta="no ejecutar", esperado="art2_f")]))
    salida = tmp_path / "resultado.json"
    monkeypatch.setattr(evaluate_citations, "desde_entorno", Evaluador)
    asyncio.run(evaluate_citations.evaluar("desarrollo", datos, salida))
    resultado = json.loads(salida.read_text(encoding="utf-8"))
    assert resultado["recuperaciones_correctas"] == 12
    assert resultado["recall_at_4"] == 1.0
    assert resultado["muestras"][0]["fragmentos_recuperados"][0]["localizador"] == "Ley 19.628 art. 2 f)"
    assert resultado["muestras"][0]["citas_resueltas"][0]["identificador_normativo"] == "art2_f"
    assert resultado["citas_esperadas"] == 1
    assert resultado["juicios_evaluables"] == 11
    assert resultado["muestras"][-1]["cita_esperada"] is None
