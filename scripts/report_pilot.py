"""Resume evidencia medida; no convierte fallos de calidad en resultados positivos."""
import collections
import json
from pathlib import Path
import re
import statistics

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "pilot/results"


def cargar_resultados(carpeta):
    """Carga una matriz comparable y rechaza cambios de modelo/dataset/esquema."""
    filas = [json.loads(p.read_text(encoding="utf-8"))
             for p in sorted(Path(carpeta).glob("*-dev-c*.json"))]
    if not filas:
        raise ValueError("No hay resultados de desarrollo")
    for clave in ("instrucciones_sha256", "esquema_sha256", "esquemas_wire_sha256",
                  "revision_modelo", "contexto_tokens", "dataset_sha256", "protocolo"):
        valores = {f.get(clave) for f in filas}
        if len(valores) > 1:
            raise ValueError(f"Configuraciones no comparables: {clave} distinto")
    indices = {f.get("versiones", {}).get("indice") for f in filas}
    if len(indices) > 1:
        raise ValueError("Configuraciones no comparables: indice distinto")
    return filas


def smoke_correcto(caso):
    if caso.get("estado") != caso.get("esperado"):
        return False
    accion = caso.get("accion_esperada")
    if accion == "bloquear":
        return caso.get("codigo") == "POLITICA_BLOQUEA"
    return caso.get("accion") == accion


def numero(n):
    return "—" if n is None else f"{n:.3f}"


