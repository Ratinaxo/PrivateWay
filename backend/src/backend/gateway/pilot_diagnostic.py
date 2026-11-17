"""Diagnóstico exclusivo con entrada SINTÉTICA fija. Nunca recibe consultas reales."""
import asyncio
import json
import time
import re
from .hybrid import desde_entorno, INSTRUCCION, JuicioSLM
from .contracts import Mensaje


async def main(caso, con_regex=False):
    p = desde_entorno()
    contenido = {"hola":"Hola mundo", "nombre":"La persona solicitante se llama Ana Torres.",
                 "mixto":"Resume este texto: Ana Torres usa persona0@example.test y +56987654320.",
                 "salud":"Ana Torres tiene diabetes."}[caso]
    mensajes = [Mensaje(role="user",content=contenido)]
    t = time.perf_counter()
    fragmentos = await p.recuperador.buscar(mensajes, [])
    print(json.dumps({"etapa":"rag", "segundos":time.perf_counter()-t,
                      "ids":[f["id"] for f in fragmentos]}),flush=True)
    entrada = dict(fragmentos=fragmentos, regex=[],mensajes=[dict(indice=0,role="user",texto=contenido,
        posiciones_palabras="; ".join(f"{w.start()}-{w.end()}:{w.group()}" for w in re.finditer(r"\w+(?:[-']\w+)*",contenido)))])
    if con_regex:
        entrada["regex"] = [dict(id=f"r{i}",mensaje=0,inicio=h.inicio,fin=h.fin,categoria=h.categoria.value,
                               texto=h.valor,persona_asociada=False) for i,h in enumerate(p._detectar(contenido))]
    try:
        original = p.slm.juzgar
        async def observar(instrucciones, datos, esquema):
            r = await original(instrucciones,datos,esquema)
            print(json.dumps({"etapa":"salida_fija", "salida_sintetica":r}),flush=True)
            return r
        p.slm.juzgar = observar
        t = time.perf_counter()
        esquema = JuicioSLM.model_json_schema()
        esquema["properties"]["referencias"]["items"] = {"type":"string", "enum":[f["id"] for f in fragmentos]}
        salida = await p.slm.analizar_etapas(entrada)
        print(json.dumps({"etapa":"slm", "segundos":time.perf_counter()-t,
                          "salida_sintetica":salida}),flush=True)
        j = JuicioSLM.model_validate_json(salida)
        print(json.dumps({"etapa":"esquema", "accion":j.accion}),flush=True)
    except Exception as exc:
        print(json.dumps({"etapa":"slm", "tipo_error":type(exc).__name__,
                          "codigo": str(exc) if isinstance(exc,ValueError) and not hasattr(exc,"errors") else "no_disponible"}),flush=True)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--caso", choices=["hola","nombre","salud","mixto"], default="hola")
    parser.add_argument("--con-regex",action="store_true")
    args=parser.parse_args()
    asyncio.run(main(args.caso,args.con_regex))
