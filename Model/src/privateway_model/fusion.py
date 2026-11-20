"""Unificación determinista de evidencias REGEX y SLM.

Los spans de igual mensaje y categoría que se solapan forman una sola unidad
canónica para el tratamiento. Las evidencias originales se conservan en la
traza; categorías distintas nunca se colapsan aunque cubran el mismo texto.
"""
from __future__ import annotations

from backend.deteccion.hallazgo import Categoria, CLASE_POR_CATEGORIA


def normalizar_hallazgos(hallazgos: list[dict], mensajes: list[str]) -> list[dict]:
    """Normaliza solapamientos sin perder spans ni procedencia de origen.

    El agrupamiento es transitivo y usa intersección estricta (no une spans
    adyacentes). Cada salida conserva ``evidencias`` con los offsets, texto,
    detector y confianza de cada hallazgo original.
    """
    por_clave: dict[tuple[int, str], list[dict]] = {}
    for hallazgo in hallazgos:
        mensaje = hallazgo["mensaje"]
        inicio, fin = hallazgo["inicio"], hallazgo["fin"]
        if (mensaje < 0 or mensaje >= len(mensajes) or inicio < 0
                or fin <= inicio or fin > len(mensajes[mensaje])
                or mensajes[mensaje][inicio:fin] != hallazgo["texto"]):
            raise ValueError("hallazgo de fusión fuera del mensaje original")
        por_clave.setdefault((mensaje, hallazgo["categoria"]), []).append(hallazgo)

    salida: list[dict] = []
    for (mensaje, categoria), grupo in sorted(por_clave.items()):
        grupo.sort(key=lambda h: (h["inicio"], h["fin"], h["fuente"], h["texto"]))
        componentes: list[list[dict]] = []
        fin_componente = -1
        for hallazgo in grupo:
            if componentes and hallazgo["inicio"] < fin_componente:
                componentes[-1].append(hallazgo)
                fin_componente = max(fin_componente, hallazgo["fin"])
            else:
                componentes.append([hallazgo])
                fin_componente = hallazgo["fin"]

        for componente in componentes:
            inicio = min(h["inicio"] for h in componente)
            fin = max(h["fin"] for h in componente)
            evidencias = [
                {"inicio": h["inicio"], "fin": h["fin"], "texto": h["texto"],
                 "fuente": h["fuente"], "confianza": h.get("confianza"),
                 "verificado": h.get("verificado"),
                 "persona_asociada": h.get("persona_asociada", False),
                 "subcategoria": h.get("subcategoria"),
                 "asociado_a": h.get("asociado_a")}
                for h in componente
            ]
            subcategorias = sorted({h["subcategoria"] for h in componente
                                    if h.get("subcategoria")})
            asociados = sorted({h["asociado_a"] for h in componente
                                if h.get("asociado_a")})
            fuentes = sorted({h["fuente"] for h in componente})
            confianza_regex = [h["confianza"] for h in componente
                               if h["fuente"] == "regex" and h.get("confianza") is not None]
            confianza_span = next((h["confianza"] for h in componente
                                   if h["fuente"] == "regex"
                                   and h["inicio"] == inicio and h["fin"] == fin
                                   and h.get("confianza") is not None), None)
            salida.append({
                "mensaje": mensaje, "inicio": inicio, "fin": fin,
                "categoria": categoria, "texto": mensajes[mensaje][inicio:fin],
                "clase_legal": CLASE_POR_CATEGORIA[Categoria(categoria)].value,
                "subcategorias": subcategorias,
                "atributo_titular": categoria == Categoria.MENOR_DE_EDAD.value,
                "asociado_a": asociados,
                "fuentes": fuentes,
                "confianzas": {"regex": confianza_regex, "slm": []},
                "confianza": confianza_span,
                "persona_asociada_por_evidencia": [
                    {"fuente": h["fuente"], "inicio": h["inicio"], "fin": h["fin"],
                     "persona_asociada": h.get("persona_asociada", False)}
                    for h in componente
                ],
                # Agregado explícito para la política: evidencia de asociación en
                # cualquier subspan de salud conservado dentro del grupo canónico.
                "persona_asociada_politica": any(
                    h.get("persona_asociada", False) for h in componente),
                "evidencias": evidencias,
            })
    return sorted(salida, key=lambda h: (h["mensaje"], h["inicio"], h["fin"], h["categoria"]))
