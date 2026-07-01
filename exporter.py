"""
Genera reporte Excel de facturas pendientes con formato profesional.
"""
import io
import pandas as pd
from datetime import date


_COLS_EXPORT = [
    ("proveedor",    "Proveedor"),
    ("rfc_emisor",   "RFC Emisor"),
    ("folio",        "Folio"),
    ("uuid",         "UUID (Folio Fiscal)"),
    ("fecha",        "Fecha Emisión"),
    ("total",        "Total"),
    ("moneda",       "Moneda"),
    ("dias_retraso", "Días de Retraso"),
]


def generar_excel(df_pendientes: pd.DataFrame, df_en_sisor: pd.DataFrame, resumen: dict) -> bytes:
    buffer = io.BytesIO()

    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        wb = writer.book

        # --- Formatos ---
        fmt_titulo = wb.add_format({
            "bold": True, "font_size": 14, "font_color": "#FFFFFF",
            "bg_color": "#1a2e4a", "align": "center", "valign": "vcenter",
        })
        fmt_header = wb.add_format({
            "bold": True, "font_color": "#FFFFFF", "bg_color": "#2563EB",
            "border": 1, "align": "center",
        })
        fmt_header_ok = wb.add_format({
            "bold": True, "font_color": "#FFFFFF", "bg_color": "#16A34A",
            "border": 1, "align": "center",
        })
        fmt_money = wb.add_format({
            "num_format": '"$"#,##0.00', "border": 1,
        })
        fmt_date = wb.add_format({
            "num_format": "DD/MM/YYYY", "border": 1, "align": "center",
        })
        fmt_cell = wb.add_format({"border": 1})
        fmt_cell_red = wb.add_format({
            "border": 1, "bg_color": "#FEF2F2", "font_color": "#DC2626",
        })
        fmt_num = wb.add_format({
            "border": 1, "align": "center", "num_format": "0",
        })
        fmt_resumen_label = wb.add_format({
            "bold": True, "bg_color": "#F1F5F9", "border": 1,
        })
        fmt_resumen_val = wb.add_format({
            "border": 1, "align": "right",
        })
        fmt_resumen_money = wb.add_format({
            "border": 1, "align": "right", "num_format": '"$"#,##0.00',
        })

        # === Hoja 1: Pendientes ===
        _write_sheet(
            writer, wb, df_pendientes,
            sheet_name="Facturas Pendientes",
            fmt_titulo=fmt_titulo,
            fmt_header=fmt_header,
            fmt_money=fmt_money,
            fmt_date=fmt_date,
            fmt_cell=fmt_cell,
            fmt_cell_colored=fmt_cell_red,
            fmt_num=fmt_num,
            color_header="#2563EB",
            title=f"FACTURAS TIMBRADAS NO RECIBIDAS — {date.today().strftime('%d/%m/%Y')}",
        )

        # === Hoja 2: Ya en SISOR ===
        _write_sheet(
            writer, wb, df_en_sisor,
            sheet_name="Ya en SISOR",
            fmt_titulo=fmt_titulo,
            fmt_header=fmt_header_ok,
            fmt_money=fmt_money,
            fmt_date=fmt_date,
            fmt_cell=fmt_cell,
            fmt_cell_colored=fmt_cell,
            fmt_num=fmt_num,
            color_header="#16A34A",
            title=f"FACTURAS YA REGISTRADAS EN SISOR — {date.today().strftime('%d/%m/%Y')}",
        )

        # === Hoja 3: Resumen ejecutivo ===
        ws = wb.add_worksheet("Resumen")
        writer.sheets["Resumen"] = ws
        ws.set_column(0, 0, 35)
        ws.set_column(1, 1, 20)
        ws.merge_range("A1:B1", "RESUMEN EJECUTIVO — CONCILIACIÓN CFDI vs SISOR", fmt_titulo)
        ws.set_row(0, 30)

        rows = [
            ("Fecha de corte",          date.today().strftime("%d/%m/%Y")),
            ("Total CFDIs del SAT",     resumen["total_cfdi"]),
            ("Registradas en SISOR",    resumen["en_sisor"]),
            ("TIMBRADAS no recibidas",  resumen["pendientes"]),
            ("% pendiente",             f"{resumen['pct_pendiente']}%"),
        ]
        for i, (label, val) in enumerate(rows, start=1):
            ws.write(i, 0, label, fmt_resumen_label)
            ws.write(i, 1, val, fmt_resumen_val)

        ws.write(len(rows) + 1, 0, "Monto total pendiente",  fmt_resumen_label)
        ws.write(len(rows) + 1, 1, resumen["monto_pendiente"], fmt_resumen_money)
        ws.write(len(rows) + 2, 0, "Monto total en SISOR",   fmt_resumen_label)
        ws.write(len(rows) + 2, 1, resumen["monto_en_sisor"],  fmt_resumen_money)

    return buffer.getvalue()


