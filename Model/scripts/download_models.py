"""Preparación online; revisiones inmutables y modelos locales durante operación."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
MODELS = [("Qwen/Qwen2.5-3B-Instruct-AWQ", "qwen", "qwen-research"),
          ("intfloat/multilingual-e5-large", "e5", "mit")]


def obtener(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "PrivateWay/1.0"}), timeout=120)


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
    manifiesto = []
    lock = ROOT / "Model/models.lock.json"
    previo = json.loads(lock.read_text()) if lock.exists() else []
    for repo, carpeta, licencia in MODELS:
        revision = next((m["revision"] for m in previo if m["repo"] == repo), "main")
        with obtener(f"https://huggingface.co/api/models/{repo}/revision/{revision}") as r:
            meta = json.load(r)
        revision = meta["sha"]
        nombres = [s["rfilename"] for s in meta["siblings"]
                   if (s["rfilename"].endswith((".safetensors", ".json", ".txt", ".model", ".md"))
                       )
                   and not s["rfilename"].startswith(("onnx/", "openvino/"))]
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(lambda n: descargar(repo, revision, n, ROOT / "Model/models" / carpeta / n), nombres))
        archivos = {}
        for n in nombres:
            with (ROOT / "Model/models" / carpeta / n).open("rb") as f:
                archivos[n] = hashlib.file_digest(f, "sha256").hexdigest()
        manifiesto.append(dict(repo=repo, carpeta=carpeta, revision=revision,
                               tokenizer_revision=revision, licencia=licencia, sha256=archivos))
    lock.parent.mkdir(exist_ok=True)
    temporal_lock = lock.with_name(lock.name + ".tmp")
    temporal_lock.write_text(json.dumps(manifiesto, indent=2), encoding="utf-8")
    temporal_lock.replace(lock)
    env = ROOT / ".env.model"
    if not env.exists():
        raise FileNotFoundError("Ejecuta primero Model/scripts/setup_model_env.py")
    revision = next(m["revision"] for m in manifiesto if m["carpeta"] == "e5")
    lines = env.read_text().splitlines()
    actualizados = {"PRIVATEWAY_E5_REVISION": revision}
    for key, value in actualizados.items():
        if not any(line.startswith(key + "=") for line in lines):
            lines.append(f"{key}={value}")
        else:
            lines = [f"{key}={value}" if line.startswith(key + "=") else line for line in lines]
    env.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
