import pytest

from backend.gateway.exposure import visibilidad


@pytest.mark.parametrize("valor,enviado,categoria,esperado", [
    ("Ana Torres", "Ana Torres", "persona", "literal"),
    ("Ana Torres", "Mariana llegó", "persona", "oculta"),
    ("Ana Torres", "Llegó Torres", "persona", "parcial"),
    ("+56987654320", "Contacto 7654", "telefono", "parcial"),
    ("12.345.678-5", "Referencia 34 texto 56", "run", "oculta"),
    ("persona0@example.test", "Dominio example.test", "correo", "oculta"),
    ("persona0@example.test", "Usuario persona0", "correo", "parcial"),
    ("Calle Imaginaria 100", "[PW_DIRECCION_" + "a" * 32 + "]", "direccion", "oculta"),
])
def test_visibilidad(valor, enviado, categoria, esperado):
    assert visibilidad(valor, enviado, categoria) == esperado
