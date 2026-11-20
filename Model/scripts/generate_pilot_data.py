"""Fixtures sintéticas, offsets exactos y separación por familias de plantillas."""
import json
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "Model/datasets/v1"


def generar():
    ROOT.mkdir(parents=True, exist_ok=True)
    conjuntos = {}
    nombres = {"desarrollo": ["Ana Torres", "Luis Paredes", "Rosa Vidal", "Diego Salas", "Elena Rojas", "Mario Soto"],
               "validacion": ["Julia Campos", "Pedro Lagos", "Inés Araya", "Carlos Leiva", "Sara Muñoz", "Bruno Vera"]}
    for split in nombres:
        filas = []
        for i, nombre in enumerate(nombres[split]):
            correo = f"persona{i}@example.test"
            telefono = f"+5698765432{i}"
            run = "12.345.678-5"
            direccion = f"Calle Imaginaria {100+i}"
            pref = "Resume este texto: " if split == "desarrollo" else "Prepara una ficha usando estos antecedentes: "
            escenarios = [
                (["Explica cómo funciona un calendario." if split == "desarrollo" else "Redacta instrucciones para ordenar carpetas."], [], "permitir"),
                ([pref + f"El RUN del solicitante es {run}."], [(run,"run")], "seudonimizar"),
                ([pref + f"Contacto: {correo}."], [(correo,"correo")], "seudonimizar"),
                ([pref + f"Llámame al {telefono}."], [(telefono,"telefono")], "seudonimizar"),
                ([pref + f"La persona solicitante se llama {nombre}."], [(nombre,"persona")], "seudonimizar"),
                ([pref + f"Mi domicilio es {direccion}."], [(direccion,"direccion")], "seudonimizar"),
                ([pref + f"{nombre} tiene diabetes."], [(nombre,"persona"),("diabetes","salud")], "bloquear"),
                ([pref + f"{nombre} usa {correo} y {telefono}."], [(nombre,"persona"),(correo,"correo"),(telefono,"telefono")], "seudonimizar"),
                ([pref + f"{nombre} solicitó ayuda. Debemos contactar a {nombre}."], [(nombre,"persona")], "seudonimizar"),
                ([f"La solicitante es {nombre}.", "Necesito resumir el antecedente anterior." if split == "desarrollo" else "Usa el nombre mencionado antes para el borrador."], [(nombre,"persona")], "seudonimizar"),
            ]
            if split == "validacion":
                # Familias de redacción diferentes, no variantes del prefijo de desarrollo.
                escenarios = [
                    (["Escribe una guía para regar plantas de interior."], [], "permitir"),
                    ([f"Completa el formulario de atención. Identificador de la persona: {run}."], [(run,"run")], "seudonimizar"),
                    ([f"¿Puedes redactar una invitación dirigida a {correo}?"], [(correo,"correo")], "seudonimizar"),
                    ([f"El cliente dejó {telefono} como número para devolverle la llamada."], [(telefono,"telefono")], "seudonimizar"),
                    ([f"A quien corresponda: certifico que {nombre} entregó sus antecedentes."], [(nombre,"persona")], "seudonimizar"),
                    ([f"Envía la encomienda al domicilio particular ubicado en {direccion}."], [(direccion,"direccion")], "seudonimizar"),
                    ([f"En la ficha clínica de {nombre} figura un diagnóstico de diabetes."], [(nombre,"persona"),("diabetes","salud")], "bloquear"),
                    ([f"Destinatario: {nombre}. Para confirmar la entrega escribe a {correo} o marca {telefono}."], [(nombre,"persona"),(correo,"correo"),(telefono,"telefono")], "seudonimizar"),
                    ([f"Acta: comparece {nombre}. La firma corresponde también a {nombre}."], [(nombre,"persona")], "seudonimizar"),
                    ([f"Deja registrado que {nombre} retiró el paquete.", "Ahora convierte el registro anterior en un comprobante."], [(nombre,"persona")], "seudonimizar"),
                ]
            for escenario, (textos, etiquetas, accion) in enumerate(escenarios):
                spans = []
                for mi, texto in enumerate(textos):
                    for valor, categoria in etiquetas:
                        start = 0
                        while (pos := texto.find(valor, start)) >= 0:
                            spans.append(dict(mensaje=mi, inicio=pos, fin=pos+len(valor), categoria=categoria))
                            start = pos + len(valor)
                filas.append(dict(id=f"{split}_{escenario}_{i}", familia=f"{split}_escenario{escenario}",
                                  split=split, accion=accion, hallazgos=spans,
                                  mensajes=[dict(role="user",content=t) for t in textos]))
        conjuntos[split] = filas
        (ROOT / f"{split}.json").write_text(json.dumps(filas, ensure_ascii=False, indent=2), encoding="utf-8")
    preguntas = {
        "art2_f": ["¿Un nombre permite identificar a una persona?", "¿El RUN es un identificador personal?", "¿Qué es una persona identificable?", "¿Qué medios se consideran para identificar a alguien?"],
        "art2_g": ["¿La información de salud es sensible?", "¿Qué son los datos personales sensibles?", "¿Una enfermedad es información sensible?", "¿Cómo se clasifican los datos biométricos?"],
        "art2_l": ["¿Qué es la seudonimización?", "¿Se puede conservar información adicional separada?", "¿Qué resguarda la relación entre marcador y titular?", "¿Qué tratamiento requiere información adicional para atribuir datos?"],
        "art3_c": ["¿Qué principio limita los datos a lo necesario?", "¿Durante cuánto tiempo pueden conservarse datos?", "¿Qué significa proporcionalidad del tratamiento?", "¿Deben ser pertinentes los datos para su finalidad?"],
        "art3_f": ["¿Qué principio protege frente a filtraciones?", "¿Qué medidas deben ajustarse a la naturaleza del dato?", "¿Cómo debe protegerse la pérdida accidental de datos?", "¿Qué exige la seguridad del tratamiento?"],
        "art16bis": ["¿Cómo se regulan datos relativos a la salud?", "¿Qué reglas se aplican al perfil biológico humano?", "¿Cuál es la disposición sobre datos de salud del titular?", "¿Dónde se regula el tratamiento de datos genéticos?"],
    }
    rag = [dict(id=f"rag_{ref}_{i}", split="desarrollo" if i < 2 else "validacion", consulta=q, esperado=ref)
           for ref, qs in preguntas.items() for i, q in enumerate(qs)]
    (ROOT / "recuperacion.json").write_text(json.dumps(rag, ensure_ascii=False, indent=2), encoding="utf-8")
    hashes = {}
    conjuntos.update(recuperacion=rag)
    for nombre, filas in conjuntos.items():
        ruta = ROOT / f"{nombre}.json"
        hashes[nombre] = hashlib.sha256(ruta.read_bytes()).hexdigest()
    manifiesto = {
        "version": "privateway-synthetic-v1",
        "nota": "Datos sintéticos deterministas; no derivados de registros de personas reales.",
        "conjuntos": {nombre: {"n": len(filas)} for nombre, filas in conjuntos.items()},
        "sha256": hashes,
    }
    (ROOT / "manifest.json").write_text(
        json.dumps(manifiesto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("120 consultas de deteccion y 24 de recuperacion generadas.")


if __name__ == "__main__":
    generar()
