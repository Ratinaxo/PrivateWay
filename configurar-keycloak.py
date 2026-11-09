#!/usr/bin/env python3
"""Añade solo secretos de laboratorio ausentes al .env existente; no sobrescribe valores."""
from __future__ import annotations

import re
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[0]
print(ROOT)
env = ROOT / ".env"
if not env.exists():
    raise SystemExit("No existe .env en la raíz. Copia .env.example a .env y configura primero el gateway.")

text = env.read_text(encoding="utf-8")
keys = dict(re.findall(r"^([A-Za-z_][A-Za-z_0-9]*)=(.*)$", text, flags=re.MULTILINE))
required = [
    "NEXTAUTH_SECRET", "PRIVATEWAY_OIDC_CLIENT_SECRET", "PRIVATEWAY_KEYCLOAK_ADMIN_CLIENT_SECRET",
    "KEYCLOAK_DB_PASSWORD", "KEYCLOAK_BOOTSTRAP_ADMIN_PASSWORD", "PRIVATEWAY_FIRST_ADMIN_PASSWORD",
]
newlines: list[str] = []
for name in required:
    value = keys.get(name, "").strip()
    if not value:
        secret = secrets.token_hex(32)
        if name in keys:
            # Sustituir únicamente la asignación vacía (sin mostrar valores).
            text = re.sub(rf"^{re.escape(name)}=\s*$", f"{name}={secret}", text, count=1, flags=re.MULTILINE)
        else:
            newlines.append(f"{name}={secret}")
        keys[name] = secret
for name, value in [("KEYCLOAK_BOOTSTRAP_ADMIN_USERNAME", "kc-bootstrap"),
                    ("PRIVATEWAY_FIRST_ADMIN_USERNAME", "pwadmin")]:
    if name not in keys:
        newlines.append(f"{name}={value}")
        keys[name] = value
if newlines:
    text = text.rstrip("\n") + "\n\n# OIDC local (generado en este equipo)\n" + "\n".join(newlines) + "\n"
if not text.endswith("\n"):
    text += "\n"
env.write_text(text, encoding="utf-8")
env.chmod(0o600)
print("Configuración local actualizada en .env (permisos 600).")
print(f"Usuario inicial de PrivateWay: {keys['PRIVATEWAY_FIRST_ADMIN_USERNAME']}")
print("La contraseña inicial temporal está en PRIVATEWAY_FIRST_ADMIN_PASSWORD dentro del .env.")
print("No se imprimieron secretos. No subas .env a Git.")
