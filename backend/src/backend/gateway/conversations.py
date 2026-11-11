"""Historial por sujeto OIDC, cifrado antes de almacenarlo en PostgreSQL.

La API solamente acepta llamadas autenticadas del BFF y nunca recibe la
identidad desde el cuerpo JSON de la solicitud.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import uuid

from cryptography.fernet import Fernet, InvalidToken


class HistorialNoDisponible(Exception):
    pass


def validar_conversacion(value: object, chat_id: str) -> dict:
    if not isinstance(value, dict) or set(value) != {"id", "title", "providerId", "modelId", "createdAt", "updatedAt", "messages"}:
        raise ValueError("estructura inválida")
    if value["id"] != chat_id:
        raise ValueError("id distinto")
    if not isinstance(value["title"], str) or not 1 <= len(value["title"]) <= 120:
        raise ValueError("título")
    for k in ("providerId", "modelId"):
        if not isinstance(value[k], str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", value[k]):
            raise ValueError("modelo")
    for k in ("createdAt", "updatedAt"):
        if type(value[k]) is not int or not 1_600_000_000_000 <= value[k] <= 4_100_000_000_000:
            raise ValueError("fecha")
    messages = value["messages"]
    if not isinstance(messages, list) or len(messages) > 500:
        raise ValueError("mensajes")
    for m in messages:
        if not isinstance(m, dict) or not {"id", "role", "content", "createdAt"}.issubset(m) or not set(m).issubset({"id", "role", "content", "createdAt", "noticeType"}):
            raise ValueError("mensaje")
        if not isinstance(m["id"], str) or not _uuid(m["id"]):
            raise ValueError("identificador mensaje")
        if m["role"] not in ("user", "assistant", "notice") or not isinstance(m["content"], str) or len(m["content"]) > 20000:
            raise ValueError("contenido")
        if type(m["createdAt"]) is not int or not 1_600_000_000_000 <= m["createdAt"] <= 4_100_000_000_000:
            raise ValueError("fecha mensaje")
        if "noticeType" in m and m["noticeType"] not in ("info", "protected", "blocked", "error"):
            raise ValueError("tipo aviso")
    return value


def _uuid(value: str) -> bool:
    try:
        return str(uuid.UUID(value)) == value.lower()
    except (ValueError, AttributeError, TypeError):
        return False


class ConversacionesPostgres:
    def __init__(self, *, clave: str, host: str, usuario: str, password: str, database: str):
        try:
            self.crypto = Fernet(clave.encode("ascii"))
        except (ValueError, TypeError) as exc:
            raise HistorialNoDisponible("clave de historial no válida") from exc
        self.options = {"host": host, "user": usuario, "password": password, "dbname": database, "connect_timeout": 5}
        self._init_lock = asyncio.Lock()
        self._ready = False

    @classmethod
    def desde_entorno(cls):
        if not os.environ.get("PRIVATEWAY_DB_HOST"):
            return None
        if not os.environ.get("PRIVATEWAY_CONVERSATION_KEY") or not os.environ.get("PRIVATEWAY_DB_PASSWORD"):
            return None
        return cls(clave=os.environ["PRIVATEWAY_CONVERSATION_KEY"],
                   host=os.environ["PRIVATEWAY_DB_HOST"], usuario="privateway",
                   password=os.environ["PRIVATEWAY_DB_PASSWORD"], database="privateway")

    def _conn(self):
        try:
            import psycopg
            return psycopg.connect(**self.options)
        except Exception as exc:
            raise HistorialNoDisponible("PostgreSQL no disponible") from exc

    async def _preparar(self):
        if self._ready:
            return
        async with self._init_lock:
            if self._ready:
                return
            def crear():
                with self._conn() as conn:
                    conn.execute("""CREATE TABLE IF NOT EXISTS privateway_conversations (
                        owner UUID NOT NULL, id UUID NOT NULL, content BYTEA NOT NULL,
                        updated_at BIGINT NOT NULL, PRIMARY KEY(owner, id)
                    )""")
                    conn.execute("CREATE INDEX IF NOT EXISTS privateway_conversations_recent ON privateway_conversations(owner, updated_at DESC)")
            try:
                await asyncio.to_thread(crear)
                self._ready = True
            except Exception as exc:
                raise HistorialNoDisponible("no se pudo crear historial") from exc

    async def listar(self, owner: str) -> list[dict]:
        await self._preparar()
        def consulta():
            with self._conn() as conn:
                filas = conn.execute("SELECT content FROM privateway_conversations WHERE owner = %s ORDER BY updated_at DESC LIMIT 100", (owner,)).fetchall()
            try:
                return [json.loads(self.crypto.decrypt(bytes(fila[0]))) for fila in filas]
            except (InvalidToken, ValueError, TypeError) as exc:
                raise HistorialNoDisponible("no se pudo descifrar historial") from exc
        return await asyncio.to_thread(consulta)

    async def guardar(self, owner: str, chat_id: str, body: object) -> None:
        validar_conversacion(body, chat_id)
        assert isinstance(body, dict)
        await self._preparar()
        contenido = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()
        if len(contenido) > 5_000_000:
            raise ValueError("conversación demasiado grande")
        encrypted = self.crypto.encrypt(contenido)
        def guardar_en_db():
            with self._conn() as conn:
                conn.execute("""INSERT INTO privateway_conversations(owner, id, content, updated_at)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (owner,id) DO UPDATE SET content=EXCLUDED.content,
                        updated_at=EXCLUDED.updated_at
                        WHERE privateway_conversations.updated_at <= EXCLUDED.updated_at""",
                        (owner, chat_id, encrypted, body["updatedAt"]))
        await asyncio.to_thread(guardar_en_db)

    async def eliminar(self, owner: str, chat_id: str) -> None:
        await self._preparar()
        def eliminar_db():
            with self._conn() as conn:
                conn.execute("DELETE FROM privateway_conversations WHERE owner = %s AND id = %s", (owner, chat_id))
        await asyncio.to_thread(eliminar_db)
