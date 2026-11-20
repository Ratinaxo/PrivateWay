import asyncio
import json
import pytest
from backend.deteccion.hallazgo import (Categoria, ClaseLegal, CLASE_POR_CATEGORIA,
                                        SUBCATEGORIAS_SENSIBLES)
from privateway_model.slm_protocol import Extraccion, ExtraccionPorCategoria, anclar, analizar
from privateway_model.slm_protocol import extraer


def entidad(texto, mensaje=0, categoria="persona"):
    return {"categoria":categoria,"texto":texto,"mensaje":mensaje,"persona_asociada":categoria == "salud"}


def wire(entidades):
    grupos={c:[] for c in [
        "persona", "direccion", "identificador", "run", "correo", "telefono", "tarjeta",
        "patente", "origen_etnico", "afiliacion", "socioeconomico", "convicciones", "salud",
        "perfil_biologico", "biometrico", "sexualidad", "menor_de_edad", "geolocalizacion",
        "obligaciones", "infracciones",
    ]}
    for e in entidades:
        m={"texto":e["texto"],"mensaje":e["mensaje"]}
        if e["categoria"] == "salud":
            m["persona_asociada"]=e["persona_asociada"]
            m["subcategoria"]="datos relativos a la salud"
        elif Categoria(e["categoria"]) in SUBCATEGORIAS_SENSIBLES:
            m["subcategoria"] = sorted(SUBCATEGORIAS_SENSIBLES[Categoria(e["categoria"])])[0]
        if e["categoria"] == "menor_de_edad":
            m["asociado_a"] = e.get("asociado_a", "Ana Torres")
        grupos[e["categoria"]].append(m)
    return json.dumps(grupos)


def test_offsets_locales_unicode_repeticiones_y_mensajes():
    ms = [{"indice":0,"texto":"Inés Araya escribió. Luego Inés Araya volvió."},
          {"indice":1,"texto":"Inés Araya llamó."}]
    ex = Extraccion.model_validate({"entidades":[entidad("Inés Araya"),entidad("Inés Araya",1)]})
    hs = anclar(ex,ms,[])
    assert len(hs) == 3
    assert len({h["id"] for h in hs}) == 3
    for h in hs:
        assert ms[h["mensaje"]]["texto"][h["inicio"]:h["fin"]] == h["texto"]


def test_duplicado_con_corchetes_solo_se_descarta_si_regex_lo_acredita():
    valor = "contacto@example.test"
    mensajes = [dict(indice=0, texto=valor)]
    extraidas = Extraccion.model_validate({"entidades": [entidad(f"[{valor}]", categoria="correo")]})
    previo = dict(id="r0", mensaje=0, inicio=0, fin=len(valor), categoria="correo",
                  texto=valor, persona_asociada=False)
    assert anclar(extraidas, mensajes, [previo]) == [previo]
    with pytest.raises(ValueError, match="entidad no literal"):
        anclar(extraidas, mensajes, [])


@pytest.mark.parametrize("literal", ["Ana", "ana", "Otro nombre", "mariana"])
def test_rechaza_alucinacion_subcadena_y_normalizacion(literal):
    ex = Extraccion.model_validate({"entidades":[entidad(literal)]})
    with pytest.raises(ValueError,match="entidad no literal"):
        anclar(ex,[{"indice":0,"texto":"Mariana"}],[])


def test_conserva_regex_y_deduplica_mismo_span():
    previo = dict(id="r0",mensaje=0,inicio=0,fin=14,categoria="correo",texto="a@example.test",persona_asociada=False)
    ex = Extraccion.model_validate({"entidades":[entidad("a@example.test",categoria="correo")]})
    assert anclar(ex,[{"indice":0,"texto":"a@example.test"}],[previo]) == [previo]


def test_fusion_de_salud_combina_asociacion_personal():
    previo = dict(id="r0", mensaje=0, inicio=10, fin=18, categoria="salud",
                  texto="diabetes", persona_asociada=False)
    ex = Extraccion.model_validate({"entidades": [entidad("diabetes", categoria="salud")]})
    salida = anclar(ex, [{"indice": 0, "texto": "Ana tiene diabetes"}], [previo])
    assert len(salida) == 1
    assert salida[0]["persona_asociada"] is True


def test_taxonomia_completa_declara_clase_legal_y_subcategorias():
    categorias = {campo for campo in ExtraccionPorCategoria.model_fields}
    assert categorias == {categoria.value for categoria in Categoria}
    assert CLASE_POR_CATEGORIA[Categoria.SALUD] == ClaseLegal.SENSIBLE
    assert CLASE_POR_CATEGORIA[Categoria.GEOLOCALIZACION] == ClaseLegal.REGIMEN_ESPECIAL
    assert "datos genéticos" in SUBCATEGORIAS_SENSIBLES[Categoria.PERFIL_BIOLOGICO]


def test_menor_de_edad_se_asocia_a_hallazgo_de_persona():
    ex = Extraccion.model_validate({"entidades": [{
        "categoria": "menor_de_edad", "texto": "13 años", "mensaje": 0,
        "persona_asociada": False, "asociado_a": "Ana Torres",
    }]})
    salida = anclar(ex, [{"indice": 0, "texto": "Ana Torres tiene 13 años"}], [])
    menor = next(h for h in salida if h["categoria"] == "menor_de_edad")
    persona = next(h for h in salida if h["categoria"] == "persona")
    assert menor["asociado_a"] == "Ana Torres"
    assert persona["texto"] == "Ana Torres"


