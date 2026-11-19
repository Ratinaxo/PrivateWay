import asyncio
import json
from types import SimpleNamespace

from backend.gateway import evaluate_citations
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

        async def buscar(self, mensajes, regex):
            return [{"id": "art2_f_0"}, {"id": "art2_g_0"}]

        async def analizar(self, solicitud, contexto):
            pregunta = solicitud.messages[0].content
            if pregunta == "11":
                raise AnalisisNoDisponible()
            return SimpleNamespace(traza={
                "fragmentos": await self.buscar([], []),
                "referencias": ["art2_f_0" if pregunta == "0" else "art2_g_0"],
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
    assert resultado["citas_esperadas"] == 1
    assert resultado["juicios_evaluables"] == 11
    assert resultado["muestras"][-1]["cita_esperada"] is None
