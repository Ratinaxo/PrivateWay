"""Piloto REGEX → RAG → SLM. Toda inconsistencia detiene el envío."""
from __future__ import annotations

import asyncio
import secrets
import time
import httpx
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.deteccion.hallazgo import Categoria, Hallazgo, Procedencia
from .contracts import Accion, Mensaje
from .pipeline import AnalisisNoDisponible, DecisionValidada, Restitucion
from .regex_pipeline import PipelineRegex, seudonimizar_texto
from .slm_protocol import ASOCIACION_SALUD, DECISION, EXTRACCION, FUNDAMENTO, NOMBRES, VERSION


class EntidadSLM(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(pattern=r"^[a-zA-Z0-9_]{1,32}$")
    categoria: Literal["run", "correo", "telefono", "persona", "direccion", "salud"]
    texto: str = Field(min_length=1, max_length=20000)
    mensaje: int = Field(ge=0)
    inicio: int = Field(ge=0)
    fin: int = Field(gt=0)
    persona_asociada: bool


class DeteccionSLM(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    hallazgos: list[EntidadSLM] = Field(max_length=100)
    seleccionados: list[str] = Field(max_length=100)
    referencias: list[str] = Field(default_factory=list)


class JuicioSLM(DeteccionSLM):
    referencias: list[str] = Field(min_length=1, max_length=4)
    justificacion: str = Field(min_length=1, max_length=400)
    accion: Literal["permitir", "seudonimizar", "bloquear"]


INSTRUCCION = "\n".join((EXTRACCION, NOMBRES, ASOCIACION_SALUD, DECISION, FUNDAMENTO))

_ROL_PERSONA = r"(?:persona(?:\s+solicitante)?|solicitante|paciente|encargad[oa]|responsable|usuari[oa])"
_PALABRA_NOMBRE = r"[A-ZÁÉÍÓÚÑÜ][a-záéíóúñü]+(?:[-'][A-ZÁÉÍÓÚÑÜ][a-záéíóúñü]+)?"
_NOMBRE_DECLARADO = re.compile(
    rf"(?i:\b(?:la|el)\s+{_ROL_PERSONA}(?:\s+[\wáéíóúñü-]+){{0,6}}?"
    rf"\s+(?:se llama|es)\s+)(?P<nombre>{_PALABRA_NOMBRE}(?:\s+{_PALABRA_NOMBRE}){{1,3}})"
    r"(?=\s*(?:[.!?;,]|$))"
)


class PipelineHibrido(PipelineRegex):
    listo = True

    def __init__(self, *, recuperador, slm, detector=None, usar_regex=True):
        super().__init__(detector=detector)
        self.recuperador, self.slm = recuperador, slm
        self.usar_regex = usar_regex

    async def procesar_respuesta(self, solicitud, decision, respuesta, contexto):
        respuesta = await super().procesar_respuesta(solicitud, decision, respuesta, contexto)
        if decision.restitucion is None:
            return respuesta
        contenido = decision.restitucion.aplicar(respuesta.content, contexto)
        return respuesta.model_copy(update={"content": contenido})

    async def comprobar(self):
        try:
            return bool(await self.recuperador.comprobar() and await self.slm.comprobar())
        except Exception:
            return False

    async def analizar(self, solicitud, contexto):
        return await self._ejecutar(solicitud, contexto)

    async def _ejecutar(self, solicitud, contexto, solo_deteccion=False):
        try:
            # Presupuesto de pared, también cubre espera por servicios/cola.
            async with asyncio.timeout(120):
                return await self._analizar(solicitud, contexto, solo_deteccion=solo_deteccion)
        except Exception as exc:
            codigo = "HIBRIDO_FALLO"
            if isinstance(exc, (TimeoutError, httpx.TimeoutException)):
                codigo = "HIBRIDO_TIMEOUT"
            elif isinstance(exc, httpx.HTTPStatusError):
                codigo = "SERVICIO_HTTP_" + str(exc.response.status_code)
            elif isinstance(exc, ValidationError):
                codigo = "SLM_ESQUEMA_INVALIDO"
            elif isinstance(exc, ValueError):
                codigo = {"CONTEXTO_EXCEDIDO":"CONTEXTO_EXCEDIDO", "SALIDA_INCOMPLETA":"SLM_SALIDA_INCOMPLETA",
                          "offset incorrecto":"SLM_OFFSET_INVALIDO", "cita desconocida":"SLM_CITA_INVALIDA",
                          "regex descartado":"SLM_DESCARTA_REGEX", "criterio contradictorio":"SLM_ACCION_INCOHERENTE",
                          "sin evidencia":"RAG_SIN_EVIDENCIA", "salud ambigua":"SLM_SALUD_AMBIGUA",
                          "cobertura incompleta":"SLM_SELECCION_INCOMPLETA"}.get(str(exc), codigo)
                if str(exc) == "entidad no literal":
                    codigo = "SLM_ENTIDAD_NO_LITERAL"
            raise AnalisisNoDisponible("HIBRIDO_NO_VALIDADO", codigo=codigo) from None

    async def detectar(self, solicitud, contexto):
        """Solo experimento intrínseco: nunca habilita transmisión al proveedor."""
        return await self._ejecutar(solicitud, contexto, solo_deteccion=True)

    async def _analizar(self, solicitud, contexto, solo_deteccion=False):
        t = time.perf_counter()
        if sum(len(m.content) for m in solicitud.messages) > 120000:
            raise ValueError("limite")
        regex = []
        for i, mensaje in enumerate(solicitud.messages):
            for h in self._detectar(mensaje.content) if self.usar_regex else []:
                regex.append(dict(id=f"r{len(regex)}", mensaje=i, inicio=h.inicio,
                                  fin=h.fin, categoria=h.categoria.value,
                                  texto=h.valor, persona_asociada=False))
            if self.usar_regex:
                for m in _NOMBRE_DECLARADO.finditer(mensaje.content):
                    inicio, fin = m.span("nombre")
                    regex.append(dict(id=f"r{len(regex)}", mensaje=i, inicio=inicio, fin=fin,
                                      categoria="persona", texto=m.group("nombre"), persona_asociada=False))
        tiempos = {"regex_ms": (time.perf_counter() - t) * 1000}
        t = time.perf_counter()
        fragmentos = await self.recuperador.buscar(solicitud.messages, regex)
        if not fragmentos or len({f["id"] for f in fragmentos}) != len(fragmentos):
            raise ValueError("sin evidencia")
        tiempos["rag_ms"] = (time.perf_counter() - t) * 1000
        versiones = await self.recuperador.versiones()
        if any(f.get("indice", versiones["indice"]) != versiones["indice"] for f in fragmentos):
            raise ValueError("version de corpus cambio durante solicitud")
        entrada = dict(fragmentos=fragmentos, regex=regex,
                       mensajes=[dict(indice=i, role=m.role, texto=m.content,
                                      posiciones_palabras="; ".join(f"{w.start()}-{w.end()}:{w.group()}"
                                          for w in re.finditer(r"\w+(?:[-']\w+)*", m.content)))
                                 for i, m in enumerate(solicitud.messages)])
        t = time.perf_counter()
        esquema = JuicioSLM.model_json_schema()
        esquema["properties"]["referencias"]["items"] = {"type":"string", "enum":[f["id"] for f in fragmentos]}
        if solo_deteccion and callable(getattr(self.slm, "extraer_entidades", None)):
            hallazgos = await self.slm.extraer_entidades(entrada)
            juicio = DeteccionSLM.model_validate(dict(hallazgos=hallazgos, seleccionados=[h["id"] for h in hallazgos]))
        elif callable(getattr(self.slm, "analizar_etapas", None)):
            resultado = await self.slm.analizar_etapas(entrada)
            juicio = JuicioSLM.model_validate_json(resultado)
        else:
            resultado = await self.slm.juzgar(INSTRUCCION, entrada, esquema)
            juicio = JuicioSLM.model_validate_json(resultado)
        tiempos["slm_ms"] = (time.perf_counter() - t) * 1000
        ids = [h.id for h in juicio.hallazgos]
        if len(set(ids)) != len(ids) or len(set(juicio.seleccionados)) != len(juicio.seleccionados):
            raise ValueError("ids duplicados")
        if set(juicio.seleccionados) != set(ids):
            raise ValueError("cobertura incompleta")
        if not set(juicio.referencias).issubset({f["id"] for f in fragmentos}):
            raise ValueError("cita desconocida")
        por_id = {h.id: h for h in juicio.hallazgos}
        for previo in regex:
            h = por_id.get(previo["id"])
            if h is None or any(getattr(h, k) != previo[k] for k in ("mensaje", "inicio", "fin", "categoria", "texto")):
                raise ValueError("regex descartado")
        por_mensaje = [[] for _ in solicitud.messages]
        for h in juicio.hallazgos:
            if h.mensaje >= len(solicitud.messages):
                raise ValueError("mensaje inexistente")
            texto = solicitud.messages[h.mensaje].content
            if h.fin > len(texto) or texto[h.inicio:h.fin] != h.texto:
                raise ValueError("offset incorrecto")
            if h.categoria == "salud" and not h.persona_asociada:
                raise ValueError("salud ambigua")
            por_mensaje[h.mensaje].append(Hallazgo(
                Categoria(h.categoria), h.texto, h.inicio, h.fin, "piloto",
                Procedencia.REGEX if h.id in {r["id"] for r in regex} else Procedencia.SLM, 1.0))
        esperada = (Accion.BLOQUEAR if any(h.categoria == "salud" for h in juicio.hallazgos)
                    else Accion.SEUDONIMIZAR if juicio.hallazgos else Accion.PERMITIR)
        if solo_deteccion:
            return DecisionValidada(esperada, "DETECCION_EXPERIMENTAL", validacion_completa=False,
                traza={"hallazgos":[h.model_dump() for h in juicio.hallazgos],
                       "recuperados":[f["id"] for f in fragmentos],
                       "tiempos":tiempos, "versiones":versiones})
        if juicio.accion != esperada.value:
            raise ValueError("criterio contradictorio")
        t = time.perf_counter()
        etiquetas = {}
        nuevos = []
        if esperada != Accion.BLOQUEAR:
            # Marcadores de entrada se rechazan para evitar colisiones del piloto.
            if any("[PW_" in m.content for m in solicitud.messages):
                raise ValueError("colision marcador")
            for m, hs in zip(solicitud.messages, por_mensaje):
                saneado = seudonimizar_texto(m.content, hs, etiquetas, crear_etiqueta=_marcador)
                if self._detectar(saneado):
                    raise ValueError("regex residual")
                nuevos.append(Mensaje(role=m.role, content=saneado))
        tiempos["transformacion_ms"] = (time.perf_counter() - t) * 1000
        traza = dict(modelo=self.slm.modelo, revision_modelo=getattr(self.slm,"revision","no_registrada"),
                     instrucciones=VERSION, esquema="juicio-normalizado-v1",
                     criterio="piloto-v1", reglas="regex-v1", accion_propuesta=juicio.accion,
                     accion_aplicada=esperada.value, referencias=juicio.referencias,
                     fragmentos=fragmentos, justificacion=juicio.justificacion,
                     hallazgos=[h.model_dump() for h in juicio.hallazgos], tiempos=tiempos,
                     versiones=versiones)
        return DecisionValidada(esperada, "HIBRIDO_" + esperada.name,
                                nuevos if esperada != Accion.BLOQUEAR else None,
                                True, esperada == Accion.SEUDONIMIZAR, traza,
                                restitucion=Restitucion(contexto, {
                                    marcador: valor for (_, valor), marcador in etiquetas.items()
                                }) if etiquetas else None)


def _marcador(categoria: Categoria) -> str:
    # Evita secuencias de dígitos que REGEX podría interpretar como identificadores.
    sufijo = secrets.token_hex(16).translate(str.maketrans("0123456789abcdef", "abcdefghijklmnop"))
    return f"[PW_{categoria.name}_{sufijo}]"


def desde_entorno():
    from .rag import RecuperadorPostgres, EmbeddingsHTTP
    from .slm import ClienteVLLM
    return PipelineHibrido(recuperador=RecuperadorPostgres(EmbeddingsHTTP()), slm=ClienteVLLM())
