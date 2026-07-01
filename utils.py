"""
Utilidades compartidas entre módulos de la app.
"""
from datetime import date
from typing import Optional


def estado_entrega(fecha_str, hoy: date = None) -> str:
    """Clasifica una fecha de entrega como 'vencida', 'proxima', 'a_tiempo' o 'sin_fecha'."""
    if hoy is None:
        hoy = date.today()
    try:
        if not fecha_str:
            return "sin_fecha"
        f = date.fromisoformat(str(fecha_str).strip()[:10])
        dias = (f - hoy).days
        if dias < 0:
            return "vencida"
        if dias <= 7:
            return "proxima"
        return "a_tiempo"
    except Exception:
        return "sin_fecha"


def dias_restantes(fecha_str, hoy: date = None) -> Optional[int]:
    """Días restantes hasta la fecha de entrega, o None si no hay fecha válida."""
    if hoy is None:
        hoy = date.today()
    try:
        if not fecha_str:
            return None
        return (date.fromisoformat(str(fecha_str).strip()[:10]) - hoy).days
    except Exception:
        return None
