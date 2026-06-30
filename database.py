"""
Capa de persistencia Supabase para el control de facturas.
Tablas: oak_facturas_ofb, oak_sisor_entradas, oak_ordenes_compra, oak_runs_comparacion
"""
import re
import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Tuple, Optional, Dict, Any, List
from supabase import create_client, Client

_OFB   = "oak_facturas_ofb"
_SISOR = "oak_sisor_entradas"
_OC    = "oak_ordenes_compra"
_RUNS  = "oak_runs_comparacion"


# ─── Cliente ──────────────────────────────────────────────────────────────────

@st.cache_resource
def _sb() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _val(v: Any) -> Optional[str]:
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, (pd.Timestamp, datetime)):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    s = str(v).strip()
    return s if s and s.lower() not in ("nan", "none", "nat", "0000-00-00") else None


def _float(v: Any) -> Optional[float]:
    try:
        if pd.isna(v):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _fetch_all(table: str, columns: str = "*") -> List[dict]:
    """Descarga todas las filas de una tabla manejando paginación de 1 000 filas."""
    sb = _sb()
    data, start, page = [], 0, 1000
    while True:
        result = sb.table(table).select(columns).range(start, start + page - 1).execute()
        data.extend(result.data)
        if len(result.data) < page:
            break
        start += page
    return data


def _upsert(table: str, records: List[dict], on_conflict: str,
            ignore_duplicates: bool = False, batch: int = 500) -> None:
    sb = _sb()
    for i in range(0, len(records), batch):
        sb.table(table).upsert(
            records[i:i + batch],
            on_conflict=on_conflict,
            ignore_duplicates=ignore_duplicates,
        ).execute()


# ─── Inicialización ────────────────────────────────────────────────────────────

def init_db() -> None:
    """Las tablas se crean en el dashboard de Supabase. Esta función es un no-op."""
    pass


# ─── facturas_ofb ─────────────────────────────────────────────────────────────

def insertar_facturas_ofb(df: pd.DataFrame, archivo_origen: str) -> Tuple[int, int]:
    if df.empty:
        return 0, 0

    # Contar existentes antes
    sb = _sb()
    antes = sb.table(_OFB).select("id", count="exact").limit(0).execute().count or 0

    now = datetime.now().isoformat(timespec="seconds")
    records = [
        {
            "uuid":           _val(row.get("uuid")),
            "rfc_emisor":     _val(row.get("rfc_emisor")),
            "proveedor":      _val(row.get("proveedor")),
            "total":          _float(row.get("total")),
            "moneda":         _val(row.get("moneda")),
            "folio":          _val(row.get("folio")),
            "folio_num":      _val(row.get("folio_num")),
            "fecha":          _val(row.get("fecha")),
            "tipo":           _val(row.get("tipo")),
            "estado_sat":     _val(row.get("estado_sat")),
            "fecha_carga":    now,
            "archivo_origen": archivo_origen,
        }
        for _, row in df.iterrows()
    ]

    _upsert(_OFB, records, on_conflict="uuid", ignore_duplicates=True)

    despues = sb.table(_OFB).select("id", count="exact").limit(0).execute().count or 0
    nuevas = despues - antes
    return nuevas, len(df) - nuevas


def eliminar_facturas_ofb(ids: list) -> int:
    if not ids:
        return 0
    sb = _sb()
    sb.table(_OFB).delete().in_("id", ids).execute()
    return len(ids)


def get_facturas_ofb() -> pd.DataFrame:
    data = _fetch_all(_OFB)
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data).sort_values(["fecha", "proveedor"], na_position="last")
    df["fecha"]     = pd.to_datetime(df["fecha"], errors="coerce")
    df["total"]     = pd.to_numeric(df["total"], errors="coerce").fillna(0.0)
    df["folio_num"] = df["folio_num"].fillna("").astype(str)
    return df.reset_index(drop=True)


# ─── sisor_entradas ───────────────────────────────────────────────────────────

def _normalizar_fecha_iso(valor) -> Optional[str]:
    if valor is None:
        return None
    s = str(valor).strip()
    if not s or s.lower() in ("nan", "none", "nat"):
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}", s):
        return s[:10]
    m = re.match(r"^(\d{2})[-/](\d{2})[-/](\d{4})", s)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return None


