"""Compara tareas sintéticas de extracción mediante el perfil externo del laboratorio."""
import argparse
import asyncio
from dataclasses import replace
import json
from pathlib import Path
import secrets
import time

import httpx

from backend.gateway.api import create_app
from backend.gateway.audit import AuditoriaArchivo
from backend.gateway.config import Configuracion, proveedores_desde_entorno
from backend.gateway.contracts import Mensaje, SolicitudChat
from backend.gateway.providers import ProveedorNoDisponible
from privateway_model.slm_protocol import VERSION


CASOS = (
    ("nombre", "La solicitante de prueba se llama Ana Torres.", "nombre de la solicitante", "Ana Torres"),
    ("direccion", "El domicilio de prueba es Calle Imaginaria 100.", "domicilio", "Calle Imaginaria 100"),
    ("correo", "El correo de prueba es persona0@example.test.", "correo", "persona0@example.test"),
    ("negativo", "El color elegido para la maqueta es azul.", "color elegido", "azul"),
    ("salud", "La solicitante de prueba Ana Torres tiene diabetes.", "nombre de la solicitante", "Ana Torres"),
    ("nombre-2", "La encargada del expediente ficticio es Elena Leiva.", "encargada", "Elena Leiva"),
    ("nombre-3", "El expediente se abrió el lunes. El solicitante simulado se llama Mateo Lagos.", "solicitante", "Mateo Lagos"),
    ("direccion-2", "El domicilio ficticio es Pasaje Inventado 45.", "domicilio", "Pasaje Inventado 45"),
    ("correo-2", "El correo de contacto simulado es oficina23@example.test.", "correo de contacto", "oficina23@example.test"),
    ("telefono", "El teléfono ficticio de contacto es +56 9 5555 0102.", "teléfono", "+56 9 5555 0102"),
    ("run", "El RUN de ejemplo es 12.345.678-5.", "RUN", "12.345.678-5"),
    ("mixto-nombre", "Clara Pino usa el correo prueba67@example.test y el teléfono +56 9 5555 0103.", "nombre de la persona", "Clara Pino"),
    ("mixto-correo", "Pablo Vera usa el correo pruebas42@example.test y el teléfono +56 9 5555 0104.", "correo", "pruebas42@example.test"),
    ("negativo-2", "La maqueta se entregará el martes, aunque el envío anterior fue el lunes.", "día de entrega de la maqueta", "martes"),
    ("salud-2", "El paciente ficticio Raúl Soto tiene asma.", "nombre del paciente", "Raúl Soto"),
)


def evaluar_respuesta(texto, esperado):
    return texto.strip().casefold() == esperado.casefold()


def solicitud_caso(texto, campo, alias):
    return SolicitudChat(model=alias, temperature=0, max_tokens=128, messages=[
        Mensaje(role="user", content=(
            f"{texto} Copia literalmente el valor del campo «{campo}». "
            "Si el valor está entre corchetes, incluye ambos corchetes y todo su contenido. "
            "Devuelve solo ese valor."
        ))
    ])


def accion_del_caso(caso):
    if caso.startswith("negativo"):
        return "permitir"
    if caso.startswith("salud"):
        return "bloquear"
    return "seudonimizar"


async def comprobar_con_simulador(archivo):
    from privateway_model.evaluation_flow import BancoFlujo
    from privateway_model.hybrid import desde_entorno

    auditoria = archivo.with_suffix(".events.jsonl")
    if auditoria.exists():
        raise RuntimeError("Usar una ruta con evidencia independiente")
    banco = BancoFlujo(desde_entorno(), auditoria)
    muestras = []
    try:
        for caso, texto, campo, esperado in CASOS:
            solicitud = solicitud_caso(texto, campo, "pw-simulado")
            decision, error, enviados = await banco.ejecutar(solicitud)
            accion_esperada = accion_del_caso(caso)
            accion = decision.accion.value if decision else None
            visible = (any(esperado in m.content for m in enviados)
                       if enviados and accion_esperada != "permitir" else None)
            correcto = (error is None and accion == accion_esperada and visible is not True
                        and (enviados is None) == (accion_esperada == "bloquear"))
            muestra = dict(id=caso, accion_esperada=accion_esperada, accion=accion,
                           error=error, valor_objetivo_literal_en_payload=visible,
                           transmitida=enviados is not None, correcto=correcto)
            muestras.append(muestra)
            print(json.dumps(muestra, ensure_ascii=True), flush=True)
    finally:
        await banco.cerrar()
    aprobada = all(m["correcto"] for m in muestras)
    with archivo.open("x", encoding="utf-8") as salida:
        json.dump(dict(protocolo=VERSION, aprobada=aprobada, muestras=muestras), salida, indent=2)
    return aprobada


class ProveedorObservado:
    def __init__(self, adaptador):
        self.adaptador = adaptador
        self.error = None
        self.enviados = []

    async def completar(self, modelo, mensajes, solicitud):
        self.error = None
        self.enviados = [mensaje.content for mensaje in mensajes]
        try:
            return await self.adaptador.completar(modelo, mensajes, solicitud)
        except ProveedorNoDisponible as exc:
            self.error = exc.codigo
            raise


