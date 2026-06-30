"""
Parser del Excel exportado de SISOR.
Maneja dos formatos:
  1. Formato "RESUMEN DE FACTURAS CAPTURADAS" (formato estándar de SISOR)
  2. Formato tabla genérica (por si SISOR cambia el reporte)
"""
import io
import re
import pandas as pd
from typing import Optional, List, Tuple


# ─── Formato estándar SISOR ───────────────────────────────────────────────────
# Columnas por posición (basado en el export real):
#   0: fecha_captura, 1: proveedor, 5: factura, 7: importe, 8: importe_mxn, 9: fecha_factura

_SISOR_COLS = {
    0: "fecha_captura",
    1: "proveedor",
    5: "factura",
    7: "importe",
    8: "importe_mxn",
    9: "fecha_factura",
}

# Para detección de formato genérico
_UUID_CANDIDATES      = ["uuid", "folio fiscal", "folio_fiscal", "foliofiscal", "timbre"]
_RFC_CANDIDATES       = ["rfc", "rfc emisor", "rfc_emisor", "rfcemisor", "rfc proveedor"]
_PROVEEDOR_CANDIDATES = ["proveedor", "nombre", "razon social", "razonsocial", "nombre proveedor"]
_TOTAL_CANDIDATES     = ["total", "importe", "monto", "importe total"]
_FECHA_CANDIDATES     = ["fecha", "fecha factura", "fecha_factura", "fecha emision"]
_FOLIO_CANDIDATES     = ["folio", "numero", "no factura", "num factura", "numero factura", "factura"]


def _is_sisor_standard(df_raw: pd.DataFrame) -> bool:
    """Detecta si es el formato estándar de SISOR por palabras clave en las primeras filas."""
    for i in range(min(15, len(df_raw))):
        row_vals = df_raw.iloc[i].astype(str).str.upper()
        if row_vals.str.contains("RESUMEN DE FACTURAS CAPTURADAS").any():
            return True
        if row_vals.str.contains("FECHA.*CAPTURA").any():
            return True
    return False


