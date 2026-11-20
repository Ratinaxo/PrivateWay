"""Recuperación exacta, corpus inmutable por versión y activación transaccional."""
from __future__ import annotations
import asyncio
import json
import math
import os
from pathlib import Path
import httpx
import psycopg

_LOTE_EMBEDDINGS_INGESTA = 32


def conexion():
    return psycopg.connect(host=os.environ["PRIVATEWAY_DB_HOST"],
                          port=int(os.environ.get("PRIVATEWAY_DB_PORT", "5432")),
                          user="privateway", dbname="privateway",
                          password=os.environ["PRIVATEWAY_DB_PASSWORD"], connect_timeout=5)


def vector(v):
    if len(v) != 1024 or not all(math.isfinite(float(x)) for x in v):
        raise ValueError("vector invalido")
    if not 0.99 <= sum(float(x) ** 2 for x in v) <= 1.01:
        raise ValueError("vector no normalizado")
    return "[" + ",".join(str(float(x)) for x in v) + "]"


async def codificar_en_lotes(embeddings, textos, tipo):
    """Codifica pasajes en peticiones acotadas y conserva el orden de entrada."""
    vectores = []
    for inicio in range(0, len(textos), _LOTE_EMBEDDINGS_INGESTA):
        lote = textos[inicio:inicio + _LOTE_EMBEDDINGS_INGESTA]
        resultado = await embeddings.codificar(lote, tipo)
        if not isinstance(resultado, (list, tuple)) or len(resultado) != len(lote):
            raise ValueError("embeddings incompletos")
        vectores.extend(resultado)
    return vectores


class EmbeddingsHTTP:
    def __init__(self):
        self.url = os.environ["PRIVATEWAY_EMBEDDINGS_URL"]
        self.token = os.environ["PRIVATEWAY_EMBEDDINGS_TOKEN"]

    async def llamar(self, ruta, datos=None):
        async with httpx.AsyncClient(base_url=self.url, timeout=120, trust_env=False,
                                    headers={"Authorization": f"Bearer {self.token}"}) as c:
            r = await c.get(ruta, timeout=5) if datos is None else await c.post(ruta, json=datos)
            r.raise_for_status()
            return r.json()

    async def comprobar(self):
        return (await self.llamar("/ready"))["ready"]

    async def codificar(self, textos, tipo):
        r = await self.llamar("/encode", {"textos": textos, "tipo": tipo})
        for v in r["vectores"]:
            vector(v)
        if len(r["vectores"]) != len(textos):
            raise ValueError("embeddings incompletos")
        return r["vectores"]

    async def segmentos(self, texto):
        return (await self.llamar("/segments", {"texto": texto}))["segmentos"]


class RecuperadorPostgres:
    # Las señales son intencionalmente categóricas. Nunca se incorpora el valor
    # detectado por REGEX a una consulta adicional ni a la traza de recuperación.
    _CONSULTAS_CATEGORIA = {
        "run": "identificador personal RUN cédula de identidad persona identificable",
        "correo": "dato personal dirección de correo electrónico identificador",
        "telefono": "dato personal número telefónico identificador",
        "tarjeta": "dato personal número de tarjeta de pago identificable",
        "patente": "dato personal placa patente vehículo identificable",
        "persona": "dato personal persona identificada o identificable",
        "direccion": "dato personal domicilio dirección de una persona",
        "identificador": "datos personales combinación de atributos medios razonables de identificación",
        "origen_etnico": "dato personal sensible origen étnico o racial",
        "afiliacion": "dato personal sensible afiliación política sindical o gremial",
        "socioeconomico": "dato personal sensible situación socioeconómica",
        "convicciones": "dato personal sensible convicciones ideológicas filosóficas creencias religiosas",
        "salud": "dato personal sensible relativo a la salud",
        "perfil_biologico": "dato personal sensible genético proteómico metabólico muestras biológicas",
        "biometrico": "dato personal sensible biométrico identificación única",
        "sexualidad": "dato personal sensible vida sexual orientación sexual identidad de género",
        "menor_de_edad": "categoría especial niño niña adolescente edad consentimiento titular",
        "geolocalizacion": "categoría especial datos de geolocalización coordenadas ubicación en tiempo real",
        "obligaciones": "datos relativos a obligaciones económicas financieras bancarias comerciales",
        "infracciones": "datos relativos a infracciones penales civiles administrativas disciplinarias",
    }
    _CONSULTAS_SUBCATEGORIA = {
        "origen étnico": "origen étnico",
        "origen racial": "origen racial",
        "afiliación política": "afiliación política",
        "afiliación sindical": "afiliación sindical",
        "afiliación gremial": "afiliación gremial",
        "situación socioeconómica": "situación socioeconómica",
        "convicciones ideológicas": "convicciones ideológicas",
        "convicciones filosóficas": "convicciones filosóficas",
        "creencias religiosas": "creencias religiosas",
        "datos relativos a la salud": "datos relativos a la salud",
        "datos genéticos": "datos genéticos",
        "datos proteómicos": "datos proteómicos",
        "datos metabólicos": "datos metabólicos",
        "muestras biológicas": "muestras biológicas",
        "huella digital": "huella digital biométrica",
        "iris": "iris biométrico",
        "rasgos de la mano": "rasgos de la mano biométricos",
        "rasgos faciales": "rasgos faciales biométricos",
        "voz": "voz biométrica",
        "características conductuales": "características conductuales biométricas",
        "vida sexual": "vida sexual",
        "orientación sexual": "orientación sexual",
        "identidad de género": "identidad de género",
    }

    def __init__(self, embeddings):
        self.embeddings = embeddings

    async def versiones(self):
        def leer():
            with conexion() as c:
                row = c.execute("SELECT id, metadata FROM pw_rag_indices WHERE activo").fetchone()
                if row is None:
                    raise ValueError("sin corpus activo")
                return {"indice": row[0], **row[1]}
        return await asyncio.to_thread(leer)

    async def comprobar(self):
        version = await self.versiones()
        actual = await self.embeddings.llamar("/ready")
        return bool(actual["ready"] and actual == version["embeddings"])

    async def buscar(self, mensajes, regex):
        version = await self.versiones()
        actual = await self.embeddings.llamar("/ready")
        if actual != version["embeddings"]:
            raise ValueError("encoder distinto al indice")
        textos = []
        for m in mensajes:
            # Mantener la consulta original completa (en segmentos si es larga).
            textos.extend(await self.embeddings.segmentos(m.content))
        # Aportar contexto legislativo a partir de la categoría detectada, sin
        # copiar valores sensibles ni offsets del hallazgo a los embeddings.
        categorias = set()
        subcategorias = set()
        for h in regex or []:
            categoria = getattr(h, "categoria", None)
            if categoria is None and isinstance(h, dict):
                categoria = h.get("categoria")
            categoria = getattr(categoria, "value", categoria)
            if categoria in self._CONSULTAS_CATEGORIA:
                categorias.add(categoria)
                subcategoria = h.get("subcategoria") if isinstance(h, dict) else getattr(h, "subcategoria", None)
                if subcategoria in self._CONSULTAS_SUBCATEGORIA:
                    subcategorias.add(subcategoria)
        textos.extend(self._CONSULTAS_CATEGORIA[c] for c in sorted(categorias))
        textos.extend(self._CONSULTAS_SUBCATEGORIA[c] for c in sorted(subcategorias))
        if not textos:
            return []
        vectores = await self.embeddings.codificar(textos, "query")
        def buscar():
            candidatos = {}
            with conexion() as c:
                for v in vectores:
                    for fid, texto, meta, distancia in c.execute("""
                        SELECT id, texto, metadata, embedding <=> %s::vector AS d
                        FROM pw_rag_fragmentos WHERE indice = %s
                        ORDER BY d, id LIMIT 4""", (vector(v), version["indice"])):
                        if fid not in candidatos or distancia < candidatos[fid][0]:
                            candidatos[fid] = (distancia, {**meta, "id": fid, "texto": texto,
                                                           "indice": version["indice"]})
            return [x[1] for x in sorted(candidatos.values(), key=lambda x: (x[0], x[1]["id"]))[:4]]
        return await asyncio.to_thread(buscar)


