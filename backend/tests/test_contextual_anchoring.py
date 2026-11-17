import asyncio
import json
from backend.gateway.slm_protocol import extraer


def test_contexto_original_y_registro_regex_conservado():
    original="Ana Torres usa a@example.test."
    i=original.index("a@example.test")
    previo=dict(id="r0",mensaje=0,inicio=i,fin=i+14,categoria="correo",texto="a@example.test",persona_asociada=False)
    class Cliente:
        async def juzgar(self,instruccion,datos,esquema):
            t=datos["mensajes"][0]["texto"]
            assert t == original
            assert "[PW_" not in t
            return json.dumps(dict(persona=[dict(texto="Ana Torres",mensaje=0)],direccion=[],salud=[],run=[],correo=[],telefono=[]))
    hs=asyncio.run(extraer(Cliente(),dict(mensajes=[dict(indice=0,texto=original)],regex=[previo])))
    assert hs[0] == previo
    assert hs[1]["texto"] == original[hs[1]["inicio"]:hs[1]["fin"]] == "Ana Torres"
