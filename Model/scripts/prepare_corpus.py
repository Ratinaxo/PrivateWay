"""Construye el manifiesto RAG desde los Markdown normativos de docs/."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import unicodedata


ROOT = Path(__file__).resolve().parents[2] / "Model/corpus"
REPO = Path(__file__).resolve().parents[2]
MESES = {"ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6,
         "JUL": 7, "AGO": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DIC": 12}
# Deja margen para el encabezado y el prefijo E5 dentro del límite de 512 tokens.
OBJETIVO_CARACTERES = 1800


def fecha_es(texto: str) -> str | None:
    m = re.search(r"(\d{1,2})-([A-ZÁÉÍÓÚ]{3})-(\d{4})", texto.upper())
    if not m:
        return None
    mes = MESES.get(m.group(2).replace("Á", "A").replace("É", "E"))
    if not mes:
        return None
    return dt.date(int(m.group(3)), mes, int(m.group(1))).isoformat()


def slug(texto: str) -> str:
    limpio = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", limpio).strip("_")[:72] or "seccion"


def limpiar_markdown(texto: str) -> str:
    texto = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", texto)
    texto = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", texto)
    texto = re.sub(r"<[^>]+>", " ", texto)
    texto = re.sub(r"[*_`]+", "", texto)
    texto = re.sub(r"^\s*[-+]\s+", "", texto, flags=re.MULTILINE)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def metadatos_documento(path: Path, fuente: str) -> dict:
    raw = path.read_bytes()
    texto = raw.decode("utf-8")
    doc_id = "ley" + ("19628" if "19628" in path.name else "21719")
    if doc_id == "ley19628":
        version_m = re.search(r"Versión:\s*Última Versión De\s*:\s*([^\n]+)", texto, re.I)
        vigencia_inicio = fecha_es(re.search(r"Inicio Vigencia:\s*([^\n]+)", texto, re.I)[1])
        vigencia_fin = fecha_es(re.search(r"Fin Vigencia:\s*([^\n]+)", texto, re.I)[1])
        version = fecha_es(version_m[1]) if version_m else None
        estado = "vigente_hasta"
        fuente_url = "https://www.bcn.cl/leychile/navegar?idNorma=141599"
    else:
        version_m = re.search(r"Ultima Modificación:\s*(\d{1,2}-[A-ZÁÉÍÓÚ]{3}-\d{4})", texto, re.I)
        vigencia_m = re.search(r"Vigencia Diferida por Fecha De\s*:\s*(\d{1,2}-[A-ZÁÉÍÓÚ]{3}-\d{4})", texto, re.I)
        version = fecha_es(version_m[1]) if version_m else None
        vigencia_inicio = fecha_es(vigencia_m[1]) if vigencia_m else None
        vigencia_fin = None
        estado = "vigencia_diferida" if vigencia_inicio else "vigente"
        fuente_url = "https://www.bcn.cl/leychile/navegar?idNorma=1209272"
    if not version:
        raise ValueError(f"No se pudo leer la versión de {path.name}")
    return dict(id=doc_id, nombre=path.name, tipo="legislacion_chilena",
                url=fuente_url, url_documento=fuente,
                version=version, vigencia_desde=vigencia_inicio,
                vigencia_hasta=vigencia_fin, estado=estado,
                sha256=hashlib.sha256(raw).hexdigest())


def secciones(texto: str):
    """Devuelve bloques markdown con su ruta de encabezados, sin mezclar artículos."""
    lineas = texto.splitlines()
    encabezado = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
    pila: list[tuple[int, str]] = []
    actual = None
    cuerpo: list[str] = []
    ordinal = 0
    for linea in lineas:
        m = encabezado.match(linea)
        if m:
            if actual is not None:
                yield actual, cuerpo, ordinal
            nivel, titulo = len(m[1]), m[2].strip().strip('"')
            while pila and pila[-1][0] >= nivel:
                pila.pop()
            pila.append((nivel, titulo))
            ordinal += 1
            actual = (nivel, titulo, tuple(t for n, t in pila if n > 1))
            cuerpo = []
        elif actual is not None:
            cuerpo.append(linea)
    if actual is not None:
        yield actual, cuerpo, ordinal


def partes(cuerpo: list[str]) -> list[str]:
    """Agrupa párrafos contiguos hasta un tamaño moderado y corta por párrafo."""
    parrafos = [limpiar_markdown(p) for p in re.split(r"\n\s*\n", "\n".join(cuerpo))]
    parrafos = [p for p in parrafos if p]
    salida, actual = [], ""
    for parrafo in parrafos:
        if actual and len(actual) + len(parrafo) + 1 > OBJETIVO_CARACTERES:
            salida.append(actual)
            actual = ""
        if len(parrafo) <= OBJETIVO_CARACTERES:
            actual = f"{actual} {parrafo}".strip()
            continue
        # Las disposiciones extensas se dividen en oraciones, conservando límites.
        oraciones = re.split(r"(?<=[.;:])\s+(?=[A-ZÁÉÍÓÚ¿¡\d(])", parrafo)
        for oracion in oraciones:
            if actual and len(actual) + len(oracion) + 1 > OBJETIVO_CARACTERES:
                salida.append(actual)
                actual = ""
            actual = f"{actual} {oracion}".strip()
    if actual:
        salida.append(actual)
    return salida


def patrones_atomos():
    return {
        "art2_f": (r"(?ms)^f\) Dato personal:.*?(?=^g\) Datos personales sensibles:)",
                   "Ley 19.628 art. 2 f), sustituido por Ley 21.719 art. primero numeral 5 uno"),
        "art2_g": (r"(?ms)^g\) Datos personales sensibles:.*?(?=^i\) Fuentes de acceso público:)",
                   "Ley 19.628 art. 2 g), sustituido por Ley 21.719 art. primero numeral 5 uno"),
        "art2_l": (r"(?ms)^l\) Seudonimización:.*?(?=^m\) Base de datos personales:)",
                   "Ley 19.628 art. 2 l), sustituido por Ley 21.719 art. primero numeral 5 tres"),
        "art3_c": (r"(?ms)^c\) Principio de proporcionalidad\..*?(?=^d\) Principio de calidad\.)",
                   "Ley 19.628 art. 3 c), sustituido por Ley 21.719 art. primero numeral 6"),
        "art3_f": (r"(?ms)^f\) Principio de seguridad\..*?(?=^g\) Principio de transparencia e información\.)",
                   "Ley 19.628 art. 3 f), sustituido por Ley 21.719 art. primero numeral 6"),
    }


def extraer_atomos(markdown: str, documento: dict) -> tuple[list[dict], str]:
    """Extrae literales de los numerales reformatorios y evita indexarlos otra vez."""
    atomos = []
    spans = []
    for fragmento_id, (patron, localizador) in patrones_atomos().items():
        encontrado = re.search(patron, markdown)
        if not encontrado:
            raise ValueError(f"No se encontró la disposición normativa {fragmento_id}")
        texto = limpiar_markdown(encontrado[0])
        atomos.append(dict(
            id=fragmento_id, documento="ley21719", tipo_fuente="legislacion_chilena",
            archivo=documento["nombre"], localizador=localizador,
            encabezado=fragmento_id, contexto="Ley 21.719 / artículo primero",
            version=documento["version"], vigencia_desde=documento["vigencia_desde"],
            vigencia_hasta=documento["vigencia_hasta"], estado=documento["estado"],
            etapa_normativa="reforma_con_vigencia_diferida",
            texto=f"{localizador}. {texto}"))
        spans.append(encontrado.span())
    restante = markdown
    for inicio, fin in sorted(spans, reverse=True):
        restante = restante[:inicio] + "\n\n" + restante[fin:]
    return atomos, restante


def construir(directorio_fuentes: Path) -> dict:
    archivos = [directorio_fuentes / "Ley-19628.md", directorio_fuentes / "Ley-21719.md"]
    if any(not p.is_file() for p in archivos):
        faltan = [p.name for p in archivos if not p.is_file()]
        raise FileNotFoundError("Faltan fuentes Markdown: " + ", ".join(faltan))
    documentos, fragmentos = [], []
    for path in archivos:
        doc = metadatos_documento(path, path.name)
        documentos.append(doc)
        markdown = path.read_text(encoding="utf-8")
        if doc["id"] == "ley21719":
            atomos, markdown_generico = extraer_atomos(markdown, doc)
            fragmentos.extend(atomos)
            # El texto base permanece disponible hasta su fecha de reemplazo; la
            # reforma se identifica en metadatos como una capa normativa distinta.
            doc["etapa_normativa"] = "reforma_con_vigencia_diferida"
            texto_16bis = None
            encabezado_16bis = None
            for (nivel, titulo, ruta), cuerpo, _ordinal in secciones(markdown):
                if re.match(r"(?i)^art[ií]culo\s+16\s+bis", titulo):
                    texto_16bis = limpiar_markdown("\n".join(cuerpo))
                    encabezado_16bis = titulo
                    locator_16bis = (
                        "Ley 19.628 art. 16 bis, incorporado por Ley 21.719 "
                        "art. primero numeral 8"
                    )
                    break
            if not texto_16bis:
                raise ValueError("No se encontró la disposición art16bis")
            fragmentos.append(dict(
                id="art16bis", documento="ley21719",
                tipo_fuente="legislacion_chilena", archivo=doc["nombre"],
                localizador=locator_16bis, encabezado=encabezado_16bis,
                contexto="Ley 21.719 / artículo primero numeral 8",
                version=doc["version"], vigencia_desde=doc["vigencia_desde"],
                vigencia_hasta=doc["vigencia_hasta"], estado=doc["estado"],
                etapa_normativa="reforma_con_vigencia_diferida",
                texto=f"{locator_16bis}. {encabezado_16bis} {texto_16bis}"))
        else:
            markdown_generico = markdown
        for (nivel, titulo, ruta), cuerpo, ordinal in secciones(markdown_generico):
            # Solo indexa unidades dispositivas, no metadatos, títulos editoriales
            # ni referencias marginales reconstruidas desde el PDF.
            if any("referencias marginales" in t.casefold() for t in ruta):
                continue
            if not re.match(r"(?i)^art[ií]culo\s+", titulo):
                continue
            if doc["id"] == "ley21719" and re.match(r"(?i)^art[ií]culo\s+16\s+bis", titulo):
                continue
            unidades = partes(cuerpo)
            if not unidades:
                continue
            ruta_texto = " / ".join(ruta) if ruta else titulo
            localizador = ruta_texto
            contexto = limpiar_markdown(" / ".join(ruta[:-1]))
            for i, unidad in enumerate(unidades, 1):
                texto_fragmento = f"{ruta_texto}. {unidad}"
                fragmentos.append(dict(
                    id=f"{doc['id']}_{ordinal:04d}_{slug(titulo)}_{i:03d}",
                    documento=doc["id"], tipo_fuente=doc["tipo"],
                    archivo=doc["nombre"], localizador=localizador,
                    encabezado=titulo, contexto=contexto,
                    version=doc["version"], vigencia_desde=doc["vigencia_desde"],
                    vigencia_hasta=doc["vigencia_hasta"], estado=doc["estado"],
                    etapa_normativa=("texto_base_antes_de_reforma" if doc["id"] == "ley19628"
                                     else "reforma_con_vigencia_diferida"),
                    texto=texto_fragmento))
    return dict(version="docs-markdown-v1", documentos=documentos, fragmentos=fragmentos)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fuentes", type=Path, default=REPO / "docs",
                        help="directorio con Ley-19628.md y Ley-21719.md")
    parser.add_argument("--salida", type=Path, default=ROOT / "manifest.json")
    args = parser.parse_args()
    datos = construir(args.fuentes)
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Corpus preparado: {len(datos['documentos'])} documentos, "
          f"{len(datos['fragmentos'])} fragmentos estructurales.")


if __name__ == "__main__":
    main()
