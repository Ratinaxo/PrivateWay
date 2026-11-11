"""Previsualizaciones sensibles de auditoría, cifradas y separadas del JSONL.

Conserva hasta 30 días de contenido cuando se configura la clave. Los registros
previos a habilitar este almacén no permiten reconstruir los mensajes originales.
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
import re
import secrets

from cryptography.fernet import Fernet, InvalidToken
from .audit import AuditoriaNoDisponible

_ID = re.compile(r"^evt_[0-9a-f]{32}$")


class ContenidoAuditoria:
    def __init__(self, carpeta: str | Path, clave: str, dias: int = 30) -> None:
        try:
            self.cifrador = Fernet(clave.encode("ascii"))
        except (ValueError, TypeError) as exc:
            raise AuditoriaNoDisponible("clave de previsualización inválida") from exc
        self.carpeta = Path(carpeta)
        self.carpeta.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.carpeta, 0o700)
        self.dias = dias
        self._lock = asyncio.Lock()

    def _ruta(self, evento: str) -> Path:
        if not _ID.fullmatch(evento):
            raise AuditoriaNoDisponible("evento no válido")
        return self.carpeta / f"{evento}.enc"

    def _purgar(self) -> None:
        limite = datetime.now(timezone.utc) - timedelta(days=self.dias)
        for ruta in self.carpeta.glob("evt_*.enc"):
            try:
                if datetime.fromtimestamp(ruta.stat().st_mtime, timezone.utc) < limite:
                    ruta.unlink()
            except OSError:
                continue

    def _guardar(self, evento: str, contenido: dict) -> None:
        ruta = self._ruta(evento)
        datos = json.dumps(contenido, ensure_ascii=False, separators=(",", ":")).encode()
        if len(datos) > 1_500_000:
            raise AuditoriaNoDisponible("previsualización demasiado grande")
        cifrado = self.cifrador.encrypt(datos)
        temporal = ruta.with_name(f".{evento}.{secrets.token_hex(8)}.tmp")
        try:
            fd = os.open(temporal, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(cifrado)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporal, ruta)
            self._purgar()
        except OSError as exc:
            raise AuditoriaNoDisponible("almacén de contenido inaccesible") from exc
        finally:
            temporal.unlink(missing_ok=True)

    async def guardar(self, evento: str, contenido: dict) -> None:
        async with self._lock:
            await asyncio.to_thread(self._guardar, evento, contenido)

    def _leer(self, evento: str) -> dict | None:
        ruta = self._ruta(evento)
        if not ruta.is_file():
            return None
        try:
            if datetime.fromtimestamp(ruta.stat().st_mtime, timezone.utc) < datetime.now(timezone.utc) - timedelta(days=self.dias):
                return None
            if ruta.stat().st_size > 2_200_000:
                raise AuditoriaNoDisponible("previsualización inválida")
            contenido = json.loads(self.cifrador.decrypt(ruta.read_bytes()))
            if not isinstance(contenido, dict):
                raise ValueError("formato")
            return contenido
        except (OSError, InvalidToken, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise AuditoriaNoDisponible("previsualización no verificable") from exc

    async def leer(self, evento: str) -> dict | None:
        async with self._lock:
            return await asyncio.to_thread(self._leer, evento)
