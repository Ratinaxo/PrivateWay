"""Ejecuta solo desarrollo y captura recursos del stack; no imprime secretos."""
import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess
import threading
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DOCKER = (["sudo", "-n", "docker"] if os.environ.get("PRIVATEWAY_DOCKER_SUDO") == "1"
          else ["docker"])
COMPOSE = DOCKER + ["compose", "--env-file", ".env.pilot", "-f", "compose.pilot.yaml"]


def escribir_atomico(ruta, contenido):
    temporal = ruta.with_name(f".{ruta.name}.{os.getpid()}.tmp")
    temporal.write_text(contenido, encoding="utf-8")
    os.replace(temporal, ruta)


def renovar_sudo():
    if os.environ.get("PRIVATEWAY_DOCKER_SUDO") == "1":
        subprocess.run(["sudo", "-v"], check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-only", action="store_true")
    parser.add_argument("--limite", type=int)
    parser.add_argument("--dataset", choices=["piloto", "v2"], default="piloto",
                        help="piloto: benchmark inicial; v2: benchmark ampliado de desarrollo")
    args = parser.parse_args()
    os.chdir(ROOT)
    if not args.smoke_only:
        # Solicita/renueva la contraseña; los comandos Docker usan sudo -n.
        renovar_sudo()
    salida = ROOT / "pilot/results"
    salida.mkdir(exist_ok=True)
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
        escribir_atomico(salida / "smoke.json", json.dumps(smoke, indent=2))
        print(json.dumps({"caso_smoke":len(smoke), **smoke[-1]}), flush=True)
    escribir_atomico(salida / "smoke.json", json.dumps(smoke, indent=2))
    print(json.dumps({"smoke":smoke}), flush=True)
    fallos_smoke = [s for s in smoke if s["estado"] != s["esperado"] or
                    (s["accion_esperada"] != "bloquear" and s["accion"] != s["accion_esperada"])]
    if fallos_smoke:
        raise SystemExit(f"Smoke test falló en {len(fallos_smoke)} de {len(smoke)} casos; se detiene la batería.")
    if args.smoke_only:
        return
    stop = threading.Event()
    marca = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{os.getpid()}"
    ruta_recursos = salida / f"recursos-{marca}.jsonl"
    def recursos():
        with ruta_recursos.open("x", encoding="utf-8") as f:
            while not stop.is_set():
                muestra = {"utc":datetime.datetime.now(datetime.timezone.utc).isoformat()}
                for nombre, comando in [
                    ("docker",DOCKER+["stats","--no-stream","--format","{{json .}}"]),
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
        for nivel,modo in [("deteccion",m) for m in ("regex","slm","hibrido")] + [("flujo","hibrido")]:
            for n in (1,5,10):
                prefijo = "v2-" if args.dataset == "v2" else ""
                datos = "/pilot/datasets/v2" if args.dataset == "v2" else "/pilot/datasets"
                comando = COMPOSE + ["exec","-T","backend","python","-m","backend.gateway.evaluate",
                    "--datos", datos,
                    "--modo",modo,"--nivel",nivel,"--split","desarrollo","--concurrencia",str(n),
                    "--salida",f"/pilot/results/{prefijo}{nivel}-{modo}-dev-c{n}.json"]
                print(f"Evaluando {nivel}/{modo}, concurrencia {n}", flush=True)
                if args.limite:
                    comando += ["--limite", str(args.limite)]
                renovar_sudo()
                subprocess.run(comando, check=True)
    finally:
        stop.set()
        th.join(timeout=25)
    renovar_sudo()
    versiones = subprocess.run(COMPOSE+["images","--format","json"],capture_output=True,text=True,check=True)
    escribir_atomico(salida / "imagenes.json", versiones.stdout)
    subprocess.run([os.environ.get("PYTHON", "python"), "scripts/export_experiments.py"],
                   cwd=ROOT, check=True)
    print("Evaluaciones de desarrollo terminadas; validacion reservada sin ejecutar.", flush=True)


if __name__ == "__main__":
    main()
