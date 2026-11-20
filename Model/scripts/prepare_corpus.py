"""Descarga XML oficial y extrae artículos sin notas editoriales BCN."""
import datetime
import hashlib
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2] / "Model/corpus"


def tag(e):
    return e.tag.rsplit("}", 1)[-1].lower()


def texto(e):
    return " ".join("".join(e.itertext()).split())


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / "raw").mkdir(exist_ok=True)
    docs, fragmentos = [], []
    for ley, norma in [("19628", "141599"), ("21719", "1209272")]:
        url = f"https://www.bcn.cl/leychile/servicios/Consulta/obtxml?opt=7&idNorma={norma}"
        raw = ROOT / "raw" / f"ley{ley}.xml"
        if not raw.exists():
            with urllib.request.urlopen(url, timeout=90) as r:
                b = r.read()
            arbol = ET.fromstring(b)
            if tag(arbol) not in ("norma", "normas"):
                raise ValueError("La fuente no devolvió XML normativo")
            raw.write_bytes(b)
        b = raw.read_bytes()
        arbol = ET.fromstring(b)
        docs.append(dict(id=f"ley{ley}", url=url,
                         fecha_descarga=datetime.datetime.fromtimestamp(raw.stat().st_mtime, datetime.timezone.utc).date().isoformat(),
                         version_xml=arbol.attrib["fechaVersion"],
                         estado="texto_base" if ley == "19628" else "reforma_con_vigencia_diferida",
                         sha256=hashlib.sha256(b).hexdigest(),
                         metadata_xml={k:v for k,v in arbol.attrib.items()}))
        # El servicio XML ignora fechas futuras: extraer disposiciones reformadas
        # de la ley modificatoria, sin presentar el texto base como consolidado.
        if ley != "21719":
            continue
        ns = {"n": "http://www.leychile.cl/esquemas"}
        reforma = arbol.find(".//n:EstructuraFuncional/n:Texto", ns).text
        extracciones = [
            ("art2_f", "Ley 19.628 art. 2 f), sustituido por Ley 21.719 art. primero numeral 5 uno", r"(?ms)^\s+f\) Dato personal:.*?(?=^\s+g\))"),
            ("art2_g", "Ley 19.628 art. 2 g), sustituido por Ley 21.719 art. primero numeral 5 uno", r"(?ms)^\s+g\) Datos personales sensibles:.*?(?=^\s+i\))"),
            ("art2_l", "Ley 19.628 art. 2 l), sustituido por Ley 21.719 art. primero numeral 5 tres", r"(?ms)^\s+l\) Seudonimización:.*?(?=^\s+m\))"),
            ("art16bis", "Ley 19.628 art. 16 bis, incorporado por Ley 21.719 art. primero", r"(?ms)^\s+Artículo 16 bis\.-.*?(?=^\s+Artículo 16 ter)"),
        ]
        principios = re.search(r'(?s)"Artículo 3°\.- Principios\.(.*?)(?=\n\s+7\))', reforma)
        if not principios:
            raise ValueError("No se encontró artículo de principios")
        for letra in "abcdefg":
            patron = rf"(?ms)^\s+{letra}\) .*?(?=^\s+[a-z]\)|\Z)"
            coincidencia = re.search(patron, principios[1])
            if coincidencia:
                extracciones.append((f"art3_{letra}", f"Ley 19.628 art. 3 {letra}), sustituido por Ley 21.719 art. primero numeral 6", None))
                t = " ".join(coincidencia[0].split()).rstrip('". ')
                fragmentos.append(dict(id=f"art3_{letra}", documento="ley21719",
                    localizador=extracciones[-1][1], version=arbol.attrib["fechaVersion"],
                    vigencia_desde="2026-12-01", estado="vigencia_diferida", texto=t))
        for fid, localizador, patron in extracciones:
            if patron is None:
                continue
            encontrado = re.search(patron, reforma)
            if not encontrado:
                raise ValueError(f"No se encontró {fid}")
            t = " ".join(encontrado[0].split())
            fragmentos.append(dict(id=fid, documento="ley21719", localizador=localizador,
                                   version=arbol.attrib["fechaVersion"], vigencia_desde="2026-12-01",
                                   estado="vigencia_diferida", texto=t))
    if not fragmentos:
        raise ValueError("No se localizaron artículos. Inspeccionar XML; no se activa corpus vacío.")
    (ROOT / "manifest.json").write_text(json.dumps(dict(version="bcn-2026-12-01-piloto-v1",
        documentos=docs, fragmentos=fragmentos), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Corpus preparado: {len(fragmentos)} unidades legislativas.")


if __name__ == "__main__":
    main()
