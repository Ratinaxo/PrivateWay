"""Ejecuta el banco del piloto y captura recursos sin imprimir secretos."""
import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ["docker", "compose", "--env-file", ".env.pilot", "-f", "compose.pilot.yaml"]


def main():
    sys.stdout.reconfigure(errors="backslashreplace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-only", action="store_true")
    parser.add_argument("--limite", type=int)
    parser.add_argument("--split", choices=["desarrollo", "validacion"], default="desarrollo")
    parser.add_argument("--repeticiones", type=int, default=1)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if args.repeticiones < 1 or (args.limite is not None and args.limite < 1):
        parser.error("Los conteos deben ser positivos")
    if args.split == "validacion" and (args.limite is not None or args.smoke_only):
        parser.error("La validación ejecuta el conjunto reservado completo")
    sufijo = "dev" if args.split == "desarrollo" else "val"
    os.chdir(ROOT)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    git_limpio = not subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()
    if args.split == "validacion" and not git_limpio:
        parser.error("La validación requiere un commit limpio que identifique la configuración congelada")
    salida = args.output_dir.resolve() if args.output_dir else ROOT / "pilot/results" / datetime.datetime.now(ZoneInfo("America/Santiago")).strftime("%Y%m%d-%H%M%S")
    base = (ROOT / "pilot/results").resolve()
    if not salida.is_relative_to(base):
        parser.error("output-dir debe estar dentro de pilot/results")
    if salida.exists() and any(salida.iterdir()):
        parser.error("Usar una carpeta vacia para no mezclar ejecuciones")
    salida.mkdir(parents=True,exist_ok=True)
    metadata = dict(fecha_chile=datetime.datetime.now(ZoneInfo("America/Santiago")).date().isoformat(),
                    limite=args.limite, estado="en_curso", split=args.split, repeticiones=args.repeticiones,
                    revision_codigo=revision, arbol_limpio=git_limpio)
    (salida/"run.json").write_text(json.dumps(metadata,indent=2),encoding="utf-8")
    env = dict(l.split("=",1) for l in (ROOT / ".env.pilot").read_text().splitlines() if "=" in l and not l.startswith("#"))
    # Esperar únicamente disponibilidad; nunca reintentar solicitudes de usuario.
    deadline = time.monotonic() + 180
    while True:
        try:
            with urllib.request.urlopen("http://127.0.0.1:8082/ready", timeout=20) as r:
                if json.load(r)["ready"]:
                    break
        except (urllib.error.URLError, TimeoutError):
            pass
        if time.monotonic() > deadline:
            metadata.update(estado="no_disponible",aprobada=False)
            (salida/"run.json").write_text(json.dumps(metadata,indent=2),encoding="utf-8")
            raise RuntimeError("Gateway no listo después de 180 segundos")
        time.sleep(3)
    casos = [("Hola mundo", 200,"permitir"), ("La persona solicitante se llama Ana Torres.",200,"seudonimizar"),
             ("Ana Torres tiene diabetes.",403,"bloquear")]
    smoke = []
    for texto, esperado, accion_esperada in casos:
        req = urllib.request.Request("http://127.0.0.1:8082/api/v1/secure-chat",
            data=json.dumps({"model":"pw-simulado", "messages":[{"role":"user","content":texto}]}).encode(),
            headers={"Content-Type":"application/json","Authorization":"Bearer " + env["PRIVATEWAY_GATEWAY_TOKEN"]})
        t = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=150) as r:
                body, estado = json.load(r), r.status
        except urllib.error.HTTPError as e:
            body, estado = json.load(e), e.code
        smoke.append(dict(esperado=esperado, estado=estado, tiempo_ms=(time.perf_counter()-t)*1000,
                          accion_esperada=accion_esperada,
                          accion=body.get("decision",{}).get("accion"),
                          codigo=body.get("error",{}).get("code")))
        (salida / "smoke.json").write_text(json.dumps(smoke, indent=2), encoding="utf-8")
        print(json.dumps({"caso_smoke":len(smoke), **smoke[-1]}), flush=True)
    (salida / "smoke.json").write_text(json.dumps(smoke, indent=2), encoding="utf-8")
    print(json.dumps({"smoke":smoke}), flush=True)
    if args.smoke_only:
        from report_pilot import smoke_correcto
        metadata.update(estado="smoke_completo",aprobada=all(smoke_correcto(s) for s in smoke))
        (salida/"run.json").write_text(json.dumps(metadata,indent=2),encoding="utf-8")
        if not metadata["aprobada"]:
            raise SystemExit(1)
        return
    stop = threading.Event()
    def recursos():
        with (salida / "recursos.jsonl").open("a", encoding="utf-8") as f:
            while not stop.is_set():
                muestra = {"utc":datetime.datetime.now(datetime.timezone.utc).isoformat()}
                for nombre, comando in [
                    ("docker",["docker","stats","--no-stream","--format","{{json .}}"]),
                    ("gpu",["nvidia-smi","--query-gpu=memory.used,utilization.gpu","--format=csv,noheader,nounits"])]:
                    try:
                        r = subprocess.run(comando, capture_output=True, text=True, timeout=20)
                        muestra[nombre] = r.stdout.strip()
                    except Exception:
                        muestra[nombre] = None
                f.write(json.dumps(muestra)+"\n")
                f.flush()
                stop.wait(10)
    th = threading.Thread(target=recursos, daemon=True)
    th.start()
    try:
        for repeticion in range(1, args.repeticiones + 1):
            destino = salida if args.repeticiones == 1 else salida / f"repeticion-{repeticion}"
            for nivel,modo in [("deteccion",m) for m in ("regex","slm","hibrido")] + [("flujo","hibrido")]:
                for n in (1,5,10):
                    comando = COMPOSE + ["exec","-T","backend","python","-m","backend.gateway.evaluate",
                        "--modo",modo,"--nivel",nivel,"--split",args.split,"--concurrencia",str(n),
                        "--salida",f'/pilot/results/{destino.relative_to(base).as_posix()}/{nivel}-{modo}-{sufijo}-c{n}.json']
                    print(f"Evaluando {nivel}/{modo}, concurrencia {n}, repetición {repeticion}", flush=True)
                    if args.limite:
                        comando += ["--limite", str(args.limite)]
                    subprocess.run(comando, check=True)
    finally:
        stop.set()
        th.join(timeout=25)
    versiones = subprocess.run(COMPOSE+["images","--format","json"],capture_output=True,text=True,check=True)
    (salida / "imagenes.json").write_text(versiones.stdout,encoding="utf-8")
    from report_pilot import smoke_correcto
    flujos = [json.loads(p.read_text(encoding="utf-8")) for p in salida.rglob(f"flujo-*-{sufijo}-c*.json")]
    metadata.update(estado="completo",aprobada=all(smoke_correcto(s) for s in smoke) and all(
        f["errores"] == 0 and f["aciertos_accion"] == f["n"]
        and not any(s["apariciones_expuestas"] or s.get("apariciones_parciales")
                    for s in f["muestras"]) for f in flujos))
    (salida/"run.json").write_text(json.dumps(metadata,indent=2),encoding="utf-8")
    print(f"Evaluación de {args.split} terminada.", flush=True)
    print(f"Resultados: {salida}",flush=True)
    if not metadata["aprobada"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
