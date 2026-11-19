"""Comprueba el almacén usando exclusivamente conversaciones sintéticas."""
import asyncio
import time
import uuid
import secrets
from tempfile import TemporaryDirectory
from pathlib import Path

import httpx

from .api import create_app
from .audit import AuditoriaArchivo
from .config import Configuracion, RutaModelo
from .contracts import Accion, Mensaje, RespuestaProveedor
from .conversations import ConversacionesPostgres, HistorialNoDisponible
from .pipeline import DecisionValidada, Restitucion
from .regex_pipeline import PipelineRegex


async def comprobar_api(store, owner, primera, segunda):
    """Verifica el puente API/almacén aislando la inferencia del modelo."""
    marca = "[PW_PERSONA_" + "d" * 32 + "]"
    nombre = "Nombre sintético"

    class PipelinePrueba(PipelineRegex):
        async def analizar(self, solicitud, contexto):
            if solicitud.messages[0].content != nombre:
                return await super().analizar(solicitud, contexto)
            return DecisionValidada(
                Accion.SEUDONIMIZAR, "PRUEBA", [Mensaje(role="user", content=marca)],
                True, True, restitucion=Restitucion(contexto, {marca: nombre}),
            )

    class Eco:
        llamadas = 0

        async def completar(self, modelo, mensajes, solicitud):
            self.llamadas += 1
            assert all(nombre not in m.content for m in mensajes)
            return RespuestaProveedor(content=marca)

    import os

    token = secrets.token_urlsafe(32)
    eco = Eco()
    with TemporaryDirectory() as directorio:
        app = create_app(
            config=Configuracion((token,), {"pw-simulado": RutaModelo("simulado", "demo")}),
            pipeline=PipelinePrueba(), adaptadores={"simulado": eco},
            auditoria=AuditoriaArchivo(Path(directorio) / "events.jsonl"),
            conversaciones=store,
        )
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as cliente:
            headers = {"Authorization": "Bearer " + os.environ["GATEWAY_HISTORY_TOKEN"],
                       "X-PrivateWay-User-Id": owner}
            assert (await cliente.head(f"/api/v1/conversations/{primera}", headers=headers)).status_code == 204
            headers["X-PrivateWay-User-Id"] = str(uuid.uuid4())
            assert (await cliente.head(f"/api/v1/conversations/{primera}", headers=headers)).status_code == 404
            for chat, texto, esperado in [
                (primera, nombre, nombre),
                (primera, "Continúa", nombre),
                (segunda, "Continúa", marca),
            ]:
                r = await cliente.post("/api/v1/secure-chat", headers={
                    "Authorization": f"Bearer {token}",
                    "X-PrivateWay-History-Auth": "Bearer " + os.environ["GATEWAY_HISTORY_TOKEN"],
                    "X-PrivateWay-User-Id": owner,
                    "X-PrivateWay-Conversation-Id": chat,
                }, json={"model": "pw-simulado", "messages": [{"role": "user", "content": texto}]})
                assert r.status_code == 200, r.status_code
                assert r.json()["respuesta"]["choices"][0]["message"]["content"] == esperado
    assert eco.llamadas == 3


async def comprobar():
    store = ConversacionesPostgres.desde_entorno()
    if store is None:
        raise RuntimeError("Configurar el almacén de conversaciones")
    owner, otro, primera, segunda = (str(uuid.uuid4()) for _ in range(4))
    uno, dos = (f"[PW_PERSONA_{c * 32}]" for c in ("a", "b"))
    valor = "Nombre sintético"
    ahora = time.time_ns() // 1_000_000
    try:
        for usuario, chat in [(owner, primera), (owner, segunda), (otro, primera)]:
            await store.guardar(usuario, chat, dict(
                id=chat, title="Prueba sintética", providerId="simulado", modelId="pw-simulado",
                createdAt=ahora, updatedAt=ahora, messages=[],
            ))
        await comprobar_api(store, owner, primera, segunda)
        await asyncio.gather(
            store.guardar_marcadores(owner, primera, {uno: valor}),
            store.guardar_marcadores(owner, primera, {dos: valor}),
        )
        assert await store.restituir(owner, primera, f"{uno} {dos} {uno}") == " ".join([valor] * 3)
        assert await store.restituir(owner, segunda, uno) == uno
        assert await store.restituir(otro, primera, uno) == uno
        alterado = uno.replace("a]", "c]")
        assert await store.restituir(owner, primera, alterado) == alterado
        with store._conn() as conn:
            fila = conn.execute(
                "SELECT content FROM privateway_markers WHERE owner=%s AND chat_id=%s AND marker=%s",
                (owner, primera, uno),
            ).fetchone()
            assert valor.encode() not in bytes(fila[0])
            conn.execute(
                "UPDATE privateway_markers SET expires_at=now() WHERE owner=%s AND chat_id=%s AND marker=%s",
                (owner, primera, uno),
            )
        assert await store.restituir(owner, primera, uno) == uno
        await store.eliminar(owner, primera)
        assert await store.restituir(owner, primera, dos) == dos
        try:
            await store.guardar_marcadores(owner, primera, {uno: valor})
        except HistorialNoDisponible:
            pass
        else:
            raise AssertionError("Se permitió escribir en una conversación eliminada")
    finally:
        for usuario, chat in [(owner, primera), (owner, segunda), (otro, primera)]:
            await store.eliminar(usuario, chat)
    print("API y PostgreSQL: turnos, cifrado, concurrencia, aislamiento, expiración y borrado verificados.")


if __name__ == "__main__":
    asyncio.run(comprobar())