def test_subcategoria_sensible_invalida_se_rechaza():
    ex = Extraccion.model_validate({"entidades": [{
        "categoria": "salud", "texto": "asma", "mensaje": 0,
        "persona_asociada": False, "subcategoria": "origen racial",
    }]})
    with pytest.raises(ValueError, match="subcategoria sensible invalida"):
        anclar(ex, [{"indice": 0, "texto": "asma"}], [])


def test_accion_determinista_y_fuentes_solo_al_fundamento():
    class Cliente:
        def __init__(self): self.llamadas=[]
        async def juzgar(self, instrucciones, datos, esquema):
            self.llamadas.append(datos)
            if len(self.llamadas) == 1:
                return wire([entidad("Ana Torres")])
            return json.dumps({"referencias":["art2"],
                               "justificacion":"La política técnica del flujo principal se aplica al hallazgo."})
    c = Cliente()
    entrada = dict(mensajes=[dict(indice=0,texto="Ana Torres")],regex=[],fragmentos=[dict(id="art2",texto="Ley sobre salud.")])
    salida = json.loads(asyncio.run(analizar(c,entrada)))
    assert salida["accion"] == "seudonimizar"
    assert salida["seleccionados"] == ["s0"]
    assert "fuentes" not in c.llamadas[0] and "fragmentos" not in c.llamadas[0]
    assert "Ana Torres" not in json.dumps(c.llamadas[1])
    assert c.llamadas[1]["accion"] == "seudonimizar"
    assert len(c.llamadas) == 2


def test_no_hay_segunda_llamada_si_extraccion_inventada():
    class Cliente:
        llamadas = 0
        async def juzgar(self,*args):
            self.llamadas += 1
            return wire([entidad("Nombre inventado")])
    c=Cliente()
    with pytest.raises(ValueError, match="entidad no literal"):
        asyncio.run(analizar(c,dict(mensajes=[dict(indice=0,texto="Hola")],regex=[],fragmentos=[])))
    assert c.llamadas == 1


def test_extraccion_y_fundamento_separados_con_accion_local():
    class Cliente:
        def __init__(self): self.llamadas=[]
        async def juzgar(self,instruccion,datos,esquema):
            self.llamadas.append(datos)
            if len(self.llamadas) == 1:
                return wire([entidad("Ana Torres")])
            return json.dumps({"referencias":["art2"],"justificacion":"Dato personal; criterio técnico del flujo principal."})
    c=Cliente()
    r=json.loads(asyncio.run(analizar(c,dict(mensajes=[dict(indice=0,texto="Ana Torres")],regex=[],
                                              fragmentos=[dict(id="art2",texto="Definición legal")]))))
    assert len(c.llamadas) == 2
    assert "fuentes" not in c.llamadas[0]
    assert c.llamadas[1]["accion"] == "seudonimizar"
    assert c.llamadas[1]["politica"]
    assert r["hallazgos"][0]["fin"] == 10
    assert r["accion"] == "seudonimizar"


def test_revision_de_nombres_omitidos_sigue_exigiendo_literalidad():
    class Cliente:
        llamadas=0
        async def juzgar(self,*args):
            self.llamadas += 1
            return wire([]) if self.llamadas == 1 else json.dumps({"personas":[dict(texto="Ana Torres",mensaje=0)]})
    c=Cliente()
    hs=asyncio.run(extraer(c,dict(mensajes=[dict(indice=0,texto="Ana Torres usa el correo")],regex=[])))
    assert len(hs) == 1 and hs[0]["texto"] == "Ana Torres" and c.llamadas == 2
    c=Cliente()
    with pytest.raises(ValueError,match="entidad no literal"):
        asyncio.run(extraer(c,dict(mensajes=[dict(indice=0,texto="Texto sin nombres")],regex=[])))


@pytest.mark.parametrize("respuesta, confirmada", [
    (["s1"], True), ([], False), (["inventado"], None), (["s1", "s1"], None),
])
def test_asociacion_de_salud_solo_confirma_ids_anclados(respuesta, confirmada):
    class Cliente:
        async def juzgar(self, _, datos, esquema):
            if "diagnosticos" not in datos:
                return wire([
                    entidad("Ana Torres"),
                    {**entidad("diabetes", categoria="salud"), "persona_asociada": False},
                ])
            assert datos["diagnosticos"] == [{"id": "s1", "mensaje": 0, "texto": "diabetes"}]
            assert esquema["properties"]["asociados"]["items"]["enum"] == ["s1"]
            return json.dumps({"asociados": respuesta})

    entrada = dict(mensajes=[dict(indice=0, texto="Ana Torres tiene diabetes.")], regex=[])
    if confirmada is None:
        with pytest.raises(ValueError, match="asociacion de salud invalida"):
            asyncio.run(extraer(Cliente(), entrada))
    else:
        hallazgos = asyncio.run(extraer(Cliente(), entrada))
        assert hallazgos[1]["persona_asociada"] is confirmada
