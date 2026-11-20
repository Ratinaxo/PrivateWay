"""Banco de flujo por la API ASGI real, con proveedor espía exclusivamente simulado."""
import secrets
import httpx
from backend.gateway.api import create_app
from backend.gateway.audit import AuditoriaArchivo
from backend.gateway.config import Configuracion, RutaModelo
from backend.gateway.providers import ProveedorSimulado


class BancoFlujo:
    def __init__(self, pipeline, archivo):
        self.decisiones, self.solicitudes, self.envios = {}, {}, {}
        banco = self
        class Captura:
            listo = True
            async def analizar(self, solicitud, contexto):
                banco.solicitudes[id(solicitud)] = contexto.id_evento
                d = await pipeline.analizar(solicitud, contexto)
                banco.decisiones[contexto.id_evento] = d
                return d
            async def procesar_respuesta(self, *args):
                return await pipeline.procesar_respuesta(*args)
        class Espia(ProveedorSimulado):
            async def completar(self, modelo, mensajes, solicitud):
                banco.envios[banco.solicitudes[id(solicitud)]] = mensajes
                return await super().completar(modelo, mensajes, solicitud)
        self.token = secrets.token_urlsafe(32)
        app = create_app(config=Configuracion(tokens_cliente=(self.token,),
            rutas={"pw-simulado":RutaModelo("simulado","demo")}), pipeline=Captura(),
            auditoria=AuditoriaArchivo(archivo), adaptadores={"simulado":Espia()})
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://piloto")

    async def ejecutar(self, solicitud):
        r = await self.client.post("/api/v1/secure-chat", json=solicitud.model_dump(),
                                   headers={"Authorization":"Bearer "+self.token})
        evento = r.headers.get("X-Gateway-Event-ID")
        d = self.decisiones.pop(evento, None)
        enviado = self.envios.pop(evento, None)
        self.solicitudes = {k:v for k,v in self.solicitudes.items() if v != evento}
        error = r.json().get("error",{}).get("code") if r.status_code not in (200,403) else None
        return d, error, enviado

    async def cerrar(self):
        await self.client.aclose()
