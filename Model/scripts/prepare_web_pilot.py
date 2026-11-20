"""Create local-only credentials for connecting the web UI to the pilot gateway."""

from __future__ import annotations

import base64
import os
import secrets
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / ".env.web-pilot"


def main() -> None:
    if OUTPUT.is_symlink():
        raise RuntimeError(".env.web-pilot no puede ser un enlace simbólico")
    if OUTPUT.exists():
        if not OUTPUT.is_file():
            raise RuntimeError(".env.web-pilot debe ser un archivo regular")
        os.chmod(OUTPUT, 0o600)
        print("Credenciales E2E existentes conservadas en .env.web-pilot (permisos 0600).")
        return

    values = {
        "PRIVATEWAY_E2E_GATEWAY_TOKEN": secrets.token_urlsafe(32),
        "PRIVATEWAY_E2E_HISTORY_TOKEN": secrets.token_urlsafe(32),
        "PRIVATEWAY_E2E_AUDIT_READ_TOKEN": secrets.token_urlsafe(32),
        "PRIVATEWAY_E2E_CONVERSATION_KEY": base64.urlsafe_b64encode(os.urandom(32)).decode("ascii"),
    }
    contents = "".join(f"{name}={value}\n" for name, value in values.items())
    fd, temp_name = tempfile.mkstemp(prefix=".env.web-pilot.", dir=ROOT, text=True)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(contents)
        os.replace(temp_name, OUTPUT)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    print("Credenciales E2E locales creadas en .env.web-pilot (permisos 0600).")


if __name__ == "__main__":
    main()
