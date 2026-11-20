"""Crea credenciales locales solo para los servicios SLM y embeddings."""
import argparse
from pathlib import Path
import secrets


VALORES = {
    "PRIVATEWAY_SLM_TOKEN": lambda: secrets.token_urlsafe(32),
    "PRIVATEWAY_EMBEDDINGS_TOKEN": lambda: secrets.token_urlsafe(32),
    "PRIVATEWAY_SLM_MODEL_DIR": lambda: "/models/qwen",
    "PRIVATEWAY_SLM_CONTEXT": lambda: "4096",
    "PRIVATEWAY_GPU_MEMORY": lambda: "0.75",
    "PRIVATEWAY_E5_REVISION": lambda: "pending-download",
}


def configurar(root: Path) -> Path:
    destino = root / ".env.model"
    actuales = {}
    if destino.exists():
        actuales = dict(line.split("=", 1) for line in destino.read_text(encoding="utf-8").splitlines()
                        if "=" in line and not line.lstrip().startswith("#"))
    for nombre, generar in VALORES.items():
        if not actuales.get(nombre):
            actuales[nombre] = generar()
    destino.write_text("".join(f"{nombre}={valor}\n" for nombre, valor in actuales.items()),
                        encoding="utf-8")
    destino.chmod(0o600)
    return destino


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    configurar(args.root)
    print("Configuración local de SLM/embeddings disponible; los secretos no se muestran.")
