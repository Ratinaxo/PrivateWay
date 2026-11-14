"""Genera secretos exclusivos del piloto, sin modificar .env existente."""
from pathlib import Path
import base64
import secrets

root = Path(__file__).resolve().parents[1]
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
    destino.write_text("".join(f"{k}={v}\n" for k, v in valores.items()), encoding="utf-8")
    destino.chmod(0o600)
print("Configuracion del piloto disponible; no se muestran secretos.")
