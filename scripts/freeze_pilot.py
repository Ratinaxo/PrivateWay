"""Registra la configuración aprobada en desarrollo antes de abrir la reserva."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from report_pilot import ROOT, cargar_resultados


def sha256(archivo: Path) -> str:
    return hashlib.sha256(archivo.read_bytes()).hexdigest()


def congelar(desarrollo: Path, salida: Path) -> None:
    corrida = json.loads((desarrollo / "run.json").read_text(encoding="utf-8"))
    if corrida.get("estado") != "completo" or corrida.get("aprobada") is not True:
        raise ValueError("La corrida de desarrollo debe estar completa y aprobada")
    resultados = cargar_resultados(desarrollo)
    if any(r["split"] != "desarrollo" or r["n"] != 60 for r in resultados):
        raise ValueError("Se requieren las doce configuraciones con 60 casos de desarrollo")
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip():
        raise ValueError("Se requiere un árbol de trabajo limpio")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    base = resultados[0]
    datos = ROOT / "pilot" / "datasets"
    if sha256(datos / "desarrollo.json") != base["dataset_sha256"]:
        raise ValueError("El dataset de desarrollo cambió después de la corrida")
    manifiesto = {
        "commit": revision,
        "desarrollo": desarrollo.relative_to(ROOT).as_posix(),
        "resultado_sha256": {p.name: sha256(p) for p in sorted(desarrollo.glob("*-dev-c*.json"))},
        "datasets_sha256": {p.name: sha256(p) for p in (
            datos / "desarrollo.json", datos / "validacion.json", datos / "recuperacion.json"
        )},
        "modelo": base["repo_modelo"],
        "revision_modelo": base["revision_modelo"],
        "protocolo": base["protocolo"],
        "instrucciones_sha256": base["instrucciones_sha256"],
        "esquemas_wire_sha256": base["esquemas_wire_sha256"],
        "contexto_tokens": base["contexto_tokens"],
        "prefill_tokens": base["prefill_tokens"],
        "gpu_memory": base["gpu_memory"],
        "versiones_rag": base["versiones"],
        "modelos_lock_sha256": sha256(ROOT / "pilot" / "models.lock.json"),
        "compose_sha256": sha256(ROOT / "compose.pilot.yaml"),
    }
    with salida.open("x", encoding="utf-8") as archivo:
        json.dump(manifiesto, archivo, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--desarrollo", type=Path, required=True)
    parser.add_argument("--salida", type=Path, required=True)
    args = parser.parse_args()
    congelar(args.desarrollo.resolve(), args.salida.resolve())
