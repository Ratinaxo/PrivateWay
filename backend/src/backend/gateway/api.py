"""Entrypoint HTTP experimental. Por defecto NO envía solicitudes a Internet."""
from __future__ import annotations

import re
import hashlib
import secrets
import time
import uuid

from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .audit import AuditoriaArchivo, AuditoriaNoConfigurada, AuditoriaNoDisponible
from .config import Configuracion, proveedores_desde_entorno
from .contracts import Accion, SolicitudChat
from .pipeline import PipelineNoConfigurado, AnalisisNoDisponible, ContextoEjecucion
from .providers import ProveedorNoDisponible

import os

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
    }
    cabeceras = {"X-Gateway-Event-ID": evento} if evento else {}
    return JSONResponse(
        status_code=estado,
        headers=cabeceras,
        content={"error": {"type": "gateway_error", "code": codigo, "message": mensajes[codigo]}},
    )


def create_app(*, config=None, pipeline=None, auditoria=None, adaptadores=None) -> FastAPI:
    config = config if config is not None else Configuracion.desde_entorno()
    pipeline = pipeline if pipeline is not None else PipelineNoConfigurado()
    if auditoria is None:
        ruta_auditoria = os.environ.get("GATEWAY_AUDIT_FILE")
        auditoria = AuditoriaArchivo(ruta_auditoria) if ruta_auditoria else AuditoriaNoConfigurada()
    adaptadores = adaptadores if adaptadores is not None else proveedores_desde_entorno()

    app = FastAPI(title="Gateway LLM (entrypoint experimental)", docs_url=None, redoc_url=None)

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

    async def procesar(cuerpo: SolicitudChat, autorizacion: str | None, extendida: bool):
        evento = "evt_" + uuid.uuid4().hex
        prefix = "Bearer "
        recibida = autorizacion[len(prefix):] if autorizacion and autorizacion.startswith(prefix) else ""
        valido = any(secrets.compare_digest(recibida, t) for t in config.tokens_cliente)
        if not valido:
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

        registro = {
            "evento": evento, "alias": cuerpo.model, "proveedor": ruta.proveedor,
            "accion": decision.accion.value, "motivo": decision.codigo_motivo,
        }
        try:
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
                                      "evento": evento}},
                headers={"X-Gateway-Event-ID": evento},
            )
        return JSONResponse(content=respuesta_chat, headers={"X-Gateway-Event-ID": evento})

    @app.get("/api/v1/models")
    async def models(authorization: str | None = Header(default=None)):
        prefix = "Bearer "
        recibida = authorization[len(prefix):] if authorization and authorization.startswith(prefix) else ""
        if not any(secrets.compare_digest(recibida, t) for t in config.tokens_cliente):
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
    async def seguro(cuerpo: SolicitudChat, authorization: str | None = Header(default=None)):
        return await procesar(cuerpo, authorization, extendida=True)

    return app
