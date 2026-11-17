"""E5 local CPU: no truncamiento silencioso, ni logs de entradas."""
import os
import secrets
import threading
from contextlib import asynccontextmanager
from typing import Literal
from fastapi import FastAPI, Header, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict
from sentence_transformers import SentenceTransformer

model = None
lock = threading.Lock()


@asynccontextmanager
async def lifespan(app):
    global model
    model = SentenceTransformer(os.environ.get("EMBEDDINGS_MODEL", "/models/e5"), device="cpu")
    model.max_seq_length = 512
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)


def autorizado(token):
    esperado = os.environ["PRIVATEWAY_EMBEDDINGS_TOKEN"]
    if not secrets.compare_digest(token or "", "Bearer " + esperado):
        raise HTTPException(401, "NO_AUTORIZADO")


@app.exception_handler(RequestValidationError)
async def validacion(request, exc):
    return JSONResponse(status_code=422, content={"error": "SOLICITUD_INVALIDA"})


class Entrada(BaseModel):
    model_config = ConfigDict(extra="forbid")
    textos: list[str] = Field(min_length=1, max_length=512)
    tipo: Literal["query", "passage"]


class Texto(BaseModel):
    texto: str = Field(min_length=1, max_length=121000)


@app.get("/ready")
def ready(authorization: str | None = Header(default=None)):
    autorizado(authorization)
    return {"ready": model is not None, "modelo": "intfloat/multilingual-e5-large",
            "revision": os.environ["PRIVATEWAY_E5_REVISION"], "dimension": 1024,
            "normalizacion": True, "max_tokens": 512}


@app.post("/segments")
def segmentos(data: Texto, authorization: str | None = Header(default=None)):
    autorizado(authorization)
    # Offset mapping preserva caracteres del original. Reservar tokens para prefijo y especiales.
    # El tokenizer rápido comparte estado de padding/truncamiento con encode.
    with lock:
        tokens = model.tokenizer(data.texto, add_special_tokens=False, return_offsets_mapping=True)
    offsets = tokens["offset_mapping"]
    return {"segmentos": [data.texto[offsets[i][0]:offsets[min(i+447,len(offsets)-1)][1]]
                           for i in range(0, len(offsets), 448)] or [data.texto]}


@app.post("/encode")
def encode(data: Entrada, authorization: str | None = Header(default=None)):
    autorizado(authorization)
    textos = [f"{data.tipo}: {t}" for t in data.textos]
    with lock:
        if any(len(model.tokenizer(t)["input_ids"]) > 512 for t in textos):
            raise HTTPException(422, "ENTRADA_EXCEDE_512_TOKENS")
        vectores = model.encode(textos, batch_size=4, normalize_embeddings=True,
                                show_progress_bar=False).tolist()
    return {"vectores": vectores}
