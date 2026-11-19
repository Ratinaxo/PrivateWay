"""Exporta resultados JSON del evaluador a tablas planas y estadística descriptiva.

No lee contenido de consultas ni valores de PII: solo consume las métricas del evaluador.
"""
import argparse
import csv
import json
import math
from pathlib import Path
import random


def wilson(exitos, total, z=1.959963984540054):
    if not total:
        return None, None
    p = exitos / total
    den = 1 + z*z/total
    centro = (p + z*z/(2*total)) / den
    radio = z * math.sqrt(p*(1-p)/total + z*z/(4*total*total)) / den
    return max(0.0, centro-radio), min(1.0, centro+radio)


def bootstrap_familias(muestras, categoria, metrica, repeticiones=2000, semilla=20261117,
                       conteos_key="conteos_categoria"):
    """IC percentil 95% remuestreando familias, no spans correlacionados."""
    familias = {}
    for m in muestras:
        familia = m.get("familia")
        if familia is None:
            continue
        conteos = (m.get(conteos_key) or {}).get(categoria, {})
        total = familias.setdefault(familia, [0, 0, 0])
        for i, k in enumerate(("tp", "fp", "fn")):
            total[i] += conteos.get(k, 0)
    nombres = sorted(familias)
    if not nombres:
        return None, None
    rng = random.Random(semilla)
    valores = []
    for _ in range(repeticiones):
        tp = fp = fn = 0
        for nombre in (rng.choice(nombres) for _ in nombres):
            x = familias[nombre]
            tp += x[0]; fp += x[1]; fn += x[2]
        precision = tp / (tp + fp) if tp + fp else None
        recall = tp / (tp + fn) if tp + fn else None
        if metrica == "precision": valor = precision
        elif metrica == "recall": valor = recall
        elif metrica == "f1": valor = 2*tp/(2*tp+fp+fn) if tp+fp+fn else None
        else: valor = 5*tp/(5*tp+4*fn+fp) if tp+fn+fp else None
        if valor is not None:
            valores.append(valor)
    if not valores:
        return None, None
    valores.sort()
    return valores[int(.025*(len(valores)-1))], valores[int(.975*(len(valores)-1))]


def bootstrap_exposicion(muestras, repeticiones=2000, semilla=20261117):
    """IC por familia para la tasa de spans visibles entre spans transmitidos."""
    familias = {}
    for m in muestras:
        if not m.get("transmitida") or not m.get("familia"):
            continue
        f = familias.setdefault(m["familia"], [0, 0])
        f[0] += m.get("apariciones_expuestas", 0) or 0
        f[1] += m.get("apariciones_referencia_transmitidas", 0) or 0
    nombres = sorted(k for k, v in familias.items() if v[1])
    if not nombres:
        return None, None
    rng = random.Random(semilla)
    valores = []
    for _ in range(repeticiones):
        expuestas = referencias = 0
        for nombre in (rng.choice(nombres) for _ in nombres):
            expuestas += familias[nombre][0]
            referencias += familias[nombre][1]
        if referencias:
            valores.append(expuestas / referencias)
    if not valores:
        return None, None
    valores.sort()
    return valores[int(.025*(len(valores)-1))], valores[int(.975*(len(valores)-1))]


