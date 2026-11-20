"""Validaciones pequeñas de estado para el servicio local de embeddings."""


_REVISIONES_PENDIENTES = {"no-descargado", "pending-download"}


def revision_configurada(revision: str | None) -> bool:
    if not isinstance(revision, str):
        return False
    valor = revision.strip()
    return bool(valor) and valor.casefold() not in _REVISIONES_PENDIENTES
