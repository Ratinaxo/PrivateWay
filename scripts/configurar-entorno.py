#!/usr/bin/env python3
"""Configura una sola vez los secretos locales de PrivateWay.

Uso (desde la raíz del repositorio):
    python3 scripts/configurar-entorno.py
    python3 scripts/configurar-entorno.py --check

Conserva todos los valores no vacíos. No rota claves, no modifica Docker,
Keycloak, PostgreSQL ni los volúmenes. Nunca imprime secretos.
"""
from __future__ import annotations

import argparse
import json
import base64
import os
from pathlib import Path
import re
import secrets
import stat
import sys


ROOT = Path(__file__).resolve().parent.parent
ASSIGNMENT = re.compile(
    r"^(?P<prefix>\s*(?:export\s+)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*)(?P<value>.*)$"
)


def fernet_key() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")


# Orden estable: la misma lógica sustituye los configuradores anteriores.
SECRET_GENERATORS = {
    "PRIVATEWAY_GATEWAY_TOKEN": lambda: secrets.token_urlsafe(48),
    "PRIVATEWAY_AUDIT_READ_TOKEN": lambda: secrets.token_urlsafe(48),
    "PRIVATEWAY_HISTORY_TOKEN": lambda: secrets.token_urlsafe(48),
    "PRIVATEWAY_DB_PASSWORD": lambda: secrets.token_urlsafe(36),
    "PRIVATEWAY_CONVERSATION_KEY": fernet_key,
    "PRIVATEWAY_AUDIT_CONTENT_KEY": fernet_key,
    "NEXTAUTH_SECRET": lambda: secrets.token_hex(32),
    "PRIVATEWAY_OIDC_CLIENT_SECRET": lambda: secrets.token_hex(32),
    "PRIVATEWAY_KEYCLOAK_ADMIN_CLIENT_SECRET": lambda: secrets.token_hex(32),
    "KEYCLOAK_DB_PASSWORD": lambda: secrets.token_hex(32),
    "KEYCLOAK_BOOTSTRAP_ADMIN_PASSWORD": lambda: secrets.token_hex(32),
    "PRIVATEWAY_FIRST_ADMIN_PASSWORD": lambda: secrets.token_hex(32),
}

DEFAULTS = {
    "KEYCLOAK_BOOTSTRAP_ADMIN_USERNAME": "kc-bootstrap",
    "PRIVATEWAY_FIRST_ADMIN_USERNAME": "pwadmin",
    "GATEWAY_ROUTES_JSON": '{"pw-simulado":{"proveedor":"simulado","modelo_externo":"modelo-demo"}}',
    "GATEWAY_PROVIDERS_JSON": '{"simulado":{"tipo":"simulado"}}',
}
MANAGED = {**SECRET_GENERATORS, **DEFAULTS}
FERNET_NAMES = {"PRIVATEWAY_CONVERSATION_KEY", "PRIVATEWAY_AUDIT_CONTENT_KEY"}


def unpack_value(raw: str) -> str:
    """Inspección sin expandir variables ni ejecutar código ni un shell."""
    value = raw.strip()
    if value.startswith("#"):
        return ""
    if len(value) >= 2 and value[0] in ("'", '"') and value[-1] == value[0]:
        value = value[1:-1]
    return value


def empty_value(raw: str) -> bool:
    value = raw.strip()
    # Ejemplos: VAR=, VAR='', VAR="", VAR= # rellenar después
    if not value or value.startswith("#") or value in ('""', "''"):
        return True
    return False


def parse_lines(content: str) -> tuple[list[str], dict[str, tuple[int, re.Match[str]]]]:
    lines = content.splitlines(keepends=True)
    positions: dict[str, tuple[int, re.Match[str]]] = {}
    for i, line in enumerate(lines):
        match = ASSIGNMENT.match(line.rstrip("\r\n"))
        if not match:
            continue
        key = match.group("name")
        if key in positions:
            # Incluso duplicados fuera de los secretos pueden causar sustituciones inesperadas.
            raise ValueError(f"Variable duplicada en .env: {key}")
        positions[key] = (i, match)
    return lines, positions


