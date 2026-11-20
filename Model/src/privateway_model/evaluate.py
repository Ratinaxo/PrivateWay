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

from backend.gateway.contracts import SolicitudChat, Mensaje
from backend.gateway.pipeline import ContextoEjecucion
from privateway_model.hybrid import desde_entorno
from privateway_model.slm_protocol import (VERSION as SLM_PROTOCOL_VERSION, EXTRACCION, NOMBRES,
                           REGLA_ACCION, FUNDAMENTO, ExtraccionPorCategoria,
                           Nombres, AsociacionSalud, Fundamento)
from privateway_model.metrics import (metricas, macro_por_categoria, exposicion_solicitud,
                      conteos_parciales)


def percentil(xs, q):
    return sorted(xs)[max(0, math.ceil(len(xs)*q)-1)] if xs else None


async def evaluar(args):
    from backend.gateway.regex_pipeline import PipelineRegex
    from backend.gateway.providers import ProveedorSimulado
    datos = json.loads((args.datos / f"{args.split}.json").read_text(encoding="utf-8"))
    p = desde_entorno()
    if not await p.comprobar():
        raise RuntimeError("Servicios no disponibles; no se genera evaluación ficticia")
    rg = PipelineRegex()
    banco = None
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    if args.nivel == "flujo":
        from privateway_model.evaluation_flow import BancoFlujo
        banco = BancoFlujo(p, args.salida.with_suffix(".events.jsonl"))
    muestras = []
    categorias = collections.defaultdict(lambda: [0,0,0])
    categorias_parciales = collections.defaultdict(lambda: [0,0,0])
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
            conteos_caso = {}
            conteos_parciales_caso = {}
            for cat in {h[3] for h in verdad | pred}:
                v, pr = {h for h in verdad if h[3] == cat}, {h for h in pred if h[3] == cat}
                exactos = (len(v & pr), len(pr-v), len(v-pr))
                parciales = conteos_parciales(v, pr)
                for i, n in enumerate(exactos):
                    categorias[cat][i] += n
                for i, n in enumerate(parciales):
                    categorias_parciales[cat][i] += n
                conteos_caso[cat] = dict(tp=exactos[0], fp=exactos[1], fn=exactos[2])
                conteos_parciales_caso[cat] = dict(tp=parciales[0], fp=parciales[1], fn=parciales[2])
            transmitida = enviados is not None
            exposicion = (exposicion_solicitud(solicitud.messages, enviados, list(verdad))
                          if transmitida else None)
            if transmitida:
                estado_transmision = "confirmada"
            elif d and d.accion.value == "bloquear" and not error:
                estado_transmision = "bloqueada"
            elif error:
                estado_transmision = "fallo_sin_envio_en_simulador"
            else:
                estado_transmision = "no_transmitida"
            muestras.append(dict(id=caso["id"], error=error, latencia_ms=latencia,
                                  accion=d.accion.value if d and args.nivel == "flujo" else None,
                                  esperada=caso["accion"] if args.nivel == "flujo" else None,
                                  transmitida=transmitida, estado_transmision=estado_transmision,
                                  apariciones_expuestas=exposicion["expuestas"] if exposicion else None,
                                  apariciones_expuestas_exactas=exposicion["exactas"] if exposicion else None,
                                  apariciones_expuestas_parciales=exposicion["parciales"] if exposicion else None,
                                  apariciones_referencia_transmitidas=exposicion["referencias"] if exposicion else None,
                                  tasa_exposicion_solicitud=exposicion["tasa"] if exposicion else None,
                                  familia=caso.get("familia", caso["id"]),
                                  conteos_categoria=conteos_caso,
                                  conteos_parciales_categoria=conteos_parciales_caso,
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
    deteccion = {c:metricas(*v) for c,v in categorias.items()}
    deteccion_parcial = {c:metricas(*v) for c,v in categorias_parciales.items()}
    exposiciones = [s for s in muestras if s["transmitida"]]
    spans_transmitidos = sum(s["apariciones_referencia_transmitidas"] or 0 for s in exposiciones)
    spans_expuestos = sum(s["apariciones_expuestas"] or 0 for s in exposiciones)
    spans_expuestos_exactos = sum(s["apariciones_expuestas_exactas"] or 0 for s in exposiciones)
    spans_expuestos_parciales = sum(s["apariciones_expuestas_parciales"] or 0 for s in exposiciones)
    solicitudes_sensibles = [s for s in exposiciones if s["apariciones_referencia_transmitidas"]]
    matriz_acciones = {esperada: {observada: 0 for observada in
                       ("permitir", "seudonimizar", "bloquear", "error")}
                       for esperada in ("permitir", "seudonimizar", "bloquear")}
    for muestra in muestras:
        if muestra["esperada"] in matriz_acciones:
            observada = muestra["accion"] or "error"
            matriz_acciones[muestra["esperada"]][observada] += 1
    controles_limpios = [s for s in muestras if s["esperada"] == "permitir"]
    controles_decididos = [s for s in controles_limpios if s["accion"] is not None]
    prompts_activos = dict(extraccion=EXTRACCION, revision_nombres=NOMBRES,
                           politica=REGLA_ACCION, fundamento=FUNDAMENTO,
                           protocolo=SLM_PROTOCOL_VERSION)
    esquemas_activos = dict(extraccion=ExtraccionPorCategoria.model_json_schema(),
                            revision_nombres=Nombres.model_json_schema(),
                            asociacion_salud=AsociacionSalud.model_json_schema(),
                            fundamento=Fundamento.model_json_schema())
    dataset_sha256 = hashlib.sha256((args.datos / f"{args.split}.json").read_bytes()).hexdigest()
    esquemas_wire_sha256 = hashlib.sha256(json.dumps(
        esquemas_activos, sort_keys=True).encode()).hexdigest()
    resumen = dict(modo=args.modo, nivel=args.nivel, split=args.split, concurrencia=args.concurrencia,
                   versiones=await p.recuperador.versiones(), modelo=p.slm.modelo,
                   revision_modelo=p.slm.revision,
                   transporte="API ASGI local con auditoria y simulador" if banco else "analizador directo",
                   contexto_tokens=p.slm.contexto,
                   protocolo=SLM_PROTOCOL_VERSION,
                   dataset_sha256=dataset_sha256,
                   esquemas_wire_sha256=esquemas_wire_sha256,
                   prefill_tokens=int(os.environ.get("PRIVATEWAY_PREFILL_TOKENS", "512")),
                   gpu_memory=float(os.environ.get("PRIVATEWAY_GPU_MEMORY", "0.75")),
                   instrucciones_sha256=hashlib.sha256(json.dumps(
                       prompts_activos, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
                   esquema_sha256=hashlib.sha256(json.dumps(
                       esquemas_activos, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
                   n=len(muestras), errores=sum(bool(s["error"]) for s in muestras),
                   bloqueos=sum(s["accion"] == "bloquear" for s in muestras),
                   transmitidas=sum(s["transmitida"] for s in muestras),
                   deteccion=deteccion, macro=macro_por_categoria(deteccion),
                   deteccion_parcial=deteccion_parcial,
                   macro_parcial=macro_por_categoria(deteccion_parcial),
                   micro=metricas(*(sum(v[i] for v in categorias.values()) for i in range(3))),
                   aciertos_accion=sum(s["accion"] == s["esperada"] and not s["error"] for s in muestras)
                                    if args.nivel == "flujo" else None,
                   matriz_acciones=matriz_acciones if args.nivel == "flujo" else None,
                   controles_limpios=len(controles_limpios) if args.nivel == "flujo" else None,
                   falsos_bloqueos=sum(s["accion"] == "bloquear" for s in controles_limpios)
                                   if args.nivel == "flujo" else None,
                   tasa_falsos_bloqueos=(sum(s["accion"] == "bloquear" for s in controles_limpios) /
                                          len(controles_decididos) if controles_decididos else None)
                                   if args.nivel == "flujo" else None,
                   exposicion=dict(metodo="valor normalizado completo o token/fragmento alfanumerico contiguo de al menos 4 caracteres",
                                   apariciones_expuestas=spans_expuestos,
                                   apariciones_expuestas_exactas=spans_expuestos_exactos,
                                   apariciones_expuestas_parciales=spans_expuestos_parciales,
                                   apariciones_referencia_transmitidas=spans_transmitidos,
                                   tasa=spans_expuestos/spans_transmitidos if spans_transmitidos else None,
                                   tasa_exacta=spans_expuestos_exactos/spans_transmitidos if spans_transmitidos else None,
                                   tasa_parcial=spans_expuestos_parciales/spans_transmitidos if spans_transmitidos else None,
                                   solicitudes_sensibles_transmitidas=len(solicitudes_sensibles),
                                   solicitudes_sensibles_con_exposicion=sum(bool(s["apariciones_expuestas"])
                                                                          for s in solicitudes_sensibles))
                   if args.nivel == "flujo" else None,
                   recall4=sum(c["acierto"] for c in rag)/len(rag) if rag else None,
                   p50_ms=percentil(xs,.5), p95_ms=percentil(xs,.95), p99_ms=percentil(xs,.99),
                   throughput=len(muestras)/duracion, muestras=muestras, recuperacion=rag,
                   limitaciones=["Corpus sintético preliminar; anotación requiere revisión humana.",
                                 "Exposición medida por valores literales; no evalúa reidentificación.",
                                 "Fallo técnico cuenta como omisión en detección, no como bloqueo."])
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    temporal = args.salida.with_name(f".{args.salida.name}.{os.getpid()}.tmp")
    temporal.write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporal, args.salida)
    print(json.dumps({k:resumen[k] for k in ("n","errores","p50_ms","p95_ms","recall4")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--datos", type=Path, default=Path("/pilot/datasets/v1"))
    parser.add_argument("--split", choices=["desarrollo","validacion","reto"], default="desarrollo")
    parser.add_argument("--modo", choices=["regex","slm","hibrido"], default="hibrido")
    parser.add_argument("--nivel", choices=["deteccion","flujo"], default="deteccion")
    parser.add_argument("--concurrencia", type=int, choices=[1,5,10], default=1)
    parser.add_argument("--limite", type=int)
    parser.add_argument("--salida", type=Path, required=True)
    args = parser.parse_args()
    if args.nivel == "flujo" and args.modo != "hibrido":
        parser.error("El flujo completo evalua el gateway hibrido; usar deteccion para las lineas base")
    asyncio.run(evaluar(args))
