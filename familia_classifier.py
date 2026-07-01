"""
Clasificación de facturas por familia con base en las órdenes de compra.

Las facturas (OFB/SAT y SISOR) no traen familia ni productos; la familia se
deriva cruzando el proveedor de la factura contra el historial de OCs:
  1. Catálogo manual (familias_proveedor.json) — para proveedores sin OC.
  2. Proveedor con una sola familia en sus OCs → esa familia.
  3. Proveedor multi-familia → cruce por importe (±2%) contra renglones y
     totales por OC; si no cuadra, familia dominante con prefijo "≈".
  4. Sin información → "SIN CLASIFICAR".
"""
import json
import re
from pathlib import Path
from typing import Optional

import pandas as pd

ARCHIVO_FAMILIAS = Path(__file__).parent / "familias_proveedor.json"

SIN_CLASIFICAR      = "SIN CLASIFICAR"
TOLERANCIA_IMPORTE  = 0.02   # misma tolerancia que el matching OFB↔SISOR
MIN_LARGO_PREFIJO   = 5      # evita falsos positivos en match por prefijo


# ─── Catálogo manual {rfc: {"nombre": str, "familia": str}} ───────────────────

def cargar_familias_manuales() -> dict:
    """Carga el catálogo manual RFC → familia. Si no existe, retorna vacío."""
    if not ARCHIVO_FAMILIAS.exists():
        return {}
    try:
        with open(ARCHIVO_FAMILIAS, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def guardar_familias_manuales(catalogo: dict) -> None:
    """Guarda el diccionario {rfc: {"nombre":…, "familia":…}} en familias_proveedor.json."""
    with open(ARCHIVO_FAMILIAS, "w", encoding="utf-8") as f:
        json.dump(catalogo, f, ensure_ascii=False, indent=2)


# ─── Normalización de nombres de proveedor ────────────────────────────────────

_SUFIJOS_SOCIETARIOS = {
    "SA", "SAB", "SAPI", "SC", "SRL", "S", "DE", "CV", "RL", "DECV", "CO",
}


def _norm_proveedor(nombre) -> str:
    """
    Normaliza un nombre de proveedor para cruzar SAT/SISOR vs OC:
    mayúsculas, sin puntuación, sin paréntesis finales ni sufijos societarios.
    """
    if nombre is None or (isinstance(nombre, float) and pd.isna(nombre)):
        return ""
    s = str(nombre).upper().strip()
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s)          # "(PEGAFULL)", "(2026)"…
    s = s.replace(".", "").replace(",", " ")        # "S.A. DE C.V." → "SA DE CV"
    tokens = s.split()
    while tokens and tokens[-1] in _SUFIJOS_SOCIETARIOS:
        tokens.pop()
    return " ".join(tokens)


# ─── Índice de familias a partir del historial de OC ──────────────────────────

def construir_indice_oc(df_oc_hist: pd.DataFrame) -> dict:
    """
    Construye {proveedor_normalizado: info} desde TODO el historial de OCs.
    info = {
        "familias":  {familia: monto_total_historico},
        "dominante": familia con mayor monto,
        "renglones": [(familia, total_renglon)],
        "por_oc":    [(familia, total_oc_familia)],  # suma por (oc, familia)
    }
    """
    if df_oc_hist is None or df_oc_hist.empty:
        return {}

    df = df_oc_hist.copy()
    for col in ("proveedor", "familia"):
        if col not in df.columns:
            return {}
    df["_prov_n"]  = df["proveedor"].map(_norm_proveedor)
    df["_familia"] = df["familia"].fillna("").astype(str).str.upper().str.strip()
    df["_total"]   = pd.to_numeric(df.get("total"), errors="coerce").fillna(0.0)
    df = df[(df["_prov_n"] != "") & (df["_familia"] != "")]

    indice: dict = {}
    for prov, grupo in df.groupby("_prov_n"):
        familias = grupo.groupby("_familia")["_total"].sum().to_dict()
        renglones = list(zip(grupo["_familia"], grupo["_total"]))
        if "oc" in grupo.columns:
            por_oc = [
                (fam, tot)
                for (_, fam), tot in grupo.groupby(["oc", "_familia"])["_total"].sum().items()
            ]
        else:
            por_oc = []
        indice[prov] = {
            "familias":  familias,
            "dominante": max(familias, key=familias.get),
            "renglones": renglones,
            "por_oc":    por_oc,
        }
    return indice


def familias_disponibles(indice_oc: dict) -> list:
    """Lista ordenada de familias que existen en el historial de OCs."""
    familias = {f for info in indice_oc.values() for f in info["familias"]}
    return sorted(familias)


# ─── Clasificador principal ───────────────────────────────────────────────────

def _buscar_proveedor(prov_n: str, indice_oc: dict) -> Optional[dict]:
    """Busca un proveedor en el índice: exacto primero, luego prefijo en límite de palabra."""
    if not prov_n:
        return None
    if prov_n in indice_oc:
        return indice_oc[prov_n]

    candidatos = []
    for prov_oc, info in indice_oc.items():
        corto, largo = sorted((prov_n, prov_oc), key=len)
        if len(corto) < MIN_LARGO_PREFIJO:
            continue
        if largo == corto or largo.startswith(corto + " "):
            candidatos.append(info)
    # Solo si el prefijo identifica a UN proveedor; ambiguo = sin match
    return candidatos[0] if len(candidatos) == 1 else None


def _familia_por_importe(importe: float, info: dict) -> Optional[str]:
    """Familia cuyo renglón o total de OC coincide con el importe de la factura (±2%)."""
    if not importe or importe <= 0:
        return None
    matches = set()
    for familia, total in info["renglones"] + info["por_oc"]:
        if total > 0 and abs(importe - total) / total <= TOLERANCIA_IMPORTE:
            matches.add(familia)
    return matches.pop() if len(matches) == 1 else None


def asignar_familia(df_facturas: pd.DataFrame, indice_oc: dict, manuales: dict) -> pd.Series:
    """
    Retorna una Series 'familia' alineada al índice de df_facturas (no muta el df).
    Usa columnas disponibles: proveedor, rfc_emisor (opcional), importe o total.
    """
    if df_facturas is None or df_facturas.empty:
        return pd.Series(dtype=str)

    por_rfc = {
        str(rfc).upper().strip(): str(v.get("familia", "")).upper().strip()
        for rfc, v in manuales.items() if isinstance(v, dict) and v.get("familia")
    }
    por_nombre = {
        _norm_proveedor(v.get("nombre", "")): str(v.get("familia", "")).upper().strip()
        for v in manuales.values()
        if isinstance(v, dict) and v.get("familia") and v.get("nombre")
    }

    col_importe = "importe" if "importe" in df_facturas.columns else "total"

    def _clasificar(row) -> str:
        rfc = str(row.get("rfc_emisor", "") or "").upper().strip()
        if rfc and rfc in por_rfc:
            return por_rfc[rfc]

        prov_n = _norm_proveedor(row.get("proveedor", ""))
        if prov_n and prov_n in por_nombre:
            return por_nombre[prov_n]

        info = _buscar_proveedor(prov_n, indice_oc)
        if info is None:
            return SIN_CLASIFICAR

        if len(info["familias"]) == 1:
            return info["dominante"]

        importe = pd.to_numeric(row.get(col_importe), errors="coerce")
        familia = _familia_por_importe(float(importe) if pd.notna(importe) else 0.0, info)
        return familia if familia else f"≈ {info['dominante']}"

    return df_facturas.apply(_clasificar, axis=1)