def generate_updates(content: str) -> tuple[str, list[str]]:
    lines, positions = parse_lines(content)
    changed = []
    newline = "\r\n" if "\r\n" in content else "\n"
    if lines and not lines[-1].endswith(("\n", "\r")):
        lines[-1] += newline

    for key, supplier in MANAGED.items():
        if key in positions:
            i, m = positions[key]
            if empty_value(m.group("value")):
                value = supplier() if callable(supplier) else supplier
                original = lines[i]
                ending = "\r\n" if original.endswith("\r\n") else "\n" if original.endswith("\n") else ""
                lines[i] = m.group("prefix") + value + ending
                changed.append(key)
        else:
            if key == "PRIVATEWAY_GATEWAY_TOKEN":
                lines.append("# Secretos generados por scripts/configurar-entorno.py" + newline)
            value = supplier() if callable(supplier) else supplier
            lines.append(key + "=" + value + newline)
            changed.append(key)

    return "".join(lines), changed


def validate_secrets(content: str) -> list[str]:
    _, positions = parse_lines(content)
    warnings = []
    seen: dict[str, str] = {}
    for key in SECRET_GENERATORS:
        if key not in positions or empty_value(positions[key][1].group("value")):
            warnings.append(f"{key}: falta o está vacío")
            continue
        value = unpack_value(positions[key][1].group("value"))
        if key in FERNET_NAMES:
            try:
                decoded = base64.urlsafe_b64decode(value.encode("ascii"))
                if len(decoded) != 32 or base64.urlsafe_b64encode(decoded).decode("ascii") != value:
                    raise ValueError("longitud o alfabeto incorrecto")
            except (ValueError, UnicodeEncodeError) as exc:
                warnings.append(f"{key}: formato de clave Fernet inválido ({type(exc).__name__})")
        elif len(value) < 24:
            warnings.append(f"{key}: longitud inferior a 24 caracteres")
        if value.lower() in {"change-me", "changeme", "placeholder", "secret", "password", "tu_clave_aqui"}:
            warnings.append(f"{key}: parece un valor de ejemplo")
        if value in seen:
            warnings.append(f"{key}: comparte valor con {seen[value]}; usa secretos distintos")
        else:
            seen[value] = key
    for key in DEFAULTS:
        if key not in positions or empty_value(positions[key][1].group("value")):
            warnings.append(f"{key}: falta o está vacío")
        elif key.endswith("_JSON"):
            try:
                obj = json.loads(unpack_value(positions[key][1].group("value")))
                if not isinstance(obj, dict):
                    warnings.append(f"{key}: debe ser un objeto JSON")
            except json.JSONDecodeError:
                warnings.append(f"{key}: JSON inválido")
    return warnings


def service_block(text: str, service: str) -> str:
    # Inspección orientativa; no sustituye `docker compose config`.
    match = re.search(rf"(?m)^  {re.escape(service)}:\s*(?:#.*)?$", text)
    if not match:
        return ""
    rest = text[match.end():]
    end = re.search(r"(?m)^(?:  [A-Za-z_][A-Za-z0-9_-]*:\s*(?:#.*)?$|[A-Za-z_][A-Za-z0-9_-]*:\s*(?:#.*)?$)", rest)
    return rest[:end.start()] if end else rest