def main():
    filas = []
    for p in sorted(RESULTS.glob("*-dev-c*.json")):
        if p.name.startswith(("deteccion-","flujo-")):
            filas.append(json.loads(p.read_text(encoding="utf-8")))
    if len(filas) != 12:
        raise RuntimeError(f"Se esperaban 12 configuraciones completas; hay {len(filas)}")
    filas.sort(key=lambda f: (f["nivel"] != "deteccion", {"regex":0,"slm":1,"hibrido":2}[f["modo"]], f["concurrencia"]))
    for clave in ("instrucciones_sha256", "esquema_sha256", "revision_modelo", "contexto_tokens"):
        if len({f[clave] for f in filas}) != 1:
            raise RuntimeError(f"Configuraciones no comparables: {clave} distinto")
    if len({f["versiones"]["indice"] for f in filas}) != 1:
        raise RuntimeError("Los experimentos no usan el mismo indice")
    smoke = json.loads((RESULTS / "smoke.json").read_text())
    lineas = ["# Informe del piloto local — 14 de noviembre de 2026", "",
        "**Infraestructura e integración implementadas; esta configuración del SLM todavía no es apta para el flujo funcional.**", "",
        "## Configuración y alcance", "",
        "RTX 3070 de 8 GB; aproximadamente 16 GB de RAM en Windows y 7,72 GiB disponibles para Docker/WSL2. "
        "vLLM 0.10.2 con Qwen2.5-3B-Instruct-AWQ, kernel AWQ-Marlin, float16, contexto 4096, "
        "salida máxima 1024, temperatura 0, una generación simultánea y presupuesto GPU 75 %. "
        "E5-large opera en CPU y pgvector realiza búsqueda exacta top-4.", "",
        "Se prepararon 120 consultas (60 desarrollo y 60 validación) y 24 preguntas de recuperación. "
        "Esta primera ejecución utiliza los diez escenarios iniciales de desarrollo, con las seis categorías, "
        "combinaciones, repeticiones e historial. No se ejecutó validación reservada. "
        "Cada configuración tiene un calentamiento previo y una sola pasada: estas muestras no permiten "
        "concluir capacidad sostenida ni generalización.", "",
        "Corpus oficial: 11 unidades legislativas, divididas en 12 fragmentos del índice activo. "
        "Las disposiciones reformadas se extraen de la Ley 21.719, con su versión XML real y estado temporal; "
        "el servicio XML de BCN no entregó un consolidado futuro de la Ley 19.628. "
        "Los localizadores, hashes, fuentes y revisiones están en `corpus/manifest.json` y `models.lock.json`.", "",
        "## Comprobaciones técnicas", "",
        "- Backend: 76 pruebas automatizadas aprobadas; una advertencia de deprecación de TestClient/httpx.",
        "- Frontend: batería de contratos offline aprobada; no se modificó la interfaz.",
        "- Docker reconoce la GPU y vLLM carga el modelo; E5 y PostgreSQL están disponibles.",
        "- La ingesta repetida conserva el mismo identificador de índice y los 12 fragmentos.",
        "- Readiness interno verificado. Entrada local mediante proxy en `127.0.0.1:8082`.",
        "- Conexión directa del gateway a 1.1.1.1:443 rechazada con código 101 (sin ruta). "
        "Es una comprobación puntual, además del aislamiento definido en Compose.",
        "- Fallos de esquema, offsets, referencias, servicios, timeout y auditoría se prueban con dobles controlados; "
        "no habilitan envío. Eso no garantiza que el modelo detecte toda PII o toda inyección.", "",
        "## Pruebas reales de las tres acciones", "",
        "| Acción esperada | HTTP esperado | HTTP observado | Acción recibida | Tiempo (s) |",
        "|---|---:|---:|---|---:|"]
    for s in smoke:
        lineas.append(f'| {s["accion_esperada"]} | {s["esperado"]} | {s["estado"]} | {s["accion"] or s["codigo"]} | {s["tiempo_ms"]/1000:.3f} |')
    lineas += ["", "Una detención técnica (503) no es un bloqueo decidido por el SLM. "
        "Una seudonimización requiere además la acción esperada: HTTP 200 por sí solo no acredita protección.", "",
        "## Comparación medida", "",
        "Detección compara spans y categorías exactos; no transmite al proveedor. "
        "Flujo ejecuta la API ASGI real, validación, auditoría cifrada, proveedor espía simulado y posprocesamiento. "
        "Su latencia excluye la conexión TCP y el proxy; la prueba anterior sí los incluye. "
        "Los fallos técnicos cuentan como omisiones en detección y se informan separadamente de bloqueos.", "",
        "| Nivel / variante | Concurrencia | n | Fallos técnicos | F2 micro | p50 (s) | p95 (s) | Transmitidas | Aciertos de acción |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for f in filas:
        lineas.append(f'| {f["nivel"]}/{f["modo"]} | {f["concurrencia"]} | {f["n"]} | {f["errores"]} | '
            f'{numero(f["micro"]["f2"])} | {f["p50_ms"]/1000:.3f} | {f["p95_ms"]/1000:.3f} | '
            f'{f["transmitidas"] if f["nivel"] == "flujo" else "—"} | {f["aciertos_accion"] if f["nivel"] == "flujo" else "—"} |')
    recall = filas[0]["recall4"]
    lineas += ["", f"Recall@4 documental: **{numero(recall)}**, sobre las doce preguntas de desarrollo. "
        "Se considera acierto recuperar un fragmento del artículo/letra esperado. "
        "Son preguntas jurídicas directas, distintas de las consultas empresariales analizadas por el gateway; "
        "no mide pertinencia de las fuentes en esas decisiones, de la justificación ni corrección jurídica.", "",
        "## Exposición y errores", ""]
    for f in filas:
        if f["nivel"] == "flujo":
            exposiciones = sum(s["apariciones_expuestas"] or 0 for s in f["muestras"])
            lineas.append(f'- Concurrencia {f["concurrencia"]}: {f["transmitidas"]} consultas transmitidas, '
                f'{f["bloqueos"]} bloqueadas por decisión, {f["errores"]} fallos técnicos y '
                f'{exposiciones} apariciones literales anotadas aún visibles en los envíos.')
    fallos = collections.Counter()
    for p in RESULTS.glob("flujo-*.events.jsonl"):
        for l in p.read_text().splitlines():
            e = json.loads(l)["evento"]
            if e.get("fase") == "fallo_analisis":
                fallos[e["motivo"]] += 1
    lineas += ["", "Códigos de fallo del flujo (incluyen calentamiento): " +
               (", ".join(f"`{k}`: {v}" for k,v in sorted(fallos.items())) or "sin fallos de análisis registrados"), "",
        "La exposición se estima por coincidencia literal de valores anotados y solo sobre consultas enviadas. "
        "No mide inferencia ni reidentificación. Cero envíos no implica protección útil y no permite definir una tasa "
        "de exposición sobre transmisiones. En esta ejecución, el único envío de cada configuración fue un control negativo sin PII; "
        "por ello cero exposición no demuestra eficacia del tratamiento.", "", "## Recursos observados", ""]
    gpu, uso_gpu, memoria, cpu = [], [], collections.defaultdict(list), collections.defaultdict(list)
    for path in sorted(RESULTS.glob("recursos*.jsonl")):
        for l in path.read_text().splitlines():
            r = json.loads(l)
            try:
                gpu.append(float(r["gpu"].split(",")[0]))
                uso_gpu.append(float(r["gpu"].split(",")[1]))
            except (ValueError, TypeError, KeyError): pass
            for d in (r.get("docker") or "").splitlines():
                try:
                    d = json.loads(d)
                    m = re.match(r"([\d.]+)([A-Za-z]+)",d["MemUsage"].split("/")[0].strip())
                    if m:
                        memoria[d["Name"]].append(float(m[1])*{"GiB":1024,"MiB":1,"KiB":1/1024,"B":1/1048576}[m[2]])
                    cpu[d["Name"]].append(float(d["CPUPerc"].rstrip("%")))
                except (ValueError, KeyError): pass
    if gpu:
        lineas += [f"VRAM total observada: media {statistics.mean(gpu):.0f} MiB, máximo {max(gpu):.0f} MiB. "
                   "Incluye otras cargas del escritorio; no es consumo atribuible exclusivamente al modelo.", ""]
    if uso_gpu:
        lineas += [f"Utilización GPU media {statistics.mean(uso_gpu):.1f} %, máximo muestreado {max(uso_gpu):.1f} %.", ""]
    for nombre, xs in sorted(memoria.items()):
        cs = cpu[nombre]
        lineas.append(f'- `{nombre}`: RAM media {statistics.mean(xs):.0f} MiB; máximo muestreado {max(xs):.0f} MiB. '
                      f'CPU media {statistics.mean(cs):.1f} %; máximo {max(cs):.1f} %.')
    lineas += ["", "Muestreo aproximadamente cada diez segundos; los máximos pueden omitir picos breves. "
        "No se midió energía.", "", "## Criterio de cierre y siguiente trabajo", "",
        "La infraestructura, el RAG, los contratos y la instrumentación quedan disponibles para continuar pruebas. "
        "La configuración actual del SLM no se acepta para el flujo funcional: hubo nueve fallos técnicos de diez consultas "
        "en cada nivel de concurrencia. El detector híbrido no mejoró el F2 de REGEX en este lote y añadió latencia. "
        "Las pruebas automatizadas no sustituyen la evaluación del modelo. No se acredita protección integral ni cumplimiento legal.", "",
        "Antes de ampliar las pruebas: revisar anotaciones y cada fallo de extracción/coherencia, contrastar "
        "simplificación del contrato o un modelo candidato con mayor capacidad, y usar exclusivamente desarrollo "
        "para ajustar. Después ejecutar los 60 casos completos de desarrollo y reservar validación para una "
        "configuración cerrada. Restitución, proveedor real y taxonomía completa siguen en el hito posterior.", "",
        "Evidencias detalladas y mediciones por categoría: `results/` (local, ignorado por Git). "
        "El conjunto reservado permanece sin ejecutar. Las instrucciones de reproducción están en `../README-pilot.md`.", ""]
    (ROOT / "pilot/REPORT.md").write_text("\n".join(lineas),encoding="utf-8")
    print("Reporte generado con doce configuraciones medidas.")


if __name__ == "__main__":
    main()
