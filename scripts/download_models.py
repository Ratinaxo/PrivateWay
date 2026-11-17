"""Preparación online; revisiones inmutables y modelos locales durante operación."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.request
import argparse

ROOT = Path(__file__).resolve().parents[1]
MODELS = [("Qwen/Qwen2.5-3B-Instruct-AWQ", "qwen", "qwen-research"),
          ("intfloat/multilingual-e5-large", "e5", "mit")]


def obtener(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "PrivateWay-research-pilot/1.0"}), timeout=120)


def descargar(repo, revision, nombre, destino):
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists():
        return
    for intento in range(3):
        try:
            with obtener(f"https://huggingface.co/{repo}/resolve/{revision}/{nombre}") as r:
                temp = destino.with_suffix(destino.suffix + ".part")
                with temp.open("wb") as f:
                    while chunk := r.read(1024 * 1024):
                        f.write(chunk)
                temp.replace(destino)
            print(f"Descargado {repo}/{nombre}", flush=True)
            return
        except Exception:
            if intento == 2:
                raise
            time.sleep(2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slm",choices=["3b","7b"],default="3b")
    args = parser.parse_args()
    lock = ROOT / "pilot/models.lock.json"
    previo = json.loads(lock.read_text()) if lock.exists() else []
    manifiesto = {m["carpeta"]:m for m in previo}
    modelos = list(MODELS)
    if args.slm == "7b":
        modelos[0] = ("Qwen/Qwen2.5-7B-Instruct-AWQ","qwen7b","apache-2.0")
    for repo, carpeta, licencia in modelos:
        revision = next((m["revision"] for m in previo if m["repo"] == repo), "main")
        with obtener(f"https://huggingface.co/api/models/{repo}/revision/{revision}") as r:
            meta = json.load(r)
        revision = meta["sha"]
        nombres = [s["rfilename"] for s in meta["siblings"]
                   if s["rfilename"].endswith((".safetensors", ".json", ".txt", ".model", ".md"))
                   and not s["rfilename"].startswith(("onnx/", "openvino/"))]
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(lambda n: descargar(repo, revision, n, ROOT / "pilot/models" / carpeta / n), nombres))
        archivos = {}
        for n in nombres:
            with (ROOT / "pilot/models" / carpeta / n).open("rb") as f:
                archivos[n] = hashlib.file_digest(f, "sha256").hexdigest()
        manifiesto[carpeta] = dict(repo=repo, carpeta=carpeta, revision=revision,
                               tokenizer_revision=revision, licencia=licencia, sha256=archivos)
        lock.parent.mkdir(exist_ok=True)
        lock.write_text(json.dumps(list(manifiesto.values()), indent=2), encoding="utf-8")
    env = ROOT / ".env.pilot"
    revision = manifiesto["e5"]["revision"]
    lines = env.read_text().splitlines()
    env.write_text("\n".join(f"PRIVATEWAY_E5_REVISION={revision}" if l.startswith("PRIVATEWAY_E5_REVISION=") else l
                              for l in lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
