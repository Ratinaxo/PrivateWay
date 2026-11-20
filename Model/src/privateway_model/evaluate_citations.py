"""Compara recuperación y citas del juicio del gateway en preguntas sintéticas."""
import argparse
import asyncio
import json
import re
from pathlib import Path

from backend.gateway.contracts import Mensaje, SolicitudChat
from privateway_model.hybrid import desde_entorno
from backend.gateway.pipeline import AnalisisNoDisponible, ContextoEjecucion
from privateway_model.slm_protocol import VERSION


def _normalizar_identificador(valor):
    if not isinstance(valor, str):
        return ""
    return re.sub(r"[^a-z0-9]+", "_", valor.casefold()).strip("_")


def _fragmento_corresponde(fragmento, esperado):
    """Resuelve unidades por metadata normativa y soporta IDs legacy por prefijo."""
    objetivo = _normalizar_identificador(esperado)
    identificadores = (fragmento.get("identificador_normativo"), fragmento.get("id"))
    for identificador in identificadores:
        normalizado = _normalizar_identificador(identificador)
        if normalizado and re.search(rf"(?:^|_){re.escape(objetivo)}(?:_|$)", normalizado):
            return True
    return False


def _rango_esperado(fragmentos, esperado):
    for rango, fragmento in enumerate(fragmentos, 1):
        if _fragmento_corresponde(fragmento, esperado):
            return rango
    return None


def _resumen_fragmento(fragmento):
    campos = ("id", "identificador_normativo", "documento", "localizador", "version",
              "estado", "vigencia_desde")
    return {campo: fragmento[campo] for campo in campos if campo in fragmento}


def _resolver_cita(cita, fragmentos):
    referencia = _normalizar_identificador(cita)
    for fragmento in fragmentos:
        candidatos = (fragmento.get("id"), fragmento.get("identificador_normativo"))
        if any(referencia and referencia == _normalizar_identificador(candidato)
               for candidato in candidatos):
            return fragmento
    return None


async def evaluar(split: str, dataset: Path, salida: Path) -> None:
    casos = [c for c in json.loads(dataset.read_text(encoding="utf-8")) if c["split"] == split]
    if len(casos) != 12:
        raise ValueError("Se esperaban doce preguntas jurídicas en el conjunto")
    pipeline = desde_entorno()
    if not await pipeline.comprobar():
        raise RuntimeError("Servicios locales de SLM/RAG no disponibles")
    muestras = []
    for caso in casos:
        mensajes = [Mensaje(role="user", content=caso["consulta"])]
        # Comparar consulta sola con consulta + categorías detectadas por REGEX.
        # Solo se guardan categorías; nunca los valores detectados.
        recuperados_sin_senales = await pipeline.recuperador.buscar(mensajes, [])
        hallazgos_regex = pipeline._detectar(caso["consulta"])
        senales = [{"mensaje": 0, "categoria": h.categoria.value}
                   for h in hallazgos_regex]
        recuperados = await pipeline.recuperador.buscar(mensajes, senales)
        rango_esperado = _rango_esperado(recuperados, caso["esperado"])
        rango_sin_senales = _rango_esperado(recuperados_sin_senales, caso["esperado"])
        muestra = dict(id=caso["id"], esperado=caso["esperado"],
                       fragmentos_recuperados=[_resumen_fragmento(f) for f in recuperados],
                       categorias_regex=sorted({s["categoria"] for s in senales}),
                       fragmentos_recuperados_sin_senales=[
                           _resumen_fragmento(f) for f in recuperados_sin_senales],
                       recuperacion_correcta=rango_esperado is not None,
                       rango_esperado=rango_esperado,
                       reciprocal_rank=(1 / rango_esperado if rango_esperado else 0.0),
                       recuperacion_correcta_sin_senales=rango_sin_senales is not None,
                       rango_esperado_sin_senales=rango_sin_senales,
                       reciprocal_rank_sin_senales=(1 / rango_sin_senales
                                                    if rango_sin_senales else 0.0))
        try:
            decision = await pipeline.analizar(
                SolicitudChat(model="pw-simulado", messages=mensajes),
                ContextoEjecucion("evaluacion-citas", "sintetico"),
            )
        except AnalisisNoDisponible as exc:
            muestra.update(error=exc.codigo, citados=[], cita_esperada=None)
        else:
            traza = decision.traza
            citados = traza["referencias"]
            contexto = traza["fragmentos"]
            citas_resueltas = [_resolver_cita(cita, contexto) for cita in citados]
            muestra.update(error=None, citados=citados,
                           contexto_del_juicio=[_resumen_fragmento(f) for f in contexto],
                           esperado_en_contexto=_rango_esperado(contexto, caso["esperado"]) is not None,
                           citas_resueltas=[_resumen_fragmento(f) for f in citas_resueltas if f],
                           referencias_resueltas=len([f for f in citas_resueltas if f]),
                           cita_esperada=any(
                               f is not None and _fragmento_corresponde(f, caso["esperado"])
                               for f in citas_resueltas),
                           justificacion=traza["justificacion"])
        muestras.append(muestra)
    resumen = dict(split=split, protocolo=VERSION, versiones=await pipeline.recuperador.versiones(),
                   revision_modelo=pipeline.slm.revision, muestras=muestras,
                   recuperaciones_correctas=sum(m["recuperacion_correcta"] for m in muestras),
                   recall_at_4=(sum(m["recuperacion_correcta"] for m in muestras) / len(muestras)
                                if muestras else None),
                   mrr_at_4=(sum(m["reciprocal_rank"] for m in muestras) / len(muestras)
                             if muestras else None),
                   recall_at_4_sin_senales=(
                       sum(m["recuperacion_correcta_sin_senales"] for m in muestras) / len(muestras)
                       if muestras else None),
                   mrr_at_4_sin_senales=(
                       sum(m["reciprocal_rank_sin_senales"] for m in muestras) / len(muestras)
                       if muestras else None),
                   citas_esperadas=sum(m["cita_esperada"] is True for m in muestras),
                   juicios_evaluables=sum(m["error"] is None for m in muestras))
    with salida.open("x", encoding="utf-8") as archivo:
        json.dump(resumen, archivo, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("desarrollo", "validacion"), default="desarrollo")
    parser.add_argument("--dataset", type=Path, default=Path("/model/datasets/v1/recuperacion.json"))
    parser.add_argument("--salida", type=Path, required=True)
    args = parser.parse_args()
    if args.salida.exists():
        parser.error("Usar un archivo nuevo")
    asyncio.run(evaluar(args.split, args.dataset, args.salida))
