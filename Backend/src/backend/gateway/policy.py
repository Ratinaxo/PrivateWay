"""Política técnica experimental compartida por el gateway y el protocolo SLM."""
from __future__ import annotations

from collections.abc import Mapping, Sequence


def accion_tecnica(hallazgos: Sequence[Mapping[str, object]]) -> str:
    """Devuelve la acción determinista; salud exige asociación con una persona."""
    if any(h.get("categoria") == "salud" and h.get("persona_asociada") is True
           for h in hallazgos):
        return "bloquear"
    return "seudonimizar" if hallazgos else "permitir"
