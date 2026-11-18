"""Reportes de una ejecución concreta; ninguna conclusión de calidad está preescrita."""
import argparse
import collections
import datetime
import json
import re
import statistics
from pathlib import Path
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]


def recursos(carpeta):
    memoria=collections.defaultdict(list)
    cpu=collections.defaultdict(list)
    gpu=[]
    archivo=carpeta/"recursos.jsonl"
    if not archivo.exists():
        return ["No hay registro de recursos para esta ejecución."]
    for l in archivo.read_text(encoding="utf-8").splitlines():
        r=json.loads(l)
        try:
            gpu.append(float(r["gpu"].split(",")[0]))
        except (KeyError,TypeError,ValueError):
            pass
        for linea in (r.get("docker") or "").splitlines():
            d=json.loads(linea)
            m=re.match(r"([\d.]+)([A-Za-z]+)",d["MemUsage"].split("/")[0].strip())
            if m and m[2] in {"GiB","MiB","KiB","B"}:
                memoria[d["Name"]].append(float(m[1])*{"GiB":1024,"MiB":1,"KiB":1/1024,"B":1/1048576}[m[2]])
                cpu[d["Name"]].append(float(d["CPUPerc"].rstrip("%")))
    lineas=[]
    if gpu:
        lineas.append(f"VRAM total: media {statistics.mean(gpu):.0f} MiB; máximo muestreado {max(gpu):.0f} MiB (incluye escritorio y otras cargas).")
    for nombre, valores in sorted(memoria.items()):
        lineas.append(f'- `{nombre}`: RAM media {statistics.mean(valores):.0f} MiB, máximo {max(valores):.0f} MiB; CPU media {statistics.mean(cpu[nombre]):.1f} %.')
    return lineas+["Muestreo aproximado cada diez segundos; no mide picos breves ni energía."]


def cargar_resultados(carpeta):
    archivos = [*carpeta.glob("*-dev-c*.json"), *carpeta.glob("*-val-c*.json")]
    filas = [json.loads(p.read_text(encoding="utf-8")) for p in archivos]
    esperadas = {("deteccion",m,c) for m in ("regex","slm","hibrido") for c in (1,5,10)}
    esperadas |= {("flujo","hibrido",c) for c in (1,5,10)}
    if len(filas) != 12 or {(f["nivel"],f["modo"],f["concurrencia"]) for f in filas} != esperadas:
        raise ValueError("La ejecucion no contiene las doce configuraciones completas")
    for clave in ("instrucciones_sha256","esquema_sha256","esquemas_wire_sha256",
                  "revision_modelo","contexto_tokens","dataset_sha256","protocolo"):
        if len({f[clave] for f in filas}) != 1:
            raise ValueError(f"Resultados no comparables: {clave}")
    if len({f.get("split", "desarrollo") for f in filas}) != 1:
        raise ValueError("Se mezclaron desarrollo y validación")
    if len({f["versiones"]["indice"] for f in filas}) != 1:
        raise ValueError("Se mezclaron indices de corpus")
    ids = [{s["id"] for s in f["muestras"]} for f in filas]
    if any(i != ids[0] for i in ids) or any(f["n"] != len(f["muestras"]) for f in filas):
        raise ValueError("Las configuraciones no contienen los mismos casos")
    return sorted(filas,key=lambda f:(f["nivel"]!="deteccion",{"regex":0,"slm":1,"hibrido":2}[f["modo"]],f["concurrencia"]))


def smoke_correcto(s):
    if s["estado"] != s["esperado"]:
        return False
    if s["accion_esperada"] == "bloquear":
        return s["codigo"] == "POLITICA_BLOQUEA"
    return s["accion"] == s["accion_esperada"]


