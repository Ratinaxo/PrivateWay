"""Diagnóstico local del detector REGEX. Solo utiliza datos inventados.

Ejecutar: python -m backend.deteccion.diagnostico
No imprime los valores detectados, solo categorías y conteos.
"""
from __future__ import annotations

from collections import Counter

from .hallazgo import Categoria
from .regex import EtapaRegex


def main() -> int:
    texto = "RUN 12.345.678-5, correo persona@ejemplo.cl, móvil +56 9 1234 5678."
    hallazgos = EtapaRegex().analizar(texto)
    tipos = Counter(h.categoria for h in hallazgos)
    esperados = (Categoria.RUN, Categoria.CORREO, Categoria.TELEFONO)
    exito = all(tipos.get(categoria, 0) >= 1 for categoria in esperados)
    print("REGEX local:", "OK" if exito else "ERROR")
    for categoria in esperados:
        print(f"  {categoria.value}: {tipos.get(categoria, 0)}")
    return 0 if exito else 1


if __name__ == "__main__":
    raise SystemExit(main())