def insertar_sisor(df: pd.DataFrame, archivo_origen: str) -> Tuple[int, int, list]:
    if df.empty:
        return 0, 0, []

    sb = _sb()
    now = datetime.now().isoformat(timespec="seconds")

    # Borrar registros del mismo archivo
    sb.table(_SISOR).delete().eq("archivo_origen", archivo_origen).execute()

    # Fechas ya existentes en otros archivos
    existing = _fetch_all(_SISOR, "fecha_captura")
    fechas_existentes = {
        r["fecha_captura"][:10]
        for r in existing
        if r.get("fecha_captura")
    }

    records, omitidas, fechas_omitidas = [], 0, set()
    for _, row in df.iterrows():
        fecha_cap = _normalizar_fecha_iso(row.get("fecha_captura"))
        if fecha_cap and fecha_cap in fechas_existentes:
            omitidas += 1
            fechas_omitidas.add(fecha_cap)
            continue
        records.append({
            "proveedor":      _val(row.get("proveedor")),
            "factura":        _val(row.get("factura")),
            "importe":        _float(row.get("importe_num", row.get("importe"))),
            "fecha_factura":  _val(row.get("fecha_factura")),
            "fecha_captura":  fecha_cap,
            "fecha_carga":    now,
            "archivo_origen": archivo_origen,
        })

    if records:
        sb2 = _sb()
        for i in range(0, len(records), 500):
            sb2.table(_SISOR).insert(records[i:i + 500]).execute()

    return len(records), omitidas, sorted(fechas_omitidas)


def limpiar_sisor() -> int:
    sb = _sb()
    count = sb.table(_SISOR).select("id", count="exact").limit(0).execute().count or 0
    sb.table(_SISOR).delete().gt("id", 0).execute()
    return count


def get_sisor_entradas() -> pd.DataFrame:
    data = _fetch_all(_SISOR)
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data).sort_values(["fecha_factura", "proveedor"], na_position="last")
    df["importe_num"] = pd.to_numeric(df["importe"], errors="coerce")
    df["factura_str"] = df["factura"].fillna("").astype(str).str.strip()
    df["fecha_dt"]    = pd.to_datetime(df["fecha_factura"], errors="coerce", dayfirst=True)
    df["proveedor"]   = df["proveedor"].fillna("").astype(str).str.upper().str.strip()
    return df.reset_index(drop=True)


# ─── ordenes_compra ───────────────────────────────────────────────────────────

def insertar_oc(df: pd.DataFrame, archivo_origen: str) -> Tuple[int, int]:
    if df.empty:
        return 0, 0

    now = datetime.now().isoformat(timespec="seconds")

    # Claves existentes para calcular nuevas vs actualizadas
    sb = _sb()
    existing_raw = _fetch_all(_OC, "oc,renglon")
    existentes = {(r["oc"], r["renglon"]) for r in existing_raw}

    records = []
    for _, row in df.iterrows():
        oc_val  = int(float(row["oc"]))      if _val(row.get("oc"))      else None
        ren_val = int(float(row["renglon"])) if _val(row.get("renglon")) else None
        records.append({
            "oc":              oc_val,
            "renglon":         ren_val,
            "empresa":         _val(row.get("empresa")),
            "semana":          int(float(row["semana"])) if _val(row.get("semana")) else None,
            "pedido":          _val(row.get("pedido")),
            "folio_explosion": _val(row.get("folio_explosion")),
            "fecha":           _val(row.get("fecha")),
            "proveedor_cod":   _val(row.get("proveedor_cod")),
            "proveedor":       _val(row.get("proveedor")),
            "familia":         _val(row.get("familia")),
            "material":        _val(row.get("material")),
            "cantidad":        _float(row.get("cantidad")),
            "facturado":       _float(row.get("facturado")),
            "pendiente":       _float(row.get("pendiente")),
            "unidad":          _val(row.get("unidad")),
            "costo":           _float(row.get("costo")),
            "moneda":          _val(row.get("moneda")),
            "total":           _float(row.get("total")),
            "fecha_entrega":   _val(row.get("fecha_entrega")),
            "motivo":          _val(row.get("motivo")),
            "fecha_carga":     now,
            "archivo_origen":  archivo_origen,
        })

    _upsert(_OC, records, on_conflict="oc,renglon")

    nuevas      = sum(1 for r in records if (r["oc"], r["renglon"]) not in existentes)
    actualizadas = len(records) - nuevas
    return nuevas, actualizadas