def _write_sheet(writer, wb, df: pd.DataFrame, sheet_name: str,
                 fmt_titulo, fmt_header, fmt_money, fmt_date,
                 fmt_cell, fmt_cell_colored, fmt_num,
                 color_header: str, title: str):
    ws = wb.add_worksheet(sheet_name)
    writer.sheets[sheet_name] = ws

    # Título
    n_cols = len(_COLS_EXPORT)
    ws.merge_range(0, 0, 0, n_cols - 1, title, fmt_titulo)
    ws.set_row(0, 28)

    # Cabeceras
    visible_cols = [c for c, _ in _COLS_EXPORT if c in df.columns or c == "dias_retraso"]
    headers = [label for col, label in _COLS_EXPORT
               if col in df.columns or (col == "dias_retraso" and "dias_retraso" in df.columns)]

    for j, h in enumerate(headers):
        ws.write(1, j, h, fmt_header)
        ws.set_column(j, j, _col_width(h))

    if df.empty:
        ws.write(2, 0, "Sin registros", fmt_cell)
        return

    col_names = [c for c, _ in _COLS_EXPORT if c in df.columns]

    for i, (_, row) in enumerate(df[col_names].iterrows(), start=2):
        for j, col in enumerate(col_names):
            val = row[col]
            if col == "total":
                ws.write_number(i, j, float(val) if pd.notna(val) else 0, fmt_money)
            elif col == "fecha":
                if pd.notna(val):
                    ws.write_datetime(i, j, val.to_pydatetime(), fmt_date)
                else:
                    ws.write(i, j, "", fmt_cell)
            elif col == "dias_retraso":
                ws.write_number(i, j, int(val) if pd.notna(val) else 0, fmt_num)
            else:
                ws.write(i, j, str(val) if pd.notna(val) else "", fmt_cell)


def _col_width(header: str) -> int:
    widths = {
        "Proveedor": 35,
        "RFC Emisor": 16,
        "Folio": 12,
        "UUID (Folio Fiscal)": 38,
        "Fecha Emisión": 14,
        "Total": 14,
        "Moneda": 9,
        "Días de Retraso": 16,
    }
    return widths.get(header, 15)


# ─── Reporte Mensual ──────────────────────────────────────────────────────────

_COLS_OC = [
    ("oc",           "OC #"),
    ("fecha",        "Fecha OC"),
    ("proveedor",    "Proveedor"),
    ("familia",      "Familia"),
    ("material",     "Material"),
    ("cantidad",     "Cantidad"),
    ("unidad",       "Unidad"),
    ("costo",        "Costo Unit."),
    ("moneda",       "Moneda"),
    ("total",        "Total OC"),
    ("pendiente",    "Pendiente"),
    ("fecha_entrega","Fecha Entrega"),
    ("pedido",       "Pedido"),
]