def check_compose(root: Path) -> list[str]:
    compose_path = root / "compose.yaml"
    if not compose_path.is_file():
        return ["No encontré compose.yaml en la raíz; no puedo comprobar su configuración"]
    compose = compose_path.read_text(encoding="utf-8")
    blocks = {service: service_block(compose, service) for service in ("frontend", "backend", "postgres")}
    required = {
        "frontend": ("GATEWAY_HISTORY_TOKEN", "PRIVATEWAY_HISTORY_TOKEN", "GATEWAY_AUDIT_READ_TOKEN"),
        "backend": (
            "GATEWAY_HISTORY_TOKEN", "PRIVATEWAY_HISTORY_TOKEN", "PRIVATEWAY_DB_HOST",
            "PRIVATEWAY_DB_PASSWORD", "PRIVATEWAY_CONVERSATION_KEY", "GATEWAY_AUDIT_CONTENT_KEY",
        ),
        "postgres": ("PRIVATEWAY_DB_PASSWORD", "POSTGRES_PASSWORD"),
    }
    warnings = []
    for service, keys in required.items():
        block = blocks[service]
        if not block:
            warnings.append(f"compose.yaml: falta el servicio {service}")
            continue
        for key in keys:
            if key not in block:
                warnings.append(f"compose.yaml: {service} no parece incluir {key}")
    if "postgres_data:" not in compose:
        warnings.append("compose.yaml: no aparece el volumen postgres_data")
    return warnings


def safe_write(env_path: Path, text: str) -> None:
    if env_path.is_symlink():
        raise ValueError(".env es un enlace simbólico; se rechaza para proteger secretos")
    temp = env_path.with_name(f".env.{secrets.token_hex(10)}.tmp")
    try:
        fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, env_path)
        os.chmod(env_path, stat.S_IRUSR | stat.S_IWUSR)
    finally:
        temp.unlink(missing_ok=True)


def run() -> int:
    parser = argparse.ArgumentParser(description="Rellena los secretos faltantes en .env sin rotar los existentes")
    parser.add_argument("--check", action="store_true", help="solo verifica .env y compose.yaml; no cambia archivos")
    parser.add_argument("--project-root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = args.project_root.resolve()
    env_path = root / ".env"
    template = root / ".env.example"
    if not template.is_file():
        template = root / ".env-example"
    if env_path.is_symlink():
        print("ERROR: .env es un enlace simbólico; operación cancelada", file=sys.stderr)
        return 2
    if not env_path.exists() and not template.is_file():
        print("ERROR: no existe .env ni .env.example en la raíz del proyecto", file=sys.stderr)
        return 2
    if args.check and not env_path.exists():
        print("FALTA .env. Ejecuta python3 scripts/configurar-entorno.py")
        return 1
    before = env_path.read_text(encoding="utf-8") if env_path.exists() else template.read_text(encoding="utf-8")
    try:
        output, changed = generate_updates(before) if not args.check else (before, [])
        issues = validate_secrets(output)
    except (ValueError, UnicodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if not args.check:
        if changed or not env_path.exists():
            safe_write(env_path, output)
        elif stat.S_IMODE(env_path.stat().st_mode) != 0o600:
            os.chmod(env_path, 0o600)
        print(".env listo. Variables añadidas o rellenadas:", ", ".join(changed) if changed else "ninguno")
        print("Los valores existentes se conservaron. Ningún secreto se muestra por pantalla.")
    else:
        print("Comprobación de .env:", "correcta" if not issues else "con advertencias")
    compose_issues = check_compose(root)
    for issue in issues:
        print("ADVERTENCIA (.env):", issue)
    for issue in compose_issues:
        print("ADVERTENCIA (Compose):", issue)
    if compose_issues:
        print("El script NO instala servicios ni modifica compose.yaml. Aplica el Compose con postgres")
        print("y las variables de historial/auditoría antes de iniciar Docker.")
    print("Para verificar Compose: docker compose -f compose.yaml -f compose.dev.yaml config --quiet")
    print("Para aplicar variables a contenedores existentes: docker compose -f compose.yaml -f compose.dev.yaml up -d --no-build --force-recreate backend frontend")
    print("No borres volúmenes ni cambies claves de Keycloak/PostgreSQL ya inicializadas.")
    return 1 if args.check and (issues or compose_issues) else 0


if __name__ == "__main__":
    raise SystemExit(run())
