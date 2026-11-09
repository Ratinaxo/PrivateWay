"""Contrato mínimo y deliberadamente restrictivo para chat de texto."""
from __future__ import annotations

from enum import Enum
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Accion(str, Enum):
    PERMITIR = "permitir"
    SEUDONIMIZAR = "seudonimizar"
    BLOQUEAR = "bloquear"


class Mensaje(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["system", "developer", "user", "assistant"]
    content: str = Field(min_length=1, max_length=20000)


class SolicitudChat(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str = Field(min_length=1, max_length=100)
    messages: list[Mensaje] = Field(min_length=1, max_length=30)
    stream: Literal[False] = False  # Streaming aún no inspeccionado: se rechaza.
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1, le=8192)


class RespuestaProveedor(BaseModel):
    """Salida normalizada; contenido del proveedor queda en memoria local."""
    content: str
    finish_reason: str = "stop"
