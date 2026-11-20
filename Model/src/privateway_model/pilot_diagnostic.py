"""Diagnóstico exclusivo con entrada SINTÉTICA fija. Nunca recibe consultas reales."""
import asyncio
import json
import time
from privateway_model.hybrid import desde_entorno
from backend.gateway.contracts import Mensaje


async def main(caso):
    p = desde_entorno()
    contenido = {"hola":"Hola mundo", "nombre":"La persona solicitante se llama Ana Torres.",
                 "salud":"Resume este texto: Elena Rojas tiene asma.",
                 "direccion":"Mi domicilio es Pasaje del Faro 42."}[caso]
    mensajes = [Mensaje(role="user",content=contenido)]
    t = time.perf_counter()
    fragmentos = await p.recuperador.buscar(mensajes, [])
    print(json.dumps({"etapa":"rag", "segundos":time.perf_counter()-t,
                      "ids":[f["id"] for f in fragmentos]}),flush=True)
    entrada = dict(fragmentos=fragmentos, regex=[],
                   mensajes=[dict(indice=0, role="user", texto=contenido)])
    try:
        t = time.perf_counter()
        hallazgos = await p.slm.extraer_entidades(entrada)
        print(json.dumps({"etapa":"slm", "segundos":time.perf_counter()-t,
                          "categorias":[h["categoria"] for h in hallazgos],
                          "hallazgos":len(hallazgos)}),flush=True)
        print(json.dumps({"etapa":"esquema", "valido":True,
                          "hallazgos_anclados":len(hallazgos)}),flush=True)
    except Exception as exc:
        print(json.dumps({"etapa":"slm", "tipo_error":type(exc).__name__,
                          "codigo": str(exc) if isinstance(exc,ValueError) and not hasattr(exc,"errors") else "no_disponible"}),flush=True)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--caso", choices=["hola","nombre","salud","direccion"], default="hola")
    asyncio.run(main(parser.parse_args().caso))
