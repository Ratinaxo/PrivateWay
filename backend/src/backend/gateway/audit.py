"""Auditoría de prueba: cadena de registros, sin texto de consulta ni respuesta.

No sustituye una bitácora productiva: un administrador con acceso al fichero
podría reescribir y recalcular la cadena si no existe anclaje externo.
"""
from __future__ import annotations

import asyncio
from collections import deque
import hashlib
import json
import os
from pathlib import Path
from typing import Protocol


class AuditoriaNoDisponible(Exception):
    pass


class RegistroAuditoria(Protocol):
    listo: bool
    async def registrar(self, datos: dict[str, str]) -> None: ...


class AuditoriaNoConfigurada:
    listo = False

    async def registrar(self, datos: dict[str, str]) -> None:
        raise AuditoriaNoDisponible("auditoría no configurada")


class AuditoriaArchivo:
    """Únicamente maqueta local, un proceso escritor, fichero 0600."""
    listo = True
    _CLAVES = {"evento", "fase", "alias", "proveedor", "accion", "motivo", "transmision", "fecha_utc", "mensaje_actual", "historial", "usuario", "usuario_id", "vista_disponible", "evento_consultado"}

    def __init__(self, ruta: str | Path) -> None:
        self.ruta = Path(ruta)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self._anterior = "0" * 64
        if self.ruta.exists():
            for linea in self.ruta.read_text(encoding="utf-8").splitlines():
                try:
                    registro = json.loads(linea)
                    if registro["anterior"] != self._anterior:
                        raise ValueError("cadena rota")
                    contenido = json.dumps(
                        {"anterior": registro["anterior"], "evento": registro["evento"]},
                        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                    )
                    digest = hashlib.sha256(contenido.encode()).hexdigest()
                    if registro["hash"] != digest:
                        raise ValueError("hash inválido")
                    self._anterior = digest
                except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                    raise AuditoriaNoDisponible("bitácora local inconsistente") from exc

    async def registrar(self, datos: dict[str, str]) -> None:
        if not set(datos).issubset(self._CLAVES) or not all(isinstance(v, str) for v in datos.values()):
            raise AuditoriaNoDisponible("campos no admitidos en auditoría")
        # No se permite contenido arbitrario (por ejemplo, justificación del SLM).
        if any(len(v) > 120 or any(ch in v for ch in "\r\n") for v in datos.values()):
            raise AuditoriaNoDisponible("valor no admisible en bitácora")
        async with self._lock:
            sobre = {"anterior": self._anterior, "evento": datos}
            serial = json.dumps(sobre, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            digest = hashlib.sha256(serial.encode()).hexdigest()
            salida = json.dumps({**sobre, "hash": digest}, sort_keys=True, ensure_ascii=False)
            try:
                fd = os.open(self.ruta, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
                try:
                    with os.fdopen(fd, "a", encoding="utf-8") as f:
                        f.write(salida + "\n")
                        f.flush()
                        os.fsync(f.fileno())
                except Exception:
                    raise
            except OSError as exc:
                raise AuditoriaNoDisponible("falló el registro previo/operativo") from exc
            self._anterior = digest


    def _listar_verificando(self, limite: int) -> dict:
        """Verifica toda la cadena antes de mostrar los últimos registros.

        No expone el fichero, contenido de chats ni excepciones internas.
        """
        anterior = "0" * 64
        ultimos: deque[dict] = deque(maxlen=limite)
        total = 0
        try:
            if not self.ruta.exists():
                return {"integridad": "verificada", "total": 0, "registros": []}
            with self.ruta.open("r", encoding="utf-8") as archivo:
                for linea in archivo:
                    registro = json.loads(linea)
                    if (not isinstance(registro, dict) or registro.get("anterior") != anterior
                        or not isinstance(registro.get("evento"), dict)):
                        raise ValueError("cadena inválida")
                    evento = registro["evento"]
                    if (not set(evento).issubset(self._CLAVES) or
                        not all(isinstance(v, str) and len(v) <= 120 for v in evento.values())):
                        raise ValueError("evento inválido")
                    contenido = json.dumps(
                        {"anterior": anterior, "evento": evento},
                        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                    )
                    digest = hashlib.sha256(contenido.encode()).hexdigest()
                    if registro.get("hash") != digest:
                        raise ValueError("hash inválido")
                    anterior = digest
                    total += 1
                    # Lista blanca: sin secretos, prompts, respuestas ni tokens.
                    ultimos.append({k: evento[k] for k in
                        ("fecha_utc", "evento", "fase", "alias", "proveedor", "accion", "motivo", "transmision", "mensaje_actual", "historial", "usuario", "usuario_id", "vista_disponible", "evento_consultado")
                        if k in evento})
        except (OSError, UnicodeError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise AuditoriaNoDisponible("bitácora no verificable") from exc
        return {"integridad": "verificada", "total": total, "registros": list(reversed(ultimos))}

    async def listar(self, limite: int = 200) -> dict:
        if not isinstance(limite, int) or limite < 1 or limite > 200:
            raise AuditoriaNoDisponible("límite inválido")
        async with self._lock:
            return await asyncio.to_thread(self._listar_verificando, limite)

    async def existe_evento(self, identificador: str) -> bool:
        """Verificar la cadena completa antes de consultar contenido sensible."""
        async with self._lock:
            await asyncio.to_thread(self._listar_verificando, 1)
            if not self.ruta.exists():
                return False
            def buscar() -> bool:
                with self.ruta.open("r", encoding="utf-8") as archivo:
                    for linea in archivo:
                        registro = json.loads(linea)
                        datos = registro.get("evento", {})
                        if datos.get("evento") == identificador and datos.get("fase") == "preparada":
                            return True
                return False
            return await asyncio.to_thread(buscar)