def escribir_csv(path, rows, columns=None):
    if not rows and columns is None:
        return
    campos = columns or list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--resultados", type=Path, default=Path("pilot/results"))
    ap.add_argument("--salida", type=Path, help="Directorio de exportación; por defecto resultados/export")
    args = ap.parse_args()
    out = args.salida or args.resultados / "export"
    out.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in args.resultados.rglob("*.json")
                   if out not in p.parents and p.name not in {"smoke.json", "run.json", "imagenes.json"})
    experiments = []
    categories, cases, retrieval = [], [], []
    for path in files:
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(d, dict) or not {"modo", "nivel", "n", "muestras"}.issubset(d):
            continue
        base = {"archivo": path.relative_to(args.resultados).as_posix(), "modo": d.get("modo"), "nivel": d.get("nivel"),
                "split": d.get("split"), "concurrencia": d.get("concurrencia"), "n": d.get("n"),
                "errores": d.get("errores"), "bloqueos": d.get("bloqueos"),
                "transmitidas": d.get("transmitidas"), "throughput_casos_s": d.get("throughput"),
                "latencia_p50_ms": d.get("p50_ms"), "latencia_p95_ms": d.get("p95_ms"),
                "latencia_p99_ms": d.get("p99_ms"), "recall4": d.get("recall4"),
                "aciertos_accion": d.get("aciertos_accion"), "modelo": d.get("modelo"),
                "matriz_acciones": json.dumps(d.get("matriz_acciones"), ensure_ascii=False, sort_keys=True),
                "falsos_bloqueos": d.get("falsos_bloqueos"),
                "controles_limpios": d.get("controles_limpios"),
                "tasa_falsos_bloqueos": d.get("tasa_falsos_bloqueos"),
                "revision_modelo": d.get("revision_modelo"), "contexto_tokens": d.get("contexto_tokens"),
                "instrucciones_sha256": d.get("instrucciones_sha256"),
                "esquema_sha256": d.get("esquema_sha256")}
        micro = d.get("micro") or {}
        base.update({f"micro_{k}": micro.get(k) for k in ("tp", "fp", "fn", "precision", "recall", "f1", "f2")})
        cats = d.get("deteccion", {})
        fs = [v.get("f2") for v in cats.values() if v.get("f2") is not None]
        base["macro_f2"] = sum(fs)/len(fs) if fs else None
        for name in ("precision", "recall", "f1"):
            vals = [v.get(name) for v in cats.values() if v.get(name) is not None]
            base[f"macro_{name}"] = sum(vals)/len(vals) if vals else None
        partial = d.get("deteccion_parcial", {})
        pfs = [v.get("f2") for v in partial.values() if v.get("f2") is not None]
        base["macro_parcial_f2"] = sum(pfs)/len(pfs) if pfs else None
        exposure = d.get("exposicion") or {}
        exp_lo, exp_hi = bootstrap_exposicion(d.get("muestras", []))
        base.update({"exposicion_apariciones": exposure.get("apariciones_expuestas"),
                     "exposicion_exacta": exposure.get("apariciones_expuestas_exactas"),
                     "exposicion_parcial": exposure.get("apariciones_expuestas_parciales"),
                     "exposicion_referencias_transmitidas": exposure.get("apariciones_referencia_transmitidas"),
                     "exposicion_tasa": exposure.get("tasa"),
                     "exposicion_tasa_ic95_inf": exp_lo,
                     "exposicion_tasa_ic95_sup": exp_hi,
                     "exposicion_solicitudes_sensibles": exposure.get("solicitudes_sensibles_transmitidas"),
                     "exposicion_solicitudes_con_fuga": exposure.get("solicitudes_sensibles_con_exposicion")})
        experiments.append(base)
        for emparejamiento, medidas, clave_conteos in (
                ("exacto", cats, "conteos_categoria"),
                ("parcial", partial, "conteos_parciales_categoria")):
            for category, metric in medidas.items():
                row = {**{k: base[k] for k in ("archivo", "modo", "nivel", "split", "concurrencia", "n")},
                       "emparejamiento": emparejamiento, "categoria": category, **metric}
                for measure in ("precision", "recall", "f1", "f2"):
                    lo, hi = bootstrap_familias(d.get("muestras", []), category, measure,
                                                conteos_key=clave_conteos)
                    if lo is None and measure != "f2":
                        success = metric.get("tp")
                        total = (metric.get("tp", 0)+metric.get("fp", 0) if measure == "precision"
                                 else metric.get("tp", 0)+metric.get("fn", 0))
                        lo, hi = wilson(success or 0, total)
                    row[f"{measure}_ic95_inf"] = lo
                    row[f"{measure}_ic95_sup"] = hi
                categories.append(row)
        for sample in d.get("muestras", []):
            cases.append({"archivo": path.name, **{k: base[k] for k in ("modo", "nivel", "split", "concurrencia")},
                          "id_caso": sample.get("id"), "error": sample.get("error"),
                          "latencia_ms": sample.get("latencia_ms"), "accion_esperada": sample.get("esperada"),
                          "accion_observada": sample.get("accion"), "transmitida": sample.get("transmitida"),
                          "estado_transmision": sample.get("estado_transmision"),
                          "apariciones_expuestas": sample.get("apariciones_expuestas"),
                          "apariciones_expuestas_exactas": sample.get("apariciones_expuestas_exactas"),
                          "apariciones_expuestas_parciales": sample.get("apariciones_expuestas_parciales"),
                          "apariciones_referencia_transmitidas": sample.get("apariciones_referencia_transmitidas")})
        for sample in d.get("recuperacion", []):
            retrieval.append({"archivo": path.name, **{k: base[k] for k in ("modo", "nivel", "split", "concurrencia")},
                              "id_consulta": sample.get("id"), "acierto": sample.get("acierto")})
    escribir_csv(out / "experimentos.csv", experiments)
    escribir_csv(out / "metricas_categoria.csv", categories)
    escribir_csv(out / "casos.csv", cases)
    escribir_csv(out / "recuperacion.csv", retrieval)
    stats = {"numero_experimentos": len(experiments), "archivos_ignorados": len(files)-len(experiments),
             "nota_intervalos": "IC percentil 95% por bootstrap de familias cuando el JSON trae conteos por caso; Wilson por span solo para resultados antiguos. El bootstrap aún depende de que las familias sintéticas representen el uso esperado.",
             "tablas": ["experimentos.csv", "metricas_categoria.csv", "casos.csv", "recuperacion.csv"]}
    (out / "manifest.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