def generar(carpeta, salida, fecha, junit=None):
    filas = cargar_resultados(carpeta)
    medicion = carpeta.parent if carpeta.name.startswith("repeticion-") else carpeta
    smoke = json.loads((medicion/"smoke.json").read_text(encoding="utf-8"))
    flujos = [f for f in filas if f["nivel"] == "flujo"]
    aprobada = all(smoke_correcto(s) for s in smoke) and all(
        f["errores"] == 0 and f["aciertos_accion"] == f["n"]
        and not any(s["apariciones_expuestas"] or s.get("apariciones_parciales")
                    for s in f["muestras"]) for f in flujos)
    base = filas[0]
    split = base.get("split", "desarrollo")
    texto = [f"# Repetición del piloto — {fecha}", "",
        "**Pruebas de flujo aprobadas en este lote.**" if aprobada else "**Hay fallos pendientes en esta ejecución.**", "",
        "## Cambios y alcance", "",
        "El SLM extrae valores literales sin calcular offsets. El programa ancla cada valor exactamente "
        "en su mensaje, expande las repeticiones y conserva REGEX. El juicio técnico recibe "
        "hallazgos verificados; una etapa posterior fundamenta la clasificación con fuentes "
        "legislativas sin cambiar la acción. El gateway sigue rechazando una acción contradictoria. "
        "No se convierten respuestas inválidas en permisos ni se sustituyen por el modo REGEX.", "",
        f'Modelo: `{base.get("repo_modelo",base["modelo"])}`, revisión `{base["revision_modelo"]}`. '
        f'Protocolo `{base["protocolo"]}`; contexto {base["contexto_tokens"]} tokens. '
        "vLLM 0.10.2, AWQ-Marlin, temperatura 0, salida máxima 1024 por llamada y una generación simultánea. "
        "E5-large en CPU; pgvector exacto top-4.", "",
        f'Prefill: {base.get("prefill_tokens",512)} tokens por lote; presupuesto GPU {base.get("gpu_memory",.75):.0%}.', "",
        f'Se ejecutaron doce configuraciones con {base["n"]} escenarios de {split} cada una. '
        "Detección ejecuta solo extracción; "
        "flujo incluye extracción y juicio, API ASGI, auditoría cifrada y proveedor espía simulado. "
        "La latencia ASGI excluye TCP/proxy; el smoke sí incluye el acceso HTTP local.", ""]
    if junit:
        root = ET.parse(junit).getroot()
        suites = list(root.iter("testsuite"))
        total = sum(int(s.get("tests",0)) for s in suites)
        errores = sum(int(s.get("errors",0))+int(s.get("failures",0)) for s in suites)
        omitidas = sum(int(s.get("skipped",0)) for s in suites)
        texto += [f"Pruebas automatizadas backend: {total-errores-omitidas} aprobadas, {errores} fallidas, {omitidas} omitidas.", ""]
    texto += ["## Smoke real", "",
        "| Esperada | HTTP | Observada | Correcta |",
        "|---|---:|---|---|"]
    for s in smoke:
        texto.append(f'| {s["accion_esperada"]} | {s["estado"]} | {s["accion"] or s["codigo"]} | {"sí" if smoke_correcto(s) else "no"} |')
    texto += ["", "## Comparación", "",
        "| Nivel / variante | Concurrencia | n | Errores | F2 micro | p50 s | p95 s | Envíos | Acciones correctas |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for f in filas:
        f2 = f["micro"]["f2"]
        fmt = "—" if f2 is None else f"{f2:.3f}"
        texto.append(f'| {f["nivel"]}/{f["modo"]} | {f["concurrencia"]} | {f["n"]} | {f["errores"]} | {fmt} | '
            f'{f["p50_ms"]/1000:.3f} | {f["p95_ms"]/1000:.3f} | '
            f'{f["transmitidas"] if f["nivel"]=="flujo" else "—"} | {f["aciertos_accion"] if f["nivel"]=="flujo" else "—"} |')
    if any(f.get("latencia_etapas") for f in flujos):
        texto += ["", "## Latencia por etapa del flujo", "",
                  "| Concurrencia | Etapa | Observaciones | p50 s | p95 s |",
                  "|---:|---|---:|---:|---:|"]
        for f in flujos:
            for etapa, valores in sorted(f.get("latencia_etapas", {}).items()):
                texto.append(f'| {f["concurrencia"]} | {etapa} | {valores["n"]} | '
                             f'{valores["p50_ms"]/1000:.3f} | {valores["p95_ms"]/1000:.3f} |')
        texto += ["", "Rendimiento del flujo por concurrencia: " +
                  ", ".join(f'{f["concurrencia"]}: {f["throughput"]:.2f} solicitudes/s' for f in flujos) + "."]
    texto += ["", "Los errores cuentan como omisiones; las categorías y spans deben coincidir exactamente. "
        "Detección no exige un juicio de tratamiento y nunca transmite consultas.", "", "## Recuperación, exposición y fallos", ""]
    for f in flujos:
        enviados = [s for s in f["muestras"] if s["transmitida"]]
        anotadas = sum(s["apariciones_anotadas"] for s in enviados)
        expuestas = sum(s["apariciones_expuestas"] or 0 for s in enviados)
        parciales = sum(s.get("apariciones_parciales") or 0 for s in enviados)
        parcial = f", {parciales}/{anotadas} parcialmente visibles" if any(
            "apariciones_parciales" in s for s in f["muestras"]
        ) else ""
        texto.append(f'- Concurrencia {f["concurrencia"]}: {f["transmitidas"]} envíos, {f["bloqueos"]} bloqueos del SLM, '
            f'{f["errores"]} fallos técnicos; {expuestas}/{anotadas} apariciones literales{parcial}.')
    texto += ["", f'Recall@4: {base["recall4"]:.3f}, en doce preguntas jurídicas de {split}. '
        "Esta métrica mide recuperación documental. La pertinencia de citas y fundamentos requiere revisión aparte. "
        "La comprobación de exposición se limita a las apariciones anotadas.", ""]
    fallos = collections.Counter()
    for p in carpeta.glob("flujo-*.events.jsonl"):
        for l in p.read_text(encoding="utf-8").splitlines():
            evento = json.loads(l)["evento"]
            if evento.get("fase") == "fallo_analisis":
                fallos[evento["motivo"]] += 1
    texto += ["Códigos técnicos (incluido calentamiento): " + (
        ", ".join(f"`{k}`: {v}" for k,v in sorted(fallos.items())) or "ninguno registrado") + ".", "",
        "## Recursos observados", ""] + recursos(medicion) + ["", "## Reproducibilidad y límites", "",
        f'- Corpus: `{base["versiones"]["indice"]}`.',
        f'- Instrucciones SHA-256: `{base["instrucciones_sha256"]}`.',
        f'- Esquemas de inferencia SHA-256: `{base["esquemas_wire_sha256"]}`.',
        f'- Dataset SHA-256: `{base["dataset_sha256"]}`.',
        f'- Evidencias locales: `{carpeta.relative_to(ROOT).as_posix()}`.',
        "- Cada repetición usa una carpeta independiente; no se acumulan eventos de ejecuciones anteriores.",
        "- Se conservaron el informe del 14 de noviembre, el modelo anterior y sus revisiones.",
        "- Una pasada por configuración con datos sintéticos no demuestra generalización ni resistencia a toda inyección.",
        "- La utilidad con proveedor externo y la restitución requieren sus propias pruebas.", ""]
    salida.parent.mkdir(parents=True,exist_ok=True)
    archivo_run = medicion / "run.json"
    if archivo_run.exists():
        corrida = json.loads(archivo_run.read_text(encoding="utf-8"))
        if corrida.get("revision_codigo"):
            estado = "limpio" if corrida.get("arbol_limpio") else "con cambios locales al iniciar"
            texto += [f'- Commit base: `{corrida["revision_codigo"]}`. Árbol de trabajo {estado}.', ""]
    salida.write_text("\n".join(texto),encoding="utf-8")
    return aprobada


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--fecha",default=datetime.datetime.now(ZoneInfo("America/Santiago")).date().isoformat())
    parser.add_argument("--junit",type=Path)
    args = parser.parse_args()
    ok = generar(args.results.resolve(),args.output.resolve(),args.fecha,args.junit)
    print("Reporte generado; flujo aprobado: " + str(ok))


if __name__ == "__main__":
    main()
