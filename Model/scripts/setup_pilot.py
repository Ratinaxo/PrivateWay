"""Genera secretos exclusivos del piloto, sin modificar .env existente."""
from pathlib import Path
import base64
import secrets
import argparse

def configurar(root, slm=None):
    destino = root / ".env.pilot"
    if not destino.exists():
        valores = {
            "PRIVATEWAY_SLM_TOKEN": secrets.token_urlsafe(32),
            "PRIVATEWAY_EMBEDDINGS_TOKEN": secrets.token_urlsafe(32),
            "PRIVATEWAY_GATEWAY_TOKEN": secrets.token_urlsafe(32),
            "PRIVATEWAY_DB_PASSWORD": secrets.token_urlsafe(32),
            "PRIVATEWAY_AUDIT_CONTENT_KEY": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
            "PRIVATEWAY_SLM_CONTEXT": "4096", "PRIVATEWAY_GPU_MEMORY": "0.75",
            "PRIVATEWAY_E5_REVISION": "pending-download",
        }
        destino.write_text("".join(f"{k}={v}\n" for k,v in valores.items()),encoding="utf-8")
        destino.chmod(0o600)
    lines = destino.read_text(encoding="utf-8").splitlines()
    adicionales = {
        "PRIVATEWAY_CONVERSATION_KEY": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
        "GATEWAY_HISTORY_TOKEN": secrets.token_urlsafe(32),
    }
    nuevas = [f"{k}={v}" for k, v in adicionales.items()
              if not any(line.startswith(k + "=") for line in lines)]
    if nuevas:
        destino.write_text("\n".join([*lines, *nuevas]) + "\n", encoding="utf-8")
    if slm is not None:
        carpeta={"3b":"qwen","7b":"qwen7b"}[slm]
        lines=[l for l in destino.read_text(encoding="utf-8").splitlines()
               if not l.startswith("PRIVATEWAY_SLM_FOLDER=")]
        lines.append("PRIVATEWAY_SLM_FOLDER="+carpeta)
        destino.write_text("\n".join(lines)+"\n",encoding="utf-8")


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--slm",choices=["3b","7b"])
    args=parser.parse_args()
    configurar(Path(__file__).resolve().parents[2],args.slm)
    print("Configuracion del piloto disponible; no se muestran secretos.")
