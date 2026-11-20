"""Criterios reproducibles de visibilidad para anotaciones sintéticas."""
import re
import unicodedata

from backend.gateway.pipeline import PATRON_MARCADOR

_PALABRA = re.compile(r"[^\W_]+")


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto).casefold()
    return "".join(c for c in texto if not unicodedata.combining(c))


def visibilidad(valor: str, enviado: str, categoria: str) -> str:
    if valor in enviado:
        return "literal"
    visible = PATRON_MARCADOR.sub(" ", enviado)
    anotados = _PALABRA.findall(_normalizar(valor))
    observados = _PALABRA.findall(_normalizar(visible))
    if categoria in {"run", "telefono", "tarjeta", "geolocalizacion"}:
        digitos = "".join(c for c in valor if c.isdigit())
        # No unir cifras que estén separadas por palabras o marcadores.
        tramos = re.findall(r"\d(?:[\d .()+-]*\d)?", visible)
        for tramo in tramos:
            candidato = "".join(c for c in tramo if c.isdigit())
            if any(digitos[i:i + 4] in candidato for i in range(len(digitos) - 3)):
                return "parcial"
        return "oculta"
    if categoria == "correo":
        # El dominio compartido no identifica por sí solo al titular.
        anotados = _PALABRA.findall(_normalizar(valor.partition("@")[0]))
    return "parcial" if any(
        len(palabra) >= 3 and palabra in observados for palabra in anotados
    ) else "oculta"
