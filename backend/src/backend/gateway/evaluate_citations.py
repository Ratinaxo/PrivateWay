"""Compara recuperación y citas del juicio del gateway en preguntas sintéticas."""
import argparse
import asyncio
import json
from pathlib import Path

from .contracts import Mensaje, SolicitudChat
from .hybrid import desde_entorno
from .pipeline import AnalisisNoDisponible, ContextoEjecucion
from .slm_protocol import VERSION


async def evaluar(split: str, dataset: Path, salida: Path) -> None:
    casos = [c for c in json.loads(dataset.read_text(encoding="utf-8")) if c["split"] == split]
    if len(casos) != 12:
        raise ValueError("Se esperaban doce preguntas jurídicas en el conjunto")
    pipeline = desde_entorno()
    if not await pipeline.comprobar():
        raise RuntimeError("Servicios del piloto no disponibles")
    muestras = []
    for caso in casos:
        mensajes = [Mensaje(role="user", content=caso["consulta"])]
        esperado = caso["esperado"] + "_"
        recuperados = await pipeline.recuperador.buscar(mensajes, [])
        ids = [f["id"] for f in recuperados]
        muestra = dict(id=caso["id"], esperado=caso["esperado"], recuperados=ids,
                       recuperacion_correcta=any(i.startswith(esperado) for i in ids))
        try:
            decision = await pipeline.analizar(
                SolicitudChat(model="pw-simulado", messages=mensajes),
                ContextoEjecucion("evaluacion-citas", "sintetico"),
            )
        except AnalisisNoDisponible as exc:
            muestra.update(error=exc.codigo, citados=[], cita_esperada=None)
        else:
            traza = decision.traza
            citados = traza["referencias"]
            contexto = [f["id"] for f in traza["fragmentos"]]
            muestra.update(error=None, citados=citados, contexto_del_juicio=contexto,
                           esperado_en_contexto=any(i.startswith(esperado) for i in contexto),
                           cita_esperada=any(i.startswith(esperado) for i in citados),
                           justificacion=traza["justificacion"])
        muestras.append(muestra)
    resumen = dict(split=split, protocolo=VERSION, versiones=await pipeline.recuperador.versiones(),
                   revision_modelo=pipeline.slm.revision, muestras=muestras,
                   recuperaciones_correctas=sum(m["recuperacion_correcta"] for m in muestras),
                   citas_esperadas=sum(m["cita_esperada"] is True for m in muestras),
                   juicios_evaluables=sum(m["error"] is None for m in muestras))
    with salida.open("x", encoding="utf-8") as archivo:
        json.dump(resumen, archivo, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("desarrollo", "validacion"), default="desarrollo")
    parser.add_argument("--dataset", type=Path, default=Path("/pilot/datasets/recuperacion.json"))
    parser.add_argument("--salida", type=Path, required=True)
    args = parser.parse_args()
    if args.salida.exists():
        parser.error("Usar un archivo nuevo")
    asyncio.run(evaluar(args.split, args.dataset, args.salida))