class AuditoriaUtilidad(AuditoriaArchivo):
    def __init__(self, archivo):
        super().__init__(archivo)
        self.estado = {}

    async def registrar(self, datos):
        await super().registrar(datos)
        self.estado[datos["evento"]] = datos.get("transmision")


async def evaluar(archivo):
    config = Configuracion.desde_entorno()
    ruta = config.rutas.get("pw-lab")
    if ruta is None or ruta.proveedor != "laboratorio":
        raise RuntimeError("Se requiere el perfil externo de laboratorio")
    proveedores = proveedores_desde_entorno()
    proveedor = ProveedorObservado(proveedores[ruta.proveedor])
    proveedores[ruta.proveedor] = proveedor
    token = secrets.token_urlsafe(32)
    archivo_auditoria = archivo.with_suffix(".events.jsonl")
    if archivo_auditoria.exists():
        raise RuntimeError("Usar una ruta con evidencia independiente")
    auditoria = AuditoriaUtilidad(archivo_auditoria)
    app = create_app(config=replace(config, tokens_cliente=(token,)), adaptadores=proveedores, auditoria=auditoria)
    casos = []
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://laboratorio") as cliente:
        for caso, texto, campo, esperado in CASOS:
            solicitud = solicitud_caso(texto, campo, "pw-lab")
            inicio = time.perf_counter()
            estado_base = "completada"
            correcta_base = None
            try:
                original = await proveedores[ruta.proveedor].completar(ruta.modelo_externo, solicitud.messages, solicitud)
                if original.finish_reason == "length":
                    estado_base = "incompleta"
                else:
                    correcta_base = evaluar_respuesta(original.content, esperado)
            except ProveedorNoDisponible:
                estado_base = "fallida"
            codigo_base = proveedor.error
            tiempo_base = time.perf_counter() - inicio
            inicio = time.perf_counter()
            proveedor.error = None
            proveedor.enviados = []
            respuesta = await cliente.post("/api/v1/secure-chat", json=solicitud.model_dump(),
                                           headers={"Authorization": "Bearer " + token})
            tiempo_gateway = time.perf_counter() - inicio
            cuerpo = respuesta.json()
            codigo = cuerpo.get("error", {}).get("code")
            correcta_gateway = None
            if respuesta.status_code == 200:
                eleccion = cuerpo["respuesta"]["choices"][0]
                if eleccion["finish_reason"] == "length":
                    estado_gateway = "incompleta"
                else:
                    estado_gateway = "completada"
                    correcta_gateway = evaluar_respuesta(eleccion["message"]["content"], esperado)
            else:
                estado_gateway = "bloqueada" if codigo == "POLITICA_BLOQUEA" else "fallida"
            accion_esperada = accion_del_caso(caso)
            accion = (cuerpo.get("decision", {}).get("accion") if respuesta.status_code == 200
                      else "bloquear" if codigo == "POLITICA_BLOQUEA" else None)
            visible = None
            if proveedor.enviados and accion_esperada != "permitir":
                visible = any(esperado in mensaje for mensaje in proveedor.enviados)
            casos.append(dict(id=caso, base=estado_base, gateway=estado_gateway, codigo=codigo,
                              accion_esperada=accion_esperada, accion_gateway=accion,
                              valor_objetivo_literal_en_payload=visible,
                              codigo_proveedor_base=codigo_base, codigo_proveedor_gateway=proveedor.error,
                              transmision_gateway=auditoria.estado.get(respuesta.headers.get("X-Gateway-Event-ID")),
                              base_correcta=correcta_base, gateway_correcta=correcta_gateway,
                              base_s=tiempo_base, gateway_s=tiempo_gateway))
            print(json.dumps(casos[-1], ensure_ascii=True), flush=True)
    pares = [c for c in casos if c["base_correcta"] is not None and c["gateway_correcta"] is not None]
    resumen = dict(modelo=ruta.modelo_externo, protocolo=VERSION, tarea="copia-literal-v2",
                   temperature=0, max_tokens=128, muestras=casos,
                   pares_evaluables=len(pares),
                   acciones_correctas=sum(c["accion_gateway"] == c["accion_esperada"] for c in casos),
                   objetivos_literales_en_payload=sum(c["valor_objetivo_literal_en_payload"] is True for c in casos),
                   base_aciertos=sum(c["base_correcta"] for c in pares),
                   gateway_aciertos=sum(c["gateway_correcta"] for c in pares))
    with archivo.open("x", encoding="utf-8") as salida:
        json.dump(resumen, salida, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--salida", type=Path, required=True)
    parser.add_argument("--solo-simulador", action="store_true")
    args = parser.parse_args()
    if args.salida.exists():
        parser.error("Usar un archivo nuevo")
    if args.solo_simulador:
        if not asyncio.run(comprobar_con_simulador(args.salida)):
            raise SystemExit(1)
    else:
        asyncio.run(evaluar(args.salida))
