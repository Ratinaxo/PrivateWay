"""Validación offline del dígito verificador de RUN/RUT chileno (módulo 11)."""
from __future__ import annotations

import re

_FORMATO = re.compile(r"^(?:\d{7,8}|\d{1,2}(?:\.\d{3}){2})\s*-?\s*[\dKk]$")


def es_valido(valor: str) -> bool:
    """Acepta RUN de 7 u 8 cifras con DV, con o sin puntos/guion.

    Sólo aplica aritmética local; no consulta bases de datos ni comprueba titularidad.
    """
    if not isinstance(valor, str) or _FORMATO.fullmatch(valor) is None:
        return False
    limpio = re.sub(r"[.\s-]", "", valor).upper()
    numero, dv = limpio[:-1], limpio[-1]
    total = sum(int(digito) * (2 + indice % 6) for indice, digito in enumerate(reversed(numero)))
    resto = 11 - (total % 11)
    esperado = "0" if resto == 11 else "K" if resto == 10 else str(resto)
    return dv == esperado
