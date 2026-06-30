"""
Gestión de proveedores excluidos del análisis de pendientes.
Guarda la configuración en exclusiones.json para que persista entre sesiones.
"""
import json
from pathlib import Path

ARCHIVO_EXCLUSIONES = Path(__file__).parent / "exclusiones.json"

# Proveedores que nunca van a SISOR (bancos, gobierno, servicios, arrendamiento, consultoría)
EXCLUSIONES_DEFAULT = {
    "BSM970519DU8": "BANCO SANTANDER MEXICO",
    "BBA940707IE1": "BANCO DEL BAJIO",
    "IMS421231I45": "INSTITUTO MEXICANO DEL SEGURO SOCIAL",
    "INF7205011ZA": "INFONAVIT",
    "TME840315KT6": "TELEFONOS DE MEXICO",
    "SGM950714DC2": "SERVICIOS GASOLINEROS DE MEXICO",
    "ENV160316RQA": "ENVIOCLICK",
    "ODM950324V2A": "OFFICE DEPOT DE MEXICO",
    "AIN110302S31": "ARRENDADORA INCREMEX",
    "YAE130108FGA": "YIELD ASESORIA EMPRESARIAL",
}


def cargar_exclusiones() -> dict:
    """Carga exclusiones desde archivo. Si no existe, crea el archivo con los defaults."""
    if not ARCHIVO_EXCLUSIONES.exists():
        guardar_exclusiones(EXCLUSIONES_DEFAULT)
        return dict(EXCLUSIONES_DEFAULT)
    try:
        with open(ARCHIVO_EXCLUSIONES, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return dict(EXCLUSIONES_DEFAULT)


def guardar_exclusiones(rfcs: dict) -> None:
    """Guarda el diccionario {rfc: nombre} en exclusiones.json."""
    with open(ARCHIVO_EXCLUSIONES, "w", encoding="utf-8") as f:
        json.dump(rfcs, f, ensure_ascii=False, indent=2)
