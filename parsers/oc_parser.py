"""
Parser del archivo SEGUIMIENTO_OC.xlsx (Órdenes de Compra).

Estructura del archivo:
  Fila 1: Título "Seguimiento de O.C." (ignorar)
  Fila 2: Encabezados (header=1 en pandas)
  Datos: Fila 3 en adelante (~5,000 filas históricas)

Columnas por posición:
  A=NOMEMPRE, B=SEMANA, C=PEDIDO, D=FOLIO_EXPLOSION, E=FECHA,
  F=OC, G=RENGLON, H=PROVEE, I=NOMBREPROV, J=FAMILIA, K=MATERIAL,
  L=CANTIDAD, M=FACTURADO, N=PENDIENTE, O=UNIDAD, P=COSTO1,
  Q=MONEDA, R=TOTAL, S=FECENTREGA, T=MOTIVO
"""
import io
import re
import pandas as pd
from datetime import date, timedelta
from typing import Tuple


# Mapeo de posición de columna → nombre interno
_COL_MAP = {
    0:  "empresa",
    1:  "semana",
    2:  "pedido",
    3:  "folio_explosion",
    4:  "fecha",
    5:  "oc",
    6:  "renglon",
    7:  "proveedor_cod",
    8:  "proveedor",
    9:  "familia",
    10: "material",
    11: "cantidad",
    12: "facturado",
    13: "pendiente",
    14: "unidad",
    15: "costo",
    16: "moneda",
    17: "total",
    18: "fecha_entrega",
    19: "motivo",
}


def parse_oc(
    file_bytes: bytes,
    filename: str = "",
    semanas_atras: int = 8,
) -> Tuple[pd.DataFrame, dict]:
    """
    Lee SEGUIMIENTO_OC.xlsx y filtra a las últimas `semanas_atras` semanas.
    Retorna (df_filtrado, meta) donde meta contiene estadísticas de la carga.
    """
    ext = filename.lower().split(".")[-1] if filename else "xlsx"
    engine = "xlrd" if ext == "xls" else "openpyxl"

    # Intentar con header=1 primero (fila 1 = título, fila 2 = encabezados)
    # Si falla o da menos de 3 columnas con datos, intentar header=0
    df_raw = None
    last_err = None
    for hdr in (1, 0, 2):
        try:
            df_try = pd.read_excel(
                io.BytesIO(file_bytes),
                header=hdr,
                dtype=str,
                engine=engine,
            )
            named = [c for c in df_try.columns if not str(c).startswith("Unnamed")]
            if len(named) >= 3 and len(df_try) > 0:
                df_raw = df_try
                break
        except Exception as e:
            last_err = e

    if df_raw is None:
        raise ValueError(f"No se pudo leer el archivo de OC: {last_err}")

    total_filas = len(df_raw)

    if total_filas == 0:
        return pd.DataFrame(), {"total_filas": 0, "filas_cargadas": 0, "semanas_atras": semanas_atras}

    # Renombrar columnas por posición (ignorar nombres originales para robustez)
    n_cols = len(df_raw.columns)
    new_cols = [f"_col{i}" for i in range(n_cols)]
    for pos, name in _COL_MAP.items():
        if pos < n_cols:
            new_cols[pos] = name
    df_raw.columns = new_cols

    # Asegurar que existan las columnas mínimas
    for col in ("fecha", "oc", "renglon", "proveedor", "pendiente"):
        if col not in df_raw.columns:
            raise ValueError(
                f"No se encontró la columna '{col}' en el archivo OC.\n"
                f"Columnas detectadas: {list(df_raw.columns)}"
            )

    # Limpiar columnas clave
    df_raw["proveedor"] = (
        df_raw["proveedor"].astype(str).str.strip().str.upper()
        .str.replace(r"\s*\(\d{4}\)\s*$", "", regex=True)
        .str.strip()
    )

    # Convertir fecha — intentar varios formatos
    # NOTA: dayfirst=True sin formato explícito invierte mes/día cuando ambos son ≤12.
    # Se incluye el formato con hora porque Excel los exporta como "YYYY-MM-DD HH:MM:SS".
    fecha_raw = df_raw["fecha"].astype(str).str.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y"):
        parsed = pd.to_datetime(fecha_raw, format=fmt, errors="coerce")
        if parsed.notna().sum() > len(df_raw) * 0.5:
            df_raw["fecha"] = parsed
            break
    else:
        df_raw["fecha"] = pd.to_datetime(fecha_raw, errors="coerce", dayfirst=False)

    # Convertir fecha_entrega si existe
    if "fecha_entrega" in df_raw.columns:
        fe_raw = df_raw["fecha_entrega"].astype(str).str.strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
            fe_parsed = pd.to_datetime(fe_raw, format=fmt, errors="coerce")
            if fe_parsed.notna().sum() > fe_raw[fe_raw.str.len() > 4].count() * 0.3:
                df_raw["fecha_entrega"] = fe_parsed
                break
        else:
            df_raw["fecha_entrega"] = pd.to_datetime(fe_raw, errors="coerce", dayfirst=False)

    # Convertir numéricos
    for col in ("oc", "renglon", "semana", "cantidad", "facturado", "pendiente", "costo", "total"):
        if col in df_raw.columns:
            df_raw[col] = pd.to_numeric(
                df_raw[col].astype(str).str.replace(",", "", regex=False).str.strip(),
                errors="coerce",
            )

    # Eliminar filas sin OC o sin renglon (filas de totales / vacías)
    df_raw = df_raw.dropna(subset=["oc", "renglon"]).reset_index(drop=True)

    # ── Filtro de peso ────────────────────────────────────────────────────────
    # Incluye filas recientes (dentro de semanas_atras) MÁS todas las que
    # todavía tienen cantidad pendiente, sin importar cuándo se crearon.
    # Esto evita que OCs antiguas con saldo abierto queden sin actualizar.
    corte = pd.Timestamp(date.today() - timedelta(weeks=semanas_atras))
    mask_reciente  = df_raw["fecha"] >= corte
    mask_pendiente = df_raw["pendiente"].fillna(0) > 0
    df_filtrado = df_raw[mask_reciente | mask_pendiente].copy()

    # Diagnóstico: si el filtro dejó vacío, reportar rango real de fechas
    fecha_min = df_raw["fecha"].min()
    fecha_max = df_raw["fecha"].max()

    filas_cargadas = len(df_filtrado)

    meta = {
        "total_filas":    total_filas,
        "filas_cargadas": filas_cargadas,
        "semanas_atras":  semanas_atras,
        "fecha_corte":    corte.strftime("%d/%m/%Y"),
        "fecha_min_arch": fecha_min.strftime("%d/%m/%Y") if pd.notna(fecha_min) else "?",
        "fecha_max_arch": fecha_max.strftime("%d/%m/%Y") if pd.notna(fecha_max) else "?",
        "filas_con_fecha": int(df_raw["fecha"].notna().sum()),
    }

    return df_filtrado.reset_index(drop=True), meta
