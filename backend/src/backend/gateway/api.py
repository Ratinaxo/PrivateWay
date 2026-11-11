"""API HTTP del gateway: REGEX -> política de seudonimización -> adaptador."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
import os
import re
import secrets
import time
import uuid
from urllib.parse import unquote

from fastapi import FastAPI, Header, Request, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .audit import AuditoriaArchivo, AuditoriaNoConfigurada, AuditoriaNoDisponible
from .audit_content import ContenidoAuditoria
from .conversations import ConversacionesPostgres, HistorialNoDisponible, validar_conversacion, _uuid
from .config import Configuracion, proveedores_desde_entorno
from .contracts import Accion, SolicitudChat
from .pipeline import AnalisisNoDisponible, ContextoEjecucion
from .providers import ProveedorNoDisponible

_CODIGO = re.compile(r"^[A-Z0-9_]{2,64}$")


def error(codigo: str, estado: int, evento: str | None = None) -> JSONResponse:
    mensajes = {
        "NO_AUTORIZADO": "Credencial del gateway ausente o inválida.",
        "SOLICITUD_INVALIDA": "Esquema de solicitud no admitido.",
        "MODELO_NO_AUTORIZADO": "Modelo no disponible en el catálogo corporativo.",
        "ANALISIS_NO_DISPONIBLE": "Pipeline de protección no habilitado.",
        "POLITICA_BLOQUEA": "La política de protección impide transmitir esta solicitud.",
        "FALLO_VALIDACION": "No se pudo validar de forma segura la decisión.",
        "AUDITORIA_NO_DISPONIBLE": "No se puede garantizar la trazabilidad requerida.",
        "PROVEEDOR_NO_DISPONIBLE": "No se pudo completar la operación con el proveedor.",
        "FALLO_POSPROCESAMIENTO": "No se pudo validar o restituir la respuesta de forma segura.",
        "HISTORIAL_NO_DISPONIBLE": "No se pudo acceder a las conversaciones almacenadas.",
    }
    cabeceras = {"X-Gateway-Event-ID": evento} if evento else {}
    return JSONResponse(
        status_code=estado,
        headers=cabeceras,
        content={"error": {"type": "gateway_error", "code": codigo, "message": mensajes[codigo]}},
    )


def _token_recibido(autorizacion: str | None) -> str:
    prefijo = "Bearer "
    return autorizacion[len(prefijo):] if autorizacion and autorizacion.startswith(prefijo) else ""


def _token_autorizado(recibido: str, config: Configuracion) -> bool:
    return any(secrets.compare_digest(recibido, token) for token in config.tokens_cliente)


def create_app(*, config=None, pipeline=None, auditoria=None, adaptadores=None) -> FastAPI:
    config = config if config is not None else Configuracion.desde_entorno()
    if auditoria is None:
        ruta_auditoria = os.environ.get("GATEWAY_AUDIT_FILE")
        auditoria = AuditoriaArchivo(ruta_auditoria) if ruta_auditoria else AuditoriaNoConfigurada()
    adaptadores = adaptadores if adaptadores is not None else proveedores_desde_entorno()
    if pipeline is None:
        from .regex_pipeline import PipelineRegex
        pipeline = PipelineRegex()

    # Claves opcionales hasta completar configuración del entorno de desarrollo.
    # Nunca guardar PII en el JSONL. La vista detallada usa cifrado separado.
    contenido_auditado = None
    if os.environ.get("GATEWAY_AUDIT_CONTENT_KEY"):
        contenido_auditado = ContenidoAuditoria(
            os.environ.get("GATEWAY_AUDIT_CONTENT_DIR", "/var/lib/privateway/audit/previews"),
            os.environ["GATEWAY_AUDIT_CONTENT_KEY"],
        )
    conversaciones = ConversacionesPostgres.desde_entorno()
    app = FastAPI(title="PrivateWay Gateway", docs_url=None, redoc_url=None)

    def token_interno(authorization: str | None, variable: str) -> bool:
        esperado = os.environ.get(variable, "")
        recibido = _token_recibido(authorization)
        return bool(esperado and recibido and
                    not any(secrets.compare_digest(esperado, t) for t in config.tokens_cliente) and
                    secrets.compare_digest(recibido, esperado))

    def actor_normalizado(identificador: str | None, nombre: str | None) -> tuple[str, str]:
        if not identificador or not _uuid(identificador):
            return ("", "servicio")
        nombre = unquote(nombre or identificador).strip()
        nombre = "".join(ch for ch in nombre if ch.isprintable() and ch not in "\r\n")[:100]
        return (identificador, nombre or identificador)

    async def historial_disponible(authorization: str | None, usuario: str | None):
        if not token_interno(authorization, "GATEWAY_HISTORY_TOKEN"):
            return error("NO_AUTORIZADO", 401)
        if not usuario or not _uuid(usuario):
            return error("SOLICITUD_INVALIDA", 422)
        if conversaciones is None:
            return error("HISTORIAL_NO_DISPONIBLE", 503)
        return None

    @app.get("/api/v1/conversations")
    async def listar_conversaciones(authorization: str | None = Header(default=None),
                                   x_privateway_user_id: str | None = Header(default=None)):
        fallo = await historial_disponible(authorization, x_privateway_user_id)
        if fallo: return fallo
        try:
            data = await conversaciones.listar(x_privateway_user_id)
            return JSONResponse(content={"conversations": data}, headers={"Cache-Control": "no-store"})
        except HistorialNoDisponible:
            return error("HISTORIAL_NO_DISPONIBLE", 503)

    @app.put("/api/v1/conversations/{id}")
    async def guardar_conversacion(id: str, request: Request, authorization: str | None = Header(default=None),
                                   x_privateway_user_id: str | None = Header(default=None)):
        fallo = await historial_disponible(authorization, x_privateway_user_id)
        if fallo: return fallo
        if not _uuid(id): return error("SOLICITUD_INVALIDA", 422)
        try:
            datos = await request.json()
            await conversaciones.guardar(x_privateway_user_id, id, datos)
            return JSONResponse(content={"ok": True}, headers={"Cache-Control": "no-store"})
        except (ValueError, TypeError):
            return error("SOLICITUD_INVALIDA", 422)
        except HistorialNoDisponible:
            return error("HISTORIAL_NO_DISPONIBLE", 503)

    @app.delete("/api/v1/conversations/{id}")
    async def eliminar_conversacion(id: str, authorization: str | None = Header(default=None),
                                   x_privateway_user_id: str | None = Header(default=None)):
        fallo = await historial_disponible(authorization, x_privateway_user_id)
        if fallo: return fallo
        if not _uuid(id): return error("SOLICITUD_INVALIDA", 422)
        try:
            await conversaciones.eliminar(x_privateway_user_id, id)
            return JSONResponse(content={"ok": True}, headers={"Cache-Control": "no-store"})
        except HistorialNoDisponible:
            return error("HISTORIAL_NO_DISPONIBLE", 503)

    @app.exception_handler(RequestValidationError)
    async def error_validacion(request: Request, exc: RequestValidationError):
        # Los errores de Pydantic pueden incluir el valor original del prompt.
        return error("SOLICITUD_INVALIDA", 422)

    @app.get("/health")
    def health():
        return {"alive": True}

    @app.get("/ready")
    def ready():
        def proveedor_preparado(adaptador):
            variable = getattr(adaptador, "api_key_env", None)
            return variable is None or bool(os.environ.get(variable))
        ok = bool(getattr(pipeline, "listo", False) and getattr(auditoria, "listo", False)
                  and all(r.proveedor in adaptadores and proveedor_preparado(adaptadores[r.proveedor])
                          for r in config.rutas.values()))
        return JSONResponse(status_code=200 if ok else 503, content={"ready": ok})

    @app.get("/api/v1/audit/events")
    async def eventos_auditoria(
        limit: int = Query(200, ge=1, le=200),
        authorization: str | None = Header(default=None),
    ):
        # Credencial separada del token de chat. Los usuarios finales acceden
        # únicamente a través del BFF, que verifica el rol admin en Keycloak.
        token_administrativo = os.environ.get("GATEWAY_AUDIT_READ_TOKEN", "")
        recibido = _token_recibido(authorization)
        # Impedir que una configuración accidental habilite la lectura de
        # bitácora con el token ordinario usado para enviar chats.
        if token_administrativo and any(secrets.compare_digest(token_administrativo, t)
                                       for t in config.tokens_cliente):
            return error("AUDITORIA_NO_DISPONIBLE", 503)
        if not token_administrativo or not recibido or not secrets.compare_digest(recibido, token_administrativo):
            return error("NO_AUTORIZADO", 401)
        lector = getattr(auditoria, "listar", None)
        if lector is None:
            return error("AUDITORIA_NO_DISPONIBLE", 503)
        try:
            resultado = await lector(limit)
            return JSONResponse(content=resultado, headers={"Cache-Control": "no-store"})
        except (AuditoriaNoDisponible, OSError):
            return error("AUDITORIA_NO_DISPONIBLE", 503)

    @app.get("/api/v1/audit/events/{evento}/preview")
    async def previsualizar_evento(evento: str, authorization: str | None = Header(default=None),
                                   x_privateway_auditor_id: str | None = Header(default=None),
                                   x_privateway_auditor_name: str | None = Header(default=None)):
        if not token_interno(authorization, "GATEWAY_AUDIT_READ_TOKEN"):
            return error("NO_AUTORIZADO", 401)
        if not re.fullmatch(r"evt_[a-f0-9]{32}", evento):
            return error("SOLICITUD_INVALIDA", 422)
        if contenido_auditado is None or not getattr(auditoria, "existe_evento", None):
            return JSONResponse(status_code=404, content={"error": {"code": "SIN_PREVISUALIZACION"}}, headers={"Cache-Control": "no-store"})
        try:
            if not await auditoria.existe_evento(evento):
                return JSONResponse(status_code=404, content={"error": {"code": "SIN_PREVISUALIZACION"}}, headers={"Cache-Control": "no-store"})
            vista = await contenido_auditado.leer(evento)
            if vista is None:
                return JSONResponse(status_code=404, content={"error": {"code": "SIN_PREVISUALIZACION"}}, headers={"Cache-Control": "no-store"})
            auditor_id, auditor_nombre = actor_normalizado(x_privateway_auditor_id, x_privateway_auditor_name)
            await auditoria.registrar({"fecha_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "evento": "evt_" + uuid.uuid4().hex, "fase": "consulta_previsualizacion",
               "evento_consultado": evento, "usuario_id": auditor_id, "usuario": auditor_nombre})
            return JSONResponse(content=vista, headers={"Cache-Control": "no-store, private", "Pragma": "no-cache"})
        except AuditoriaNoDisponible:
            return error("AUDITORIA_NO_DISPONIBLE", 503)

    async def procesar(cuerpo: SolicitudChat, autorizacion: str | None, extendida: bool,
                       actor_id: str | None = None, actor_nombre: str | None = None):
        evento = "evt_" + uuid.uuid4().hex
        recibida = _token_recibido(autorizacion)
        if not _token_autorizado(recibida, config):
            return error("NO_AUTORIZADO", 401)

        ruta = config.rutas.get(cuerpo.model)
        if ruta is None or ruta.proveedor not in adaptadores:
            return error("MODELO_NO_AUTORIZADO", 404, evento)

        contexto = ContextoEjecucion(
            id_evento=evento,
            referencia_credencial=hashlib.sha256(recibida.encode()).hexdigest()[:16],
        )
        try:
            decision = await pipeline.analizar(cuerpo, contexto)
        except AnalisisNoDisponible:
            return error("ANALISIS_NO_DISPONIBLE", 503, evento)
        except Exception:
            # No devolver excepciones con trozos del prompt.
            return error("FALLO_VALIDACION", 503, evento)

        if not decision.validacion_completa or not _CODIGO.fullmatch(decision.codigo_motivo):
            return error("FALLO_VALIDACION", 503, evento)
        if decision.accion not in (Accion.PERMITIR, Accion.SEUDONIMIZAR, Accion.BLOQUEAR):
            return error("FALLO_VALIDACION", 503, evento)
        if decision.accion != Accion.BLOQUEAR:
            if decision.mensajes_salida is None or len(decision.mensajes_salida) != len(cuerpo.messages):
                return error("FALLO_VALIDACION", 503, evento)
            if any(a.role != b.role for a, b in zip(decision.mensajes_salida, cuerpo.messages)):
                return error("FALLO_VALIDACION", 503, evento)
            if decision.accion == Accion.PERMITIR and decision.mensajes_salida != cuerpo.messages:
                return error("FALLO_VALIDACION", 503, evento)
            if decision.accion == Accion.SEUDONIMIZAR and not decision.cobertura_verificada:
                return error("FALLO_VALIDACION", 503, evento)

        # La acción cubre toda la solicitud. Los avisos y la bitácora
        # necesitan distinguir si realmente se alteró el mensaje más reciente.
        cambios = {
            "mensaje_actual_seudonimizado": (
                decision.mensajes_salida is not None and
                decision.mensajes_salida[-1].content != cuerpo.messages[-1].content
            ),
            "historial_seudonimizado": (
                decision.mensajes_salida is not None and
                any(nuevo.content != original.content
                    for nuevo, original in zip(decision.mensajes_salida[:-1], cuerpo.messages[:-1]))
            ),
        }
        usuario_id, usuario = actor_normalizado(actor_id, actor_nombre)
        registro = {
            "usuario_id": usuario_id, "usuario": usuario,
            "vista_disponible": "si" if contenido_auditado is not None else "no",
            "fecha_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "evento": evento, "alias": cuerpo.model, "proveedor": ruta.proveedor,
            "accion": decision.accion.value, "motivo": decision.codigo_motivo,
            "mensaje_actual": "si" if cambios["mensaje_actual_seudonimizado"] else "no",
            "historial": "si" if cambios["historial_seudonimizado"] else "no",
        }
        vista_preparada = {
            "evento": evento,
            "usuario": usuario,
            "mensajes": [
                {"indice": i + 1, "role": m.role,
                 "antes": m.content,
                 "despues": decision.mensajes_salida[i].content if decision.mensajes_salida is not None else None}
                for i, m in enumerate(cuerpo.messages)
            ],
            "respuesta": None,
        }
        try:
            if contenido_auditado is not None:
                await contenido_auditado.guardar(evento, vista_preparada)
            await auditoria.registrar({**registro, "fase": "preparada", "transmision": "no_iniciada"})
        except AuditoriaNoDisponible:
            return error("AUDITORIA_NO_DISPONIBLE", 503, evento)

        if decision.accion == Accion.BLOQUEAR:
            try:
                await auditoria.registrar({**registro, "fase": "completada", "transmision": "no_realizada"})
            except AuditoriaNoDisponible:
                return error("AUDITORIA_NO_DISPONIBLE", 503, evento)
            return error("POLITICA_BLOQUEA", 403, evento)

        try:
            respuesta = await adaptadores[ruta.proveedor].completar(
                ruta.modelo_externo, decision.mensajes_salida, cuerpo
            )
        except ProveedorNoDisponible as exc:
            # Estas categorías sólo se generan ANTES de iniciar la solicitud HTTP.
            no_enviada = {"CLAVE_NO_CONFIGURADA", "MODELO_INVALIDO", "ROL_NO_SOPORTADO", "MENSAJES_INVALIDOS"}
            transmision = "no_realizada" if exc.codigo in no_enviada else "desconocida"
            try:
                await auditoria.registrar({**registro, "fase": "completada", "transmision": transmision})
            except AuditoriaNoDisponible:
                pass
            return error("PROVEEDOR_NO_DISPONIBLE", 502, evento)
        except Exception:
            # Un timeout NO demuestra que el proveedor no recibió el prompt.
            try:
                await auditoria.registrar({**registro, "fase": "completada", "transmision": "desconocida"})
            except AuditoriaNoDisponible:
                pass
            return error("PROVEEDOR_NO_DISPONIBLE", 502, evento)

        try:
            final = await pipeline.procesar_respuesta(cuerpo, decision, respuesta, contexto)
            if not isinstance(final.content, str):
                raise AnalisisNoDisponible("restitución no validada")
        except Exception:
            # Aquí sí se confirmó respuesta del proveedor, pero falló la restitución local.
            try:
                await auditoria.registrar({**registro, "fase": "completada", "transmision": "respuesta_recibida_posprocesamiento_fallido"})
            except AuditoriaNoDisponible:
                pass
            return error("FALLO_POSPROCESAMIENTO", 503, evento)

        try:
            if contenido_auditado is not None:
                await contenido_auditado.guardar(evento, {
                    **vista_preparada,
                    "respuesta": {"antes": respuesta.content, "despues": final.content},
                })
            await auditoria.registrar({**registro, "fase": "completada", "transmision": "respuesta_recibida"})
        except AuditoriaNoDisponible:
            # Si se llegó aquí, la transmisión ya ocurrió. No afirmar que fue evitada.
            return error("AUDITORIA_NO_DISPONIBLE", 503, evento)

        respuesta_chat = {
            "id": "chatcmpl_" + uuid.uuid4().hex,
            "object": "chat.completion", "created": int(time.time()),
            "model": cuerpo.model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": final.content},
                "finish_reason": final.finish_reason,
            }],
        }
        if extendida:
            return JSONResponse(
                content={"respuesta": respuesta_chat,
                         "decision": {"accion": decision.accion.value,
                                      "codigo_motivo": decision.codigo_motivo,
                                      "evento": evento,
                                      **cambios}},
                headers={"X-Gateway-Event-ID": evento},
            )
        return JSONResponse(content=respuesta_chat, headers={"X-Gateway-Event-ID": evento})

    @app.get("/api/v1/models")
    async def models(authorization: str | None = Header(default=None)):
        if not _token_autorizado(_token_recibido(authorization), config):
            return error("NO_AUTORIZADO", 401)
        # Sólo alias del catálogo; no revelar modelo externo, URL o credenciales.
        grupos: dict[str, dict] = {}
        etiquetas = {"openai": "OpenAI", "anthropic": "Anthropic", "gemini": "Gemini", "simulado": "Simulado"}
        for alias, ruta in sorted(config.rutas.items()):
            if ruta.proveedor not in adaptadores:
                continue
            grupo = grupos.setdefault(ruta.proveedor, {
                "id": ruta.proveedor,
                "label": etiquetas.get(ruta.proveedor, ruta.proveedor.replace("_", " ").title()),
                "models": [],
            })
            grupo["models"].append({"id": alias, "label": alias})
        return {"providers": list(grupos.values())}

    @app.post("/v1/chat/completions")
    async def chat(cuerpo: SolicitudChat, authorization: str | None = Header(default=None)):
        return await procesar(cuerpo, authorization, extendida=False)

    @app.post("/api/v1/secure-chat")
    async def seguro(cuerpo: SolicitudChat, authorization: str | None = Header(default=None),
                     x_privateway_user_id: str | None = Header(default=None),
                     x_privateway_user_name: str | None = Header(default=None)):
        return await procesar(cuerpo, authorization, extendida=True,
                              actor_id=x_privateway_user_id, actor_nombre=x_privateway_user_name)

    return app