def get_oc_pendientes() -> pd.DataFrame:
    data = _fetch_all(_OC)
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    cols = ["oc", "renglon", "fecha", "proveedor", "familia", "material",
            "cantidad", "facturado", "pendiente", "unidad", "costo", "total",
            "fecha_entrega", "motivo"]
    df = df[[c for c in cols if c in df.columns]]
    for col in ["total", "pendiente", "costo"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    df = df[df["pendiente"] > 0].sort_values(["fecha", "oc", "renglon"])
    df["monto_pendiente"] = (df["pendiente"] * df["costo"]).round(2)
    return df.reset_index(drop=True)


def get_oc_proveedores_todos() -> set:
    data = _fetch_all(_OC, "proveedor")
    return {str(r["proveedor"]).upper().strip() for r in data if r.get("proveedor")}


def get_oc_total_proveedor() -> pd.DataFrame:
    data = _fetch_all(_OC)
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    df = df[df["proveedor"].notna()]
    df["proveedor"] = df["proveedor"].astype(str).str.upper().str.strip()
    df["total"] = pd.to_numeric(df["total"], errors="coerce").fillna(0.0)
    result = (
        df.groupby("proveedor")
        .agg(ocs_distintas=("oc", "nunique"), n_lineas=("oc", "count"), monto_oc=("total", "sum"))
        .reset_index()
        .sort_values("monto_oc", ascending=False)
    )
    return result


def get_oc_resumen_proveedor() -> pd.DataFrame:
    data = _fetch_all(_OC)
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    df = df[df["proveedor"].notna()].copy()
    for col in ["total", "pendiente", "costo"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    df["monto_pend_calc"] = df.apply(
        lambda r: r["pendiente"] * r["costo"] if r["pendiente"] > 0 else 0, axis=1
    )
    df["es_pendiente"] = df["pendiente"] > 0
    result = (
        df.groupby("proveedor")
        .agg(
            ocs_activas=("oc", "nunique"),
            total_comprometido=("total", "sum"),
            monto_pendiente=("monto_pend_calc", "sum"),
            renglones_pendientes=("es_pendiente", "sum"),
            primera_oc=("fecha", "min"),
            ultima_oc=("fecha", "max"),
        )
        .reset_index()
    )
    result = result[result["renglones_pendientes"] > 0].sort_values("monto_pendiente", ascending=False)
    return result.reset_index(drop=True)


# ─── runs_comparacion ─────────────────────────────────────────────────────────

def registrar_run(stats: dict) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    _sb().table(_RUNS).insert({
        "fecha_run":       now,
        "total_ofb":       stats.get("total_cfdi", 0),
        "total_sisor":     stats.get("total_sisor_rows", 0),
        "pendientes":      stats.get("pendientes", 0),
        "en_sisor":        stats.get("en_sisor", 0),
        "monto_pendiente": stats.get("monto_pendiente", 0.0),
        "monto_en_sisor":  stats.get("monto_en_sisor", 0.0),
        "modo":            stats.get("modo", "—"),
    }).execute()


def get_historial_runs(n: int = 60) -> pd.DataFrame:
    data = _fetch_all(_RUNS)
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data).sort_values("fecha_run")
    df = df.tail(n).reset_index(drop=True)
    df["fecha_run"]       = pd.to_datetime(df["fecha_run"], errors="coerce")
    for col in ["pendientes", "en_sisor", "total_ofb", "total_sisor"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    for col in ["monto_pendiente", "monto_en_sisor"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    return df


# ─── stats generales (sidebar) ───────────────────────────────────────────────

def get_stats_db() -> Dict[str, Any]:
    sb = _sb()

    n_ofb          = sb.table(_OFB).select("id", count="exact").limit(0).execute().count or 0
    n_archivos_ofb = len({r["archivo_origen"] for r in _fetch_all(_OFB, "archivo_origen") if r.get("archivo_origen")})
    n_sisor        = sb.table(_SISOR).select("id", count="exact").limit(0).execute().count or 0

    oc_data        = _fetch_all(_OC, "pendiente")
    n_oc_total     = len(oc_data)
    n_oc_pend      = sum(1 for r in oc_data if (r.get("pendiente") or 0) > 0)

    # Última carga: max de fecha_carga entre las 3 tablas
    cargas = []
    for t in [_OFB, _SISOR, _OC]:
        rows = _fetch_all(t, "fecha_carga")
        cargas.extend(r["fecha_carga"] for r in rows if r.get("fecha_carga"))

    ultima_carga = None
    if cargas:
        raw = max(cargas)
        try:
            ultima_carga = datetime.fromisoformat(raw).strftime("%d/%m/%Y %H:%M")
        except ValueError:
            ultima_carga = raw[:16]

    return {
        "n_ofb":           n_ofb,
        "n_archivos_ofb":  n_archivos_ofb,
        "n_sisor":         n_sisor,
        "n_oc_pendientes": n_oc_pend,
        "n_oc_total":      n_oc_total,
        "ultima_carga":    ultima_carga,
        "db_vacia":        (n_ofb == 0 and n_sisor == 0),
    }


# ─── actividad diaria / semanal ───────────────────────────────────────────────

def _max_fecha_captura() -> Optional[str]:
    data = _fetch_all(_SISOR, "fecha_captura")
    fechas = [r["fecha_captura"][:10] for r in data if r.get("fecha_captura")]
    return max(fechas) if fechas else None


def get_sisor_del_dia(fecha_str: Optional[str] = None) -> pd.DataFrame:
    if fecha_str is None:
        fecha_str = _max_fecha_captura()
    if fecha_str is None:
        return pd.DataFrame()
    data = _fetch_all(_SISOR)
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    df["_dia"] = df["fecha_captura"].fillna("").str[:10]
    df = df[df["_dia"] == fecha_str].drop(columns=["_dia"])
    cols = [c for c in ["proveedor", "factura", "importe", "fecha_factura", "fecha_captura"] if c in df.columns]
    df = df[cols].sort_values("proveedor") if cols else df
    if not df.empty:
        df["importe_num"] = pd.to_numeric(df["importe"], errors="coerce").fillna(0.0)
        df["factura_str"] = df["factura"].fillna("").astype(str).str.strip()
    return df.reset_index(drop=True)


def get_oc_del_dia(fecha_str: Optional[str] = None) -> pd.DataFrame:
    if fecha_str is None:
        fecha_str = _max_fecha_captura()
    if fecha_str is None:
        return pd.DataFrame()
    data = _fetch_all(_OC)
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    df["_dia"] = df["fecha"].fillna("").str[:10]
    df = df[df["_dia"] == fecha_str].drop(columns=["_dia"])
    cols = [c for c in ["oc", "proveedor", "material", "cantidad", "unidad", "costo", "total", "fecha"] if c in df.columns]
    df = df[cols].sort_values(["proveedor", "oc"]) if cols else df
    for col in ["total", "cantidad", "costo"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    return df.reset_index(drop=True)


def _get_lunes_de_semana(fecha_str: str) -> str:
    d = datetime.strptime(fecha_str, "%Y-%m-%d").date()
    return (d - timedelta(days=d.weekday())).isoformat()


def get_actividad_semanal(lunes_str: str) -> pd.DataFrame:
    lunes   = datetime.strptime(lunes_str, "%Y-%m-%d").date()
    dias    = [lunes + timedelta(days=i) for i in range(6)]
    dias_str = {d.isoformat() for d in dias}
    nombres = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]

    sisor_data = _fetch_all(_SISOR, "fecha_captura,importe")
    oc_data    = _fetch_all(_OC, "fecha,total")

    sisor_df = pd.DataFrame(sisor_data) if sisor_data else pd.DataFrame(columns=["fecha_captura", "importe"])
    oc_df    = pd.DataFrame(oc_data)    if oc_data    else pd.DataFrame(columns=["fecha", "total"])

    if not sisor_df.empty:
        sisor_df["_dia"]   = sisor_df["fecha_captura"].fillna("").str[:10]
        sisor_df["importe"] = pd.to_numeric(sisor_df["importe"], errors="coerce").fillna(0.0)
        sisor_df = sisor_df[sisor_df["_dia"].isin(dias_str)]
        sisor_grp = sisor_df.groupby("_dia").agg(n_facturas=("importe", "count"), monto_facturas=("importe", "sum")).to_dict("index")
    else:
        sisor_grp = {}

    if not oc_df.empty:
        oc_df["_dia"]  = oc_df["fecha"].fillna("").str[:10]
        oc_df["total"] = pd.to_numeric(oc_df["total"], errors="coerce").fillna(0.0)
        oc_df = oc_df[oc_df["_dia"].isin(dias_str)]
        oc_grp = oc_df.groupby("_dia").agg(n_oc=("total", "count"), monto_oc=("total", "sum")).to_dict("index")
    else:
        oc_grp = {}

    rows = []
    for i, d in enumerate(dias):
        d_str = d.isoformat()
        s = sisor_grp.get(d_str, {})
        o = oc_grp.get(d_str, {})
        rows.append({
            "fecha":          d_str,
            "dia_nombre":     nombres[i],
            "n_facturas":     int(s.get("n_facturas", 0) or 0),
            "monto_facturas": float(s.get("monto_facturas", 0) or 0),
            "n_oc":           int(o.get("n_oc", 0) or 0),
            "monto_oc":       float(o.get("monto_oc", 0) or 0),
        })

    return pd.DataFrame(rows)
