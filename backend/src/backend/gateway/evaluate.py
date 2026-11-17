"""Evaluación sintética reproducible; sin valores de PII en resultados."""
import argparse
import asyncio
import collections
import json
import math
import hashlib
import os
from pathlib import Path
import time

from .contracts import SolicitudChat, Mensaje
from .pipeline import ContextoEjecucion
from .hybrid import desde_entorno
from .hybrid import INSTRUCCION, JuicioSLM
from .slm_protocol import VERSION, ExtraccionPorCategoria, Nombres, AccionPropuesta, Fundamento


def metricas(tp, fp, fn):
    p = tp/(tp+fp) if tp+fp else None
    r = tp/(tp+fn) if tp+fn else None
    f2 = 5*tp/(5*tp+4*fn+fp) if tp+fn+fp else None
    return dict(tp=tp, fp=fp, fn=fn, precision=p, recall=r, f2=f2)


def percentil(xs, q):
    return sorted(xs)[max(0, math.ceil(len(xs)*q)-1)] if xs else None


async def evaluar(args):
    from .regex_pipeline import PipelineRegex
    from .providers import ProveedorSimulado
    datos = json.loads((args.datos / f"{args.split}.json").read_text(encoding="utf-8"))
    p = desde_entorno()
    if not await p.comprobar():
        raise RuntimeError("Servicios no disponibles; no se genera evaluación ficticia")
    rg = PipelineRegex()
    banco = None
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    if args.nivel == "flujo":
        from .evaluation_flow import BancoFlujo
        banco = BancoFlujo(p, args.salida.with_suffix(".events.jsonl"))
    muestras, categorias = [], collections.defaultdict(lambda: [0,0,0])
    if args.limite:
        datos = datos[:args.limite]
    sem = asyncio.Semaphore(args.concurrencia)
    async def uno(caso, guardar=True):
        solicitud = SolicitudChat(model="pw-simulado", messages=[Mensaje(**m) for m in caso["mensajes"]])
        contexto = ContextoEjecucion("evaluacion", "sintetico")
        async with sem:
            t = time.perf_counter()
            d, error, enviados = None, None, None
            predichos = []
            try:
                if args.modo == "regex":
                    for i,m in enumerate(solicitud.messages):
                        predichos.extend((i,h.inicio,h.fin,h.categoria.value) for h in rg._detectar(m.content))
                    if args.nivel == "flujo":
                        d = await rg.analizar(solicitud, contexto)
                else:
                    p.usar_regex = args.modo == "hibrido"
                    if args.nivel == "deteccion":
                        d = await p.detectar(solicitud, contexto)
                    else:
                        d, error, enviados = await banco.ejecutar(solicitud)
                    predichos = [(h["mensaje"],h["inicio"],h["fin"],h["categoria"])
                                 for h in d.traza["hallazgos"]] if d else []
            except Exception as exc:
                error = getattr(exc, "codigo", "FALLO_TECNICO")
            latencia = (time.perf_counter()-t)*1000
        verdad = {(h["mensaje"],h["inicio"],h["fin"],h["categoria"]) for h in caso["hallazgos"]}
        pred = set(predichos)
        if guardar:
            for cat in {h[3] for h in verdad | pred}:
                v, pr = {h for h in verdad if h[3] == cat}, {h for h in pred if h[3] == cat}
                for i,n in enumerate((len(v & pr), len(pr-v), len(v-pr))):
                    categorias[cat][i] += n
            transmitida = enviados is not None
            expuestas = None
            if transmitida:
                # Proveedor espía local: texto exacto que habría recibido el simulador.
                expuestas = sum(solicitud.messages[m].content[a:b] in enviados[m].content
                                for m,a,b,_ in verdad)
            muestras.append(dict(id=caso["id"], error=error, latencia_ms=latencia,
                                  tp=len(verdad & pred),fp=len(pred-verdad),fn=len(verdad-pred),
                                  categorias_omitidas=sorted({h[3] for h in verdad-pred}),
                                  accion=d.accion.value if d and args.nivel == "flujo" else None,
                                  esperada=caso["accion"] if args.nivel == "flujo" else None,
                                  transmitida=transmitida, apariciones_expuestas=expuestas,
                                  apariciones_anotadas=len(verdad),
                                  recuperados=(d.traza.get("recuperados") or [f["id"] for f in d.traza.get("fragmentos",[])]) if d else [],
                                  tiempos=d.traza.get("tiempos", {}) if d else {}))
    await uno(datos[0], guardar=False)  # Calentamiento, fuera de métricas.
    inicio = time.perf_counter()
    await asyncio.gather(*(uno(c) for c in datos))
    duracion = time.perf_counter()-inicio
    if banco is not None:
        await banco.cerrar()
    rag = []
    for c in json.loads((args.datos / "recuperacion.json").read_text(encoding="utf-8")):
        if c["split"] != args.split:
            continue
        fs = await p.recuperador.buscar([Mensaje(role="user", content=c["consulta"])], [])
        rag.append(dict(id=c["id"], acierto=any(f["id"].startswith(c["esperado"]+"_") for f in fs)))
    xs = [s["latencia_ms"] for s in muestras]
    resumen = dict(modo=args.modo, nivel=args.nivel, split=args.split, concurrencia=args.concurrencia,
                   versiones=await p.recuperador.versiones(), modelo=p.slm.modelo,
                   revision_modelo=p.slm.revision,
                   repo_modelo=p.slm.repo,
                   protocolo=VERSION,
                   transporte="API ASGI local con auditoria y simulador" if banco else "analizador directo",
                   contexto_tokens=p.slm.contexto,
                   prefill_tokens=int(os.environ.get("PRIVATEWAY_PREFILL_TOKENS","512")),
                   gpu_memory=float(os.environ.get("PRIVATEWAY_GPU_MEMORY","0.75")),
                   instrucciones_sha256=hashlib.sha256(INSTRUCCION.encode()).hexdigest(),
                   esquema_sha256=hashlib.sha256(json.dumps(JuicioSLM.model_json_schema(),sort_keys=True).encode()).hexdigest(),
                   esquemas_wire_sha256=hashlib.sha256(json.dumps([ExtraccionPorCategoria.model_json_schema(),Nombres.model_json_schema(),AccionPropuesta.model_json_schema(),Fundamento.model_json_schema()],sort_keys=True).encode()).hexdigest(),
                   dataset_sha256=hashlib.sha256((args.datos/f"{args.split}.json").read_bytes()).hexdigest(),
                   n=len(muestras), errores=sum(bool(s["error"]) for s in muestras),
                   bloqueos=sum(s["accion"] == "bloquear" for s in muestras),
                   transmitidas=sum(s["transmitida"] for s in muestras),
                   deteccion={c:metricas(*v) for c,v in categorias.items()},
                   micro=metricas(*(sum(v[i] for v in categorias.values()) for i in range(3))),
                   aciertos_accion=sum(s["accion"] == s["esperada"] and not s["error"] for s in muestras)
                                    if args.nivel == "flujo" else None,
                   recall4=sum(c["acierto"] for c in rag)/len(rag) if rag else None,
                   p50_ms=percentil(xs,.5), p95_ms=percentil(xs,.95), p99_ms=percentil(xs,.99),
                   throughput=len(muestras)/duracion, muestras=muestras, recuperacion=rag,
                   limitaciones=["Corpus sintético preliminar; anotación requiere revisión humana.",
                                 "Exposición medida por valores literales; no evalúa reidentificación.",
                                 "Fallo técnico cuenta como omisión en detección, no como bloqueo."])
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k:resumen[k] for k in ("n","errores","p50_ms","p95_ms","recall4")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--datos", type=Path, default=Path("/pilot/datasets"))
    parser.add_argument("--split", choices=["desarrollo","validacion"], default="desarrollo")
    parser.add_argument("--modo", choices=["regex","slm","hibrido"], default="hibrido")
    parser.add_argument("--nivel", choices=["deteccion","flujo"], default="deteccion")
    parser.add_argument("--concurrencia", type=int, choices=[1,5,10], default=1)
    parser.add_argument("--limite", type=int)
    parser.add_argument("--salida", type=Path, required=True)
    args = parser.parse_args()
    if args.nivel == "flujo" and args.modo != "hibrido":
        parser.error("El flujo completo evalua el gateway hibrido; usar deteccion para las lineas base")
    asyncio.run(evaluar(args))
