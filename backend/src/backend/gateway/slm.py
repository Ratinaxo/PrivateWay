"""Cliente de inferencia interna. No usa los adaptadores de destino externo."""
import json
import os
from pathlib import Path
import httpx


class ClienteVLLM:
    def __init__(self, *, url=None, token=None, modelo=None, contexto=None):
        self.url = url or os.environ["PRIVATEWAY_SLM_URL"]
        self.token = token or os.environ["PRIVATEWAY_SLM_TOKEN"]
        self.modelo = modelo or os.environ.get("PRIVATEWAY_SLM_MODEL", "privateway-slm")
        self.contexto = contexto or int(os.environ.get("PRIVATEWAY_SLM_CONTEXT", "4096"))
        lock = Path(os.environ.get("PRIVATEWAY_MODELS_LOCK", "/pilot/models.lock.json"))
        self.revision = "no_registrada"
        if lock.exists():
            self.revision = next(m["revision"] for m in json.loads(lock.read_text()) if m["carpeta"] == "qwen")

    def cliente(self):
        return httpx.AsyncClient(base_url=self.url, timeout=120, trust_env=False,
                                 headers={"Authorization": f"Bearer {self.token}"})

    async def comprobar(self):
        async with self.cliente() as c:
            r = await c.get("/v1/models", timeout=5)
            r.raise_for_status()
            return any(m["id"] == self.modelo for m in r.json()["data"])

    async def juzgar(self, instruccion, entrada, esquema):
        mensajes = [{"role": "system", "content": instruccion},
                    {"role": "user", "content": json.dumps(entrada, ensure_ascii=False)}]
        async with self.cliente() as c:
            cuenta = await c.post("/tokenize", json={"model": self.modelo, "messages": mensajes,
                                                    "add_generation_prompt": True})
            cuenta.raise_for_status()
            if cuenta.json()["count"] + 1024 > self.contexto:
                raise ValueError("CONTEXTO_EXCEDIDO")
            r = await c.post("/v1/chat/completions", json={
                "model": self.modelo, "messages": mensajes, "temperature": 0,
                "max_tokens": 1024, "stream": False,
                "response_format": {"type": "json_schema", "json_schema": {
                    "name": "juicio", "strict": True, "schema": esquema}}})
            r.raise_for_status()
            choice = r.json()["choices"][0]
            if choice["finish_reason"] != "stop":
                raise ValueError("SALIDA_INCOMPLETA")
            return choice["message"]["content"]
