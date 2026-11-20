"""Métricas reproducibles de detección y exposición de PrivateWay."""
from __future__ import annotations

import re
import unicodedata


def metricas(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f2 = 5 * tp / (5 * tp + 4 * fn + fp) if tp + fn + fp else None
    f1 = 2 * tp / (2 * tp + fp + fn) if tp + fp + fn else None
    return dict(tp=tp, fp=fp, fn=fn, precision=precision, recall=recall, f1=f1, f2=f2)


def macro_por_categoria(categorias: dict[str, dict]) -> dict:
    """Promedia cada métrica sobre categorías donde esté definida."""
    salida = {}
    for nombre in ("precision", "recall", "f1", "f2"):
        valores = [m[nombre] for m in categorias.values() if m[nombre] is not None]
        salida[nombre] = sum(valores) / len(valores) if valores else None
        salida[f"categorias_{nombre}"] = len(valores)
    return salida


def conteos_parciales(verdad, predicciones) -> tuple[int, int, int]:
    """Empareja spans solapados de igual mensaje y categoría, una vez cada uno."""
    refs, preds = sorted(set(verdad)), sorted(set(predicciones))
    adyacencia = []
    for pred in preds:
        mensaje, inicio, fin, categoria = pred
        candidatos = [i for i, ref in enumerate(refs)
                      if ref[0] == mensaje and ref[3] == categoria
                      and max(inicio, ref[1]) < min(fin, ref[2])]
        candidatos.sort(key=lambda i: -(min(fin, refs[i][2]) - max(inicio, refs[i][1])))
        adyacencia.append(candidatos)
    asignacion_ref = {}

    def asignar(indice_pred, visitados):
        for indice_ref in adyacencia[indice_pred]:
            if indice_ref in visitados:
                continue
            visitados.add(indice_ref)
            previo = asignacion_ref.get(indice_ref)
            if previo is None or asignar(previo, visitados):
                asignacion_ref[indice_ref] = indice_pred
                return True
        return False

    tp = sum(asignar(i, set()) for i in range(len(preds)))
    return tp, len(preds) - tp, len(refs) - tp


def _normalizar(texto: str) -> str:
    expandido = unicodedata.normalize("NFKD", texto).casefold()
    return re.sub(r"\s+", " ", "".join(c if c.isalnum() else " " for c in expandido)).strip()


def _aplanar(texto: str) -> str:
    return "".join(c for c in _normalizar(texto) if c != " ")


def coincide_exposicion(valor: str, texto_enviado: str, min_fragmento: int = 4) -> bool:
    """Detecta valores exactos o fragmentos alfanuméricos contiguos visibles.

    La búsqueda parcial es deliberadamente conservadora: cuatro caracteres
    contiguos de un span anotado cuentan como exposición. Para valores de menos
    de cuatro caracteres se exige coincidencia completa.
    """
    objetivo, enviado = _normalizar(valor), _normalizar(texto_enviado)
    if not objetivo or not enviado:
        return False
    def token_visible(token):
        return re.search(rf"(?<!\w){re.escape(token)}(?!\w)", enviado) is not None

    if len(objetivo.replace(" ", "")) <= min_fragmento:
        return token_visible(objetivo)
    if _aplanar(objetivo) in _aplanar(enviado):
        return True
    # Un token corto se considera expuesto si aparece completo; para uno largo,
    # basta cualquier ventana contigua de cuatro caracteres.
    for token in objetivo.split():
        if len(token) <= min_fragmento:
            if token_visible(token):
                return True
        elif any(token[i:i + min_fragmento] in enviado
                 for i in range(len(token) - min_fragmento + 1)):
            return True
    return False


def exposicion_solicitud(originales, enviados, spans: list[tuple[int, int, int, int]]) -> dict:
    """Cuenta PII de referencia visible en un envío confirmado.

    ``spans`` contiene (mensaje, inicio, fin, categoria). Cada aparición se
    cuenta como máximo una vez, incluso cuando solo queda un fragmento.
    """
    exactas = parciales = 0
    for mensaje, inicio, fin, _categoria in spans:
        if mensaje >= len(originales) or mensaje >= len(enviados):
            continue
        valor = originales[mensaje].content[inicio:fin]
        texto_enviado = enviados[mensaje].content
        valor_normalizado = _aplanar(valor)
        envio_normalizado = _aplanar(texto_enviado)
        if valor_normalizado and valor_normalizado in envio_normalizado:
            exactas += 1
        elif coincide_exposicion(valor, texto_enviado):
            parciales += 1
    expuestas = exactas + parciales
    return {"expuestas": expuestas, "exactas": exactas, "parciales": parciales,
            "referencias": len(spans), "tasa": expuestas / len(spans) if spans else None}