def _parse_sisor_standard(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Parser para el formato estándar de SISOR.
    Los datos empiezan en fila 12 (índice base 0), después de las filas de encabezado.
    """
    # Encontrar la primera fila con fecha real (formato DD-MM-YYYY o similar)
    data_start = None
    for i in range(8, min(20, len(df_raw))):
        val = str(df_raw.iloc[i, 0]).strip()
        if re.match(r"\d{2}[-/]\d{2}[-/]\d{4}", val):
            data_start = i
            break

    if data_start is None:
        data_start = 12  # fallback

    df_datos = df_raw.iloc[data_start:].copy()

    # Asignar nombres de columna según posición
    n_cols = len(df_datos.columns)
    new_cols = [f"col_{i}" for i in range(n_cols)]
    for pos, name in _SISOR_COLS.items():
        if pos < n_cols:
            new_cols[pos] = name
    df_datos.columns = new_cols

    # Filtrar filas de datos reales (tienen fecha en col 0)
    df_datos = df_datos[df_datos["fecha_captura"].astype(str).str.match(r"\d{2}[-/]\d{2}[-/]\d{4}")]
    df_datos = df_datos.reset_index(drop=True)

    return df_datos


def _match_col(columns: List[str], candidates: List[str]) -> Optional[str]:
    cols_lower = {c: c.lower().strip() for c in columns}
    for cand in candidates:
        for original, lower in cols_lower.items():
            if cand in lower or lower in cand:
                return original
    return None


def parse_sisor(file_bytes: bytes, filename: str = "") -> Tuple[pd.DataFrame, dict]:
    """
    Lee el Excel de SISOR. Detecta formato automáticamente.
    Retorna (DataFrame normalizado, metadata con columnas detectadas).
    """
    # Leer archivo crudo
    try:
        if filename.lower().endswith(".csv"):
            df_raw = pd.read_csv(io.BytesIO(file_bytes), dtype=str, encoding="utf-8-sig", header=None)
            is_standard = False
        else:
            ext = filename.lower().split(".")[-1]
            engine = "xlrd" if ext in ("xls",) else "openpyxl"
            df_raw = pd.read_excel(io.BytesIO(file_bytes), header=None, dtype=str, engine=engine)
            is_standard = _is_sisor_standard(df_raw)
    except Exception as e:
        raise ValueError(f"No se pudo leer el archivo de SISOR: {e}")

    if is_standard:
        df_datos = _parse_sisor_standard(df_raw)
        meta = {
            "formato": "sisor_standard",
            "uuid_col": None,
            "rfc_col": None,
            "proveedor_col": "proveedor",
            "total_col": "importe",
            "fecha_col": "fecha_factura",
            "folio_col": "factura",
            "all_columns": list(df_raw.columns),
        }
    else:
        # Formato genérico: usar primera fila como encabezado
        for header_row in [0, 1, 2, 3]:
            df_raw2 = pd.read_excel(
                io.BytesIO(file_bytes), header=header_row, dtype=str,
                engine="openpyxl"
            )
            non_unnamed = [c for c in df_raw2.columns if not str(c).startswith("Unnamed")]
            if len(non_unnamed) >= 3:
                break
        df_datos = df_raw2
        cols = list(df_datos.columns)
        uuid_col     = _match_col(cols, _UUID_CANDIDATES)
        rfc_col      = _match_col(cols, _RFC_CANDIDATES)
        proveedor_col = _match_col(cols, _PROVEEDOR_CANDIDATES)
        total_col    = _match_col(cols, _TOTAL_CANDIDATES)
        fecha_col    = _match_col(cols, _FECHA_CANDIDATES)
        folio_col    = _match_col(cols, _FOLIO_CANDIDATES)

        # Renombrar columnas detectadas
        rename_map = {}
        if uuid_col:      rename_map[uuid_col]     = "uuid"
        if rfc_col:       rename_map[rfc_col]       = "rfc_sisor"
        if proveedor_col: rename_map[proveedor_col] = "proveedor"
        if total_col:     rename_map[total_col]     = "importe"
        if fecha_col:     rename_map[fecha_col]     = "fecha_factura"
        if folio_col:     rename_map[folio_col]     = "factura"
        df_datos = df_datos.rename(columns=rename_map)

        meta = {
            "formato": "generico",
            "uuid_col":      uuid_col,
            "rfc_col":       rfc_col,
            "proveedor_col": proveedor_col,
            "total_col":     total_col,
            "fecha_col":     fecha_col,
            "folio_col":     folio_col,
            "all_columns":   cols,
        }

    # ─── Normalizar tipos ─────────────────────────────────────────────────────

    # UUID (si existe)
    if "uuid" in df_datos.columns:
        df_datos["uuid"] = df_datos["uuid"].astype(str).str.strip().str.upper()
        df_datos.loc[df_datos["uuid"].isin(["NAN", "NONE", ""]), "uuid"] = pd.NA

    # Proveedor: limpiar sufijos SISOR como "(2026)", "(FEREMA)", etc.
    if "proveedor" in df_datos.columns:
        df_datos["proveedor"] = (
            df_datos["proveedor"].astype(str).str.strip().str.upper()
            .str.replace(r"\s*\(\d{4}\)\s*$", "", regex=True)   # quitar (2026) al final
            .str.strip()
        )

    # Importe numérico
    if "importe" in df_datos.columns:
        df_datos["importe_num"] = pd.to_numeric(
            df_datos["importe"].astype(str)
            .str.replace(",", "", regex=False)
            .str.replace("$", "", regex=False)
            .str.strip(),
            errors="coerce"
        )

    # Folio como string limpio
    if "factura" in df_datos.columns:
        df_datos["factura_str"] = df_datos["factura"].astype(str).str.strip()

    # Fecha factura
    if "fecha_factura" in df_datos.columns:
        df_datos["fecha_dt"] = pd.to_datetime(df_datos["fecha_factura"], errors="coerce", dayfirst=True)

    # Limpiar filas totalmente vacías
    df_datos = df_datos.dropna(how="all").reset_index(drop=True)

    return df_datos, meta
