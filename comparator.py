"""
Lógica de comparación entre facturas del OFB (contador/SAT) y facturas en SISOR.

Estrategia de match (en orden de prioridad):
  1. UUID exacto (si SISOR tiene columna UUID)
  2. Folio + Monto ±2%
  3. Nombre proveedor (contiene) + Monto ±2% + Fecha ±7 días
"""
import pandas as pd
from datetime import date


def comparar(df_ofb: pd.DataFrame, df_sisor: pd.DataFrame, sisor_meta: dict) -> dict:
    """
    Retorna diccionario con pendientes, en_sisor, modo y resumen.
    df_ofb: resultado de ofb_parser o cfdi_parser (columnas: uuid, proveedor, total, fecha, folio_num)
    df_sisor: resultado de sisor_parser
    """
    if df_ofb.empty:
        return _empty_result()

    # Determinar estrategia
    tiene_uuid_sisor = (
        "uuid" in df_sisor.columns
        and df_sisor["uuid"].notna().any()
        and (df_sisor["uuid"].astype(str).str.len() > 30).any()
    )

    if tiene_uuid_sisor:
        resultado = _match_uuid(df_ofb, df_sisor)
        modo = "uuid"
    else:
        resultado = _match_folio_monto(df_ofb, df_sisor)
        modo = "folio+monto"

    pendientes = resultado["pendientes"].copy()
    en_sisor   = resultado["en_sisor"].copy()

    # Calcular días desde timbrado hasta hoy
    hoy = pd.Timestamp(date.today())
    if not pendientes.empty and "fecha" in pendientes.columns:
        pendientes["dias_retraso"] = (hoy - pendientes["fecha"]).dt.days
        pendientes["dias_retraso"] = pendientes["dias_retraso"].clip(lower=0)

    total_ofb   = len(df_ofb)
    total_pend  = len(pendientes)
    total_ok    = len(en_sisor)
    pct_pend    = round(total_pend / total_ofb * 100, 1) if total_ofb > 0 else 0
    monto_pend  = pendientes["total"].sum() if not pendientes.empty and "total" in pendientes.columns else 0.0
    monto_ok    = en_sisor["total"].sum()   if not en_sisor.empty   and "total" in en_sisor.columns   else 0.0

    return {
        "pendientes":        pendientes.reset_index(drop=True),
        "en_sisor":          en_sisor.reset_index(drop=True),
        "modo":              modo,
        "tiene_uuid_sisor":  tiene_uuid_sisor,
        "resumen": {
            "total_cfdi":       total_ofb,
            "total_sisor_rows": len(df_sisor),
            "pendientes":       total_pend,
            "en_sisor":         total_ok,
            "pct_pendiente":    pct_pend,
            "monto_pendiente":  monto_pend,
            "monto_en_sisor":   monto_ok,
        },
    }


def _match_uuid(df_ofb: pd.DataFrame, df_sisor: pd.DataFrame) -> dict:
    uuids_sisor = set(df_sisor["uuid"].dropna().astype(str).str.upper().str.strip())
    mask = df_ofb["uuid"].astype(str).str.upper().str.strip().isin(uuids_sisor)
    return {"pendientes": df_ofb[~mask].copy(), "en_sisor": df_ofb[mask].copy()}


def _match_folio_monto(df_ofb: pd.DataFrame, df_sisor: pd.DataFrame) -> dict:
    """
    Match por:
      1. folio_num exacto + monto ±2%
      2. fallback: nombre (contains) + monto ±2% + fecha ±7 días
    """
    # Preparar sets de SISOR
    sisor_folios = {}  # folio_str -> lista de filas (importe_num, fecha_dt, proveedor)
    if "factura_str" in df_sisor.columns and "importe_num" in df_sisor.columns:
        for _, row in df_sisor.iterrows():
            f = str(row.get("factura_str", "")).strip()
            if f and f != "nan":
                if f not in sisor_folios:
                    sisor_folios[f] = []
                sisor_folios[f].append({
                    "importe": row.get("importe_num", None),
                    "fecha":   row.get("fecha_dt", None),
                    "prov":    str(row.get("proveedor", "")).upper(),
                })

    pendientes_idx = []
    en_sisor_idx   = []

    for idx, row in df_ofb.iterrows():
        folio = str(row.get("folio_num", "")).strip()
        total = row.get("total", 0)
        fecha = row.get("fecha", None)
        nombre = str(row.get("proveedor", "")).upper()

        matched = False

        # ── Estrategia 1: folio + monto ──────────────────────────────────────
        if folio and folio != "nan" and folio in sisor_folios:
            for s in sisor_folios[folio]:
                if s["importe"] is not None and total is not None:
                    diff = abs(s["importe"] - float(total)) / max(float(total), 1)
                    if diff <= 0.02:
                        matched = True
                        break

        # ── Estrategia 2: nombre + monto + fecha ─────────────────────────────
        if not matched and "importe_num" in df_sisor.columns and total:
            # Buscar candidatos con monto similar
            monto_cand = df_sisor[
                (df_sisor["importe_num"] - float(total)).abs() / max(float(total), 1) <= 0.02
            ]
            if not monto_cand.empty and "proveedor" in monto_cand.columns:
                # Verificar si el nombre del OFB aparece en el nombre del SISOR o viceversa
                nombre_corto = nombre.split()[0] if nombre else ""
                nombre_match = monto_cand[
                    monto_cand["proveedor"].astype(str).str.upper().str.contains(
                        nombre_corto, regex=False, na=False
                    )
                ]
                if not nombre_match.empty:
                    # Verificar fecha ±7 días
                    if "fecha_dt" in nombre_match.columns and pd.notna(fecha):
                        fecha_match = nombre_match[
                            (nombre_match["fecha_dt"] - fecha).abs() <= pd.Timedelta(days=7)
                        ]
                        if not fecha_match.empty:
                            matched = True
                    else:
                        matched = True  # sin fecha en SISOR, aceptar por nombre+monto

        if matched:
            en_sisor_idx.append(idx)
        else:
            pendientes_idx.append(idx)

    return {
        "pendientes": df_ofb.loc[pendientes_idx].copy(),
        "en_sisor":   df_ofb.loc[en_sisor_idx].copy(),
    }


def _empty_result() -> dict:
    empty = pd.DataFrame()
    return {
        "pendientes": empty, "en_sisor": empty,
        "modo": "—", "tiene_uuid_sisor": False,
        "resumen": {
            "total_cfdi": 0, "total_sisor_rows": 0,
            "pendientes": 0, "en_sisor": 0,
            "pct_pendiente": 0.0, "monto_pendiente": 0.0, "monto_en_sisor": 0.0,
        },
    }