async def ingerir(manifiesto: Path):
    import hashlib
    datos = json.loads(manifiesto.read_text(encoding="utf-8"))
    emb = EmbeddingsHTTP()
    metadata = await emb.llamar("/ready")
    if not metadata["ready"]:
        raise ValueError("embeddings no listos")
    doc_ids = [d["id"] for d in datos["documentos"]]
    if len(doc_ids) != len(set(doc_ids)):
        raise ValueError("documentos duplicados")
    bloques = []
    for f in datos["fragmentos"]:
        if f["documento"] not in doc_ids:
            raise ValueError("documento inexistente")
        for n, segmento in enumerate(await emb.segmentos(f["texto"])):
            bloques.append(dict(id=f'{f["id"]}_{n}', texto=segmento,
                                metadata={k: v for k, v in f.items() if k != "texto"}))
    if not bloques or len({f["id"] for f in bloques}) != len(bloques):
        raise ValueError("corpus vacio o duplicado")
    vectores = await codificar_en_lotes(
        emb, [f["texto"] for f in bloques], "passage")
    version = hashlib.sha256(json.dumps({"datos": datos, "encoder": metadata}, sort_keys=True).encode()).hexdigest()
    sql = Path(__file__).with_name("rag_schema.sql").read_text(encoding="utf-8")
    def guardar():
        with conexion() as c:
            c.execute(sql)
            c.execute("SELECT pg_advisory_xact_lock(714719)")
            c.execute("INSERT INTO pw_rag_indices(id, metadata) VALUES (%s,%s::jsonb) ON CONFLICT DO NOTHING",
                      (version, json.dumps({"embeddings": metadata, "corpus": datos["version"]})))
            for d in datos["documentos"]:
                c.execute("INSERT INTO pw_rag_documentos VALUES (%s,%s,%s::jsonb) ON CONFLICT DO NOTHING",
                          (version, d["id"], json.dumps(d)))
            for f, v in zip(bloques, vectores):
                c.execute("INSERT INTO pw_rag_fragmentos VALUES (%s,%s,%s,%s::jsonb,%s::vector) ON CONFLICT DO NOTHING",
                          (version, f["id"], f["texto"], json.dumps(f["metadata"]), vector(v)))
            total = c.execute("SELECT count(*) FROM pw_rag_fragmentos WHERE indice=%s", (version,)).fetchone()[0]
            if total != len(bloques):
                raise ValueError("ingesta incompleta")
            c.execute("UPDATE pw_rag_indices SET activo=false WHERE activo")
            c.execute("UPDATE pw_rag_indices SET activo=true WHERE id=%s", (version,))
    await asyncio.to_thread(guardar)
    return {"indice": version, "fragmentos": len(bloques)}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("manifiesto", type=Path)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(ingerir(args.manifiesto))))