_COLS_RECEP = [
    ("proveedor",     "Proveedor"),
    ("familia",       "Familia"),
    ("factura",       "Folio Factura"),
    ("uuid",          "UUID (Folio Fiscal)"),
    ("rfc_emisor",    "RFC Emisor"),
    ("importe",       "Importe"),
    ("fecha_factura", "Fecha Factura"),
    ("fecha_captura", "Fecha Captura SISOR"),
]

_COLS_PEND_MES = [
    ("proveedor",      "Proveedor"),
    ("familia",        "Familia"),
    ("rfc_emisor",     "RFC Emisor"),
    ("folio",          "Folio"),
    ("uuid",           "UUID (Folio Fiscal)"),
    ("fecha",          "Fecha Timbre"),
    ("total",          "Total"),
    ("moneda",         "Moneda"),
    ("dias_pendiente", "Días Pendiente"),
]


def exportar_reporte_mensual(
    df_oc: pd.DataFrame,
    df_recep: pd.DataFrame,
    df_pendientes: pd.DataFrame,
    mes_label: str,
    resumen: dict,
) -> bytes:
    """
    Genera Excel con 4 hojas:
      1. OC Colocadas — órdenes de compra del mes
      2. Facturas Ingresadas — facturas recepcionadas en SISOR del mes
      3. Timbradas No Ingresadas — facturas SAT sin recepción en SISOR
      4. Resumen — métricas consolidadas
    """
    buffer = io.BytesIO()

    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        wb = writer.book

        # ── Formatos comunes ─────────────────────────────────────────────────
        navy  = "#0D1B2A"
        gold  = "#C8A951"
        green = "#16A34A"

        fmt_titulo = wb.add_format({
            "bold": True, "font_size": 13, "font_color": "#FFFFFF",
            "bg_color": navy, "align": "center", "valign": "vcenter",
        })
        fmt_header_oc = wb.add_format({
            "bold": True, "font_color": "#FFFFFF", "bg_color": "#1E3A5F",
            "border": 1, "align": "center",
        })
        fmt_header_rec = wb.add_format({
            "bold": True, "font_color": "#FFFFFF", "bg_color": green,
            "border": 1, "align": "center",
        })
        fmt_money  = wb.add_format({"num_format": '"$"#,##0.00', "border": 1})
        fmt_num    = wb.add_format({"border": 1, "align": "center"})
        fmt_date   = wb.add_format({"num_format": "DD/MM/YYYY", "border": 1, "align": "center"})
        fmt_cell   = wb.add_format({"border": 1})
        fmt_res_lbl = wb.add_format({"bold": True, "bg_color": "#F1F5F9", "border": 1})
        fmt_res_val = wb.add_format({"border": 1, "align": "right"})
        fmt_res_mon = wb.add_format({"border": 1, "align": "right", "num_format": '"$"#,##0.00'})
        fmt_subtotal = wb.add_format({
            "bold": True, "bg_color": "#E8F4FD", "border": 1,
            "num_format": '"$"#,##0.00',
        })
        fmt_subtotal_lbl = wb.add_format({
            "bold": True, "bg_color": "#E8F4FD", "border": 1,
        })

        # ── Hoja 1: OC Colocadas ─────────────────────────────────────────────
        ws_oc = wb.add_worksheet("OC Colocadas")
        writer.sheets["OC Colocadas"] = ws_oc

        ws_oc.merge_range(
            0, 0, 0, len(_COLS_OC) - 1,
            f"ÓRDENES DE COMPRA COLOCADAS — {mes_label.upper()}",
            fmt_titulo,
        )
        ws_oc.set_row(0, 28)

        col_widths_oc = {
            "OC #": 8, "Fecha OC": 13, "Proveedor": 32, "Familia": 16,
            "Material": 30, "Cantidad": 10, "Unidad": 8, "Costo Unit.": 14,
            "Moneda": 8, "Total OC": 14, "Pendiente": 12,
            "Fecha Entrega": 14, "Pedido": 12,
        }
        visible_oc = [(col, lbl) for col, lbl in _COLS_OC if col in (df_oc.columns if not df_oc.empty else [])]
        for j, (col, lbl) in enumerate(visible_oc):
            ws_oc.write(1, j, lbl, fmt_header_oc)
            ws_oc.set_column(j, j, col_widths_oc.get(lbl, 14))

        if df_oc.empty:
            ws_oc.write(2, 0, "Sin órdenes de compra en este mes.", fmt_cell)
        else:
            for i, (_, row) in enumerate(df_oc[[c for c, _ in visible_oc]].iterrows(), start=2):
                for j, (col, _) in enumerate(visible_oc):
                    val = row[col]
                    if col in ("total", "costo", "pendiente"):
                        ws_oc.write_number(i, j, float(val) if pd.notna(val) else 0.0, fmt_money)
                    elif col == "cantidad":
                        ws_oc.write_number(i, j, float(val) if pd.notna(val) else 0.0, fmt_num)
                    elif col in ("fecha", "fecha_entrega"):
                        if pd.notna(val):
                            try:
                                dt = pd.to_datetime(val)
                                ws_oc.write_datetime(i, j, dt.to_pydatetime(), fmt_date)
                            except Exception:
                                ws_oc.write(i, j, str(val), fmt_cell)
                        else:
                            ws_oc.write(i, j, "", fmt_cell)
                    elif col == "oc":
                        ws_oc.write_number(i, j, int(val) if pd.notna(val) else 0, fmt_num)
                    else:
                        ws_oc.write(i, j, str(val) if pd.notna(val) else "", fmt_cell)

            # Subtotal
            sub_row = len(df_oc) + 2
            ws_oc.write(sub_row, 0, f"TOTAL — {len(df_oc)} renglones", fmt_subtotal_lbl)
            total_col_idx = next((j for j, (c, _) in enumerate(visible_oc) if c == "total"), None)
            if total_col_idx is not None:
                ws_oc.write_number(sub_row, total_col_idx, resumen.get("total_oc", 0.0), fmt_subtotal)

        # ── Hoja 2: Compras Recepcionadas ────────────────────────────────────
        ws_rec = wb.add_worksheet("Compras Recepcionadas")
        writer.sheets["Compras Recepcionadas"] = ws_rec

        titulo_rec = f"COMPRAS RECEPCIONADAS (COTEJADAS VS XML) — {mes_label.upper()}"
        ws_rec.merge_range(0, 0, 0, len(_COLS_RECEP) - 1, titulo_rec, fmt_titulo)
        ws_rec.set_row(0, 28)

        col_widths_rec = {
            "Proveedor": 32, "Familia": 22, "Folio Factura": 18, "UUID (Folio Fiscal)": 38,
            "RFC Emisor": 16, "Importe": 14,
            "Fecha Factura": 14, "Fecha Captura SISOR": 20,
        }
        visible_rec = [(col, lbl) for col, lbl in _COLS_RECEP if col in (df_recep.columns if not df_recep.empty else [])]
        for j, (col, lbl) in enumerate(visible_rec):
            ws_rec.write(1, j, lbl, fmt_header_rec)
            ws_rec.set_column(j, j, col_widths_rec.get(lbl, 14))

        if df_recep.empty:
            ws_rec.write(2, 0, "Sin compras recepcionadas en este mes.", fmt_cell)
        else:
            for i, (_, row) in enumerate(df_recep[[c for c, _ in visible_rec]].iterrows(), start=2):
                for j, (col, _) in enumerate(visible_rec):
                    val = row[col]
                    if col == "importe":
                        ws_rec.write_number(i, j, float(val) if pd.notna(val) else 0.0, fmt_money)
                    elif col in ("fecha_factura", "fecha_captura"):
                        if pd.notna(val) and str(val).strip():
                            try:
                                dt = pd.to_datetime(val)
                                ws_rec.write_datetime(i, j, dt.to_pydatetime(), fmt_date)
                            except Exception:
                                ws_rec.write(i, j, str(val), fmt_cell)
                        else:
                            ws_rec.write(i, j, "", fmt_cell)
                    else:
                        ws_rec.write(i, j, str(val) if pd.notna(val) else "", fmt_cell)

            sub_row_rec = len(df_recep) + 2
            ws_rec.write(sub_row_rec, 0, f"TOTAL — {len(df_recep)} facturas", fmt_subtotal_lbl)
            importe_idx = next((j for j, (c, _) in enumerate(visible_rec) if c == "importe"), None)
            if importe_idx is not None:
                ws_rec.write_number(sub_row_rec, importe_idx, resumen.get("total_recepcionadas", 0.0), fmt_subtotal)

        # ── Hoja 3: Timbradas No Ingresadas ─────────────────────────────────
        fmt_header_pend = wb.add_format({
            "bold": True, "font_color": "#FFFFFF", "bg_color": "#B91C1C",
            "border": 1, "align": "center",
        })
        fmt_dias_rojo  = wb.add_format({"border": 1, "align": "center", "bg_color": "#FEE2E2", "font_color": "#991B1B", "bold": True})
        fmt_dias_ambar = wb.add_format({"border": 1, "align": "center", "bg_color": "#FEF3C7", "font_color": "#92400E", "bold": True})
        fmt_dias_ok    = wb.add_format({"border": 1, "align": "center"})

        ws_pend = wb.add_worksheet("Timbradas No Ingresadas")
        writer.sheets["Timbradas No Ingresadas"] = ws_pend

        titulo_pend = f"FACTURAS TIMBRADAS NO INGRESADAS EN SISOR — {mes_label.upper()}"
        ws_pend.merge_range(0, 0, 0, len(_COLS_PEND_MES) - 1, titulo_pend, fmt_titulo)
        ws_pend.set_row(0, 28)

        col_widths_pend = {
            "Proveedor": 32, "Familia": 22, "RFC Emisor": 16, "Folio": 16,
            "UUID (Folio Fiscal)": 38, "Fecha Timbre": 14,
            "Total": 14, "Moneda": 8, "Días Pendiente": 14,
        }
        visible_pend = [
            (col, lbl) for col, lbl in _COLS_PEND_MES
            if col in (df_pendientes.columns if not df_pendientes.empty else [])
        ]
        for j, (col, lbl) in enumerate(visible_pend):
            ws_pend.write(1, j, lbl, fmt_header_pend)
            ws_pend.set_column(j, j, col_widths_pend.get(lbl, 14))

        if df_pendientes.empty:
            ws_pend.write(2, 0, "✅ Todas las facturas timbradas del mes fueron ingresadas en SISOR.", fmt_cell)
        else:
            for i, (_, row) in enumerate(df_pendientes[[c for c, _ in visible_pend]].iterrows(), start=2):
                for j, (col, _) in enumerate(visible_pend):
                    val = row[col]
                    if col == "total":
                        ws_pend.write_number(i, j, float(val) if pd.notna(val) else 0.0, fmt_money)
                    elif col == "fecha":
                        if pd.notna(val) and str(val).strip():
                            try:
                                dt = pd.to_datetime(val)
                                ws_pend.write_datetime(i, j, dt.to_pydatetime(), fmt_date)
                            except Exception:
                                ws_pend.write(i, j, str(val), fmt_cell)
                        else:
                            ws_pend.write(i, j, "", fmt_cell)
                    elif col == "dias_pendiente":
                        try:
                            dias = int(val) if pd.notna(val) else 0
                            fmt_d = fmt_dias_rojo if dias > 30 else (fmt_dias_ambar if dias > 7 else fmt_dias_ok)
                            ws_pend.write_number(i, j, dias, fmt_d)
                        except (TypeError, ValueError):
                            ws_pend.write(i, j, str(val) if pd.notna(val) else "", fmt_cell)
                    else:
                        ws_pend.write(i, j, str(val) if pd.notna(val) else "", fmt_cell)

            sub_row_pend = len(df_pendientes) + 2
            ws_pend.write(sub_row_pend, 0, f"TOTAL — {len(df_pendientes)} facturas sin ingresar", fmt_subtotal_lbl)
            total_idx_pend = next((j for j, (c, _) in enumerate(visible_pend) if c == "total"), None)
            if total_idx_pend is not None:
                ws_pend.write_number(sub_row_pend, total_idx_pend, resumen.get("total_pendientes", 0.0), fmt_subtotal)

        # ── Hoja 4: Resumen ──────────────────────────────────────────────────
        ws_res = wb.add_worksheet("Resumen")
        writer.sheets["Resumen"] = ws_res
        ws_res.set_column(0, 0, 42)
        ws_res.set_column(1, 1, 22)
        ws_res.merge_range(
            "A1:B1",
            f"REPORTE MENSUAL — {mes_label.upper()}",
            fmt_titulo,
        )
        ws_res.set_row(0, 30)

        n_timbradas   = resumen.get("total_timbradas", resumen.get("n_recepcionadas", 0) + resumen.get("n_pendientes", 0))
        pct_ingresadas = resumen.get("pct_ingresadas", 0.0)
        fmt_pct_verde = wb.add_format({"border": 1, "align": "right", "font_color": "#15803D", "bold": True})
        fmt_pct_ambar = wb.add_format({"border": 1, "align": "right", "font_color": "#B45309", "bold": True})
        fmt_pct_rojo  = wb.add_format({"border": 1, "align": "right", "font_color": "#B91C1C", "bold": True})
        fmt_pct = fmt_pct_verde if pct_ingresadas >= 90 else (fmt_pct_ambar if pct_ingresadas >= 70 else fmt_pct_rojo)

        filas_res = [
            ("Período",                              mes_label,                                    None),
            ("Fecha de generación",                  date.today().strftime("%d/%m/%Y"),             None),
            ("── ÓRDENES DE COMPRA ──",              "",                                            None),
            ("OCs colocadas (renglones)",             resumen.get("n_oc", 0),                       None),
            ("OCs únicas",                           resumen.get("ocs_unicas", 0),                  None),
            ("Monto total OC",                       None,                                          resumen.get("total_oc", 0.0)),
            ("── FACTURAS ──",                       "",                                            None),
            ("Facturas timbradas en SAT (total)",    n_timbradas,                                  None),
            ("Facturas ingresadas en SISOR",         resumen.get("n_recepcionadas", 0),             None),
            ("Monto ingresado en SISOR",             None,                                          resumen.get("total_recepcionadas", 0.0)),
            ("Facturas timbradas NO ingresadas",     resumen.get("n_pendientes", 0),               None),
            ("Monto pendiente de ingresar",          None,                                          resumen.get("total_pendientes", 0.0)),
            ("% Facturas recibidas vs timbradas",    None,                                          None),
        ]

        fmt_seccion = wb.add_format({
            "bold": True, "bg_color": "#0D1B2A", "font_color": "#C8A951",
            "border": 1,
        })

        for i, (lbl, val, mon) in enumerate(filas_res, start=1):
            if lbl.startswith("──"):
                ws_res.write(i, 0, lbl, fmt_seccion)
                ws_res.write(i, 1, "", fmt_seccion)
            elif mon is not None:
                ws_res.write(i, 0, lbl, fmt_res_lbl)
                ws_res.write_number(i, 1, mon, fmt_res_mon)
            elif lbl == "% Facturas recibidas vs timbradas":
                ws_res.write(i, 0, lbl, fmt_res_lbl)
                ws_res.write(i, 1, f"{pct_ingresadas:.1f}%  ({resumen.get('n_recepcionadas',0)} de {n_timbradas})", fmt_pct)
            else:
                ws_res.write(i, 0, lbl, fmt_res_lbl)
                ws_res.write(i, 1, val, fmt_res_val)

    return buffer.getvalue()
