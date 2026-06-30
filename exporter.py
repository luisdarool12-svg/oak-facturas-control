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
