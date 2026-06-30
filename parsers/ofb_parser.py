"""
Parser del Excel OFB que proporciona el contador.
Formato: reporte de CFDIs recibidos exportado de AdminXML / sistema del SAT.
Columnas conocidas: UUID, RFC Emisor, Nombre Emisor, FechaEmisionXML, Serie, Folio, Total, Moneda, TipoComprobante, Estado SAT
"""
import io
import pandas as pd
from typing import Tuple


def parse_ofb(file_bytes: bytes, filename: str = "") -> Tuple[pd.DataFrame, dict]:
    """
    Lee el Excel OFB del contador.
    Retorna DataFrame normalizado con columnas estándar y metadata.
    """
    try:
        df_raw = pd.read_excel(io.BytesIO(file_bytes), dtype=str, engine="openpyxl")
    except Exception as e:
        raise ValueError(f"No se pudo leer el archivo OFB: {e}")

    cols = list(df_raw.columns)

    # Validar que tiene las columnas esperadas
    expected = ["UUID", "RFC Emisor", "Nombre Emisor", "Total", "FechaEmisionXML"]
    missing = [c for c in expected if c not in cols]
    if missing:
        raise ValueError(
            f"El archivo OFB no tiene las columnas esperadas: {missing}\n"
            f"Columnas encontradas: {cols}"
        )

    df = pd.DataFrame()
    df["uuid"]         = df_raw["UUID"].astype(str).str.strip().str.upper()
    df["rfc_emisor"]   = df_raw["RFC Emisor"].astype(str).str.strip().str.upper()
    df["proveedor"]    = df_raw["Nombre Emisor"].astype(str).str.strip().str.upper()
    df["total"]        = pd.to_numeric(
        df_raw["Total"].astype(str).str.replace(",", "", regex=False).str.strip(),
        errors="coerce"
    )
    df["moneda"]       = df_raw["Moneda"].astype(str).str.strip() if "Moneda" in cols else "MXN"
    df["tipo"]         = df_raw["TipoComprobante"].astype(str).str.strip() if "TipoComprobante" in cols else ""
    df["estado_sat"]   = df_raw["Estado SAT"].astype(str).str.strip() if "Estado SAT" in cols else ""

    # Folio completo = Serie + Folio
    serie = df_raw["Serie"].astype(str).str.strip().replace("nan", "") if "Serie" in cols else pd.Series([""] * len(df_raw))
    folio = df_raw["Folio"].astype(str).str.strip().replace("nan", "") if "Folio" in cols else pd.Series([""] * len(df_raw))
    df["folio"] = (serie + folio).str.strip()
    df["folio_num"] = df_raw["Folio"].astype(str).str.strip() if "Folio" in cols else ""

    # Fecha
    df["fecha"] = pd.to_datetime(df_raw["FechaEmisionXML"], errors="coerce")

    # Solo facturas de Ingreso (las que debe registrar en SISOR)
    if "tipo" in df.columns and df["tipo"].notna().any():
        df = df[df["tipo"].str.startswith("I")]

    df = df.dropna(subset=["uuid"]).reset_index(drop=True)
    df = df[df["uuid"] != "NAN"].reset_index(drop=True)
    df = df.sort_values("fecha", ascending=False).reset_index(drop=True)

    meta = {
        "total_original": len(df_raw),
        "total_ingreso": len(df),
        "all_columns": cols,
        "source": "ofb",
    }

    return df, meta
