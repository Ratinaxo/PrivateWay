"""Reproduce la exclusión requerida por tokenizers sin cargar pesos ni Torch."""
import concurrent.futures
import importlib.util
from pathlib import Path
import sys
import threading
import time
import types


def test_tokenizer_y_encode_comparten_la_misma_exclusion(monkeypatch):
    stub=types.ModuleType("sentence_transformers")
    stub.SentenceTransformer=object
    monkeypatch.setitem(sys.modules,"sentence_transformers",stub)
    path=Path(__file__).resolve().parents[2]/"Model/embeddings/app.py"
    spec=importlib.util.spec_from_file_location("embeddings_prueba",path)
    app=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app)
    ocupado=threading.Lock()
    class Tokenizer:
        def __call__(self,texto,**kwargs):
            if not ocupado.acquire(blocking=False):
                raise RuntimeError("Already borrowed")
            try:
                time.sleep(.001)
                return dict(input_ids=[1]*len(texto),offset_mapping=[(i,i+1) for i in range(len(texto))])
            finally:
                ocupado.release()
    class Modelo:
        tokenizer=Tokenizer()
        def encode(self,textos,**kwargs):
            for t in textos:
                self.tokenizer(t)
            return types.SimpleNamespace(tolist=lambda:[[1.0]+[0.0]*1023 for _ in textos])
    app.model=Modelo()
    monkeypatch.setenv("PRIVATEWAY_EMBEDDINGS_TOKEN","token-de-prueba")
    def solicitud(i):
        if i%2:
            return app.segmentos(app.Texto(texto=f"consulta {i}"),"Bearer token-de-prueba")
        return app.encode(app.Entrada(textos=[f"consulta {i}"],tipo="query"),"Bearer token-de-prueba")
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
        resultados=list(pool.map(solicitud,range(100)))
    assert len(resultados) == 100
