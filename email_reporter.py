"""
Genera el reporte HTML diario y lo envía por Gmail.

Requiere .env con:
  GMAIL_USER=luisdarool12@gmail.com
  GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx

Obtener App Password en: https://myaccount.google.com/apppasswords
"""
import smtplib
import ssl
import os
from datetime import date, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

import pandas as pd

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass


# ─── Logo OAK (inline PNG base64) ────────────────────────────────────────────

_OAK_LOGO_EMAIL = (
    "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"
)

# ─── Estilos ──────────────────────────────────────────────────────────────────

_ESTILOS = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

  * { box-sizing: border-box; }
  body { font-family: 'Inter', Arial, sans-serif; background: #DFE5ED; margin: 0; padding: 24px 0; }
  .wrapper { max-width: 680px; margin: 0 auto; }

  /* ── Header ejecutivo ── */
  .header {
    background: linear-gradient(160deg, #0D1B2A 0%, #0B1724 100%);
    color: white;
    padding: 0 32px;
    border-radius: 10px 10px 0 0;
    border-bottom: 2.5px solid #C8A951;
    overflow: hidden;
  }
  .header-inner {
    display: flex; justify-content: space-between; align-items: center;
    padding: 26px 0 22px;
    border-bottom: 1px solid rgba(255,255,255,.07);
  }
  .header-brand { display: flex; align-items: center; gap: 14px; }
  .header-logo { height: 28px; width: auto; display: block; flex-shrink: 0; }
  .header-divider { width: 1px; height: 28px; background: rgba(255,255,255,.18); flex-shrink: 0; }
  .header-titles .eyebrow {
    font-size: 9.5px; letter-spacing: .22em; text-transform: uppercase;
    color: #C8A951; font-weight: 700; margin-bottom: 4px;
  }
  .header-titles h1 {
    margin: 0; font-size: 17px; font-weight: 700;
    letter-spacing: -.02em; color: #F0F4F8; line-height: 1.2;
  }
  .header-meta { text-align: right; }
  .header-fecha-dia { font-size: 20px; font-weight: 700; color: #C8A951; line-height: 1; }
  .header-fecha-sub { font-size: 10.5px; color: rgba(255,255,255,.5); margin-top: 4px; }

  /* ── Sub-bar de estado ── */
  .header-status {
    display: flex; gap: 24px; padding: 11px 0;
  }
  .hstat { }
  .hstat-k { font-size: 9px; letter-spacing: .14em; text-transform: uppercase; color: rgba(255,255,255,.4); font-weight: 600; }
  .hstat-v { font-size: 13px; font-weight: 700; color: #fff; margin-top: 2px; }
  .hstat-v.gold { color: #C8A951; }
  .hstat-v.red  { color: #FCA5A5; }

  /* ── Cuerpo ── */
  .body {
    background: #FFFFFF;
    padding: 28px 32px 20px;
    border-radius: 0 0 10px 10px;
    box-shadow: 0 8px 24px rgba(13,27,42,.12);
  }

  /* ── Divisor de sección ── */
  .seccion { margin-bottom: 34px; }
  .seccion-titulo {
    display: flex; align-items: center; gap: 10px;
    margin-bottom: 18px; padding-bottom: 10px;
    border-bottom: 2px solid #F1F5F9;
  }
  .seccion-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: #C8A951; flex-shrink: 0;
  }
  .seccion h2 {
    font-size: 10px; font-weight: 700; color: #334155;
    text-transform: uppercase; letter-spacing: .13em;
    margin: 0; flex: 1;
  }
  .seccion-titulo-linea { display: none; }

  /* ── KPIs ── */
  .kpis { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 20px; }
  .kpi  {
    flex: 1; min-width: 130px;
    background: #FAFBFC;
    border: 1px solid #E8EDF2;
    border-radius: 8px;
    padding: 14px 16px;
    border-left: 4px solid #0D1B2A;
  }
  .kpi.rojo   { border-left-color: #B91C1C; background: #FFF8F8; }
  .kpi.verde  { border-left-color: #15803D; background: #F8FFF9; }
  .kpi.ambar  { border-left-color: #B45309; background: #FFFDF5; }
  .kpi.morado { border-left-color: #6D28D9; background: #FAFAFF; }
  .kpi-label  {
    font-size: 9.5px; color: #64748B; text-transform: uppercase;
    letter-spacing: .09em; font-weight: 700;
  }
  .kpi-valor  {
    font-size: 28px; font-weight: 800; color: #0D1B2A;
    line-height: 1.15; margin-top: 6px; letter-spacing: -.03em;
    font-variant-numeric: tabular-nums;
  }
  .kpi.rojo  .kpi-valor { color: #B91C1C; }
  .kpi.verde .kpi-valor { color: #15803D; }
  .kpi.ambar .kpi-valor { color: #92400E; }
  .kpi-sub { font-size: 11px; color: #94A3B8; margin-top: 4px; }

  /* ── Tablas ── */
  table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
  th    {
    background: #0D1B2A; color: #C8A951;
    font-size: 9.5px; text-transform: uppercase;
    letter-spacing: .08em; font-weight: 700;
    padding: 10px 12px; text-align: left;
  }
  th:first-child { border-radius: 4px 0 0 0; }
  th:last-child  { border-radius: 0 4px 0 0; }
  td { padding: 9px 12px; border-bottom: 1px solid #F1F5F9; color: #253545; }
  tr:nth-child(even) td { background: #FAFBFC; }
  tr:last-child td { border-bottom: none; }

  /* ── Badges ── */
  .badge-rojo  { background: #FEE2E2; color: #991B1B; padding: 3px 8px;
                 border-radius: 4px; font-size: 11px; font-weight: 700; white-space: nowrap; }
  .badge-ambar { background: #FEF3C7; color: #92400E; padding: 3px 8px;
                 border-radius: 4px; font-size: 11px; font-weight: 700; white-space: nowrap; }
  .badge-verde { background: #DCFCE7; color: #15803D; padding: 3px 8px;
                 border-radius: 4px; font-size: 11px; font-weight: 700; white-space: nowrap; }

  /* ── Filas de alerta ── */
  .row-rojo  td { background: #FFF5F5 !important; }
  .row-ambar td { background: #FFFBEB !important; }
  .semana-total td { background: #F1F5F9 !important; font-weight: 700; color: #0D1B2A; }

  /* ── Presupuesto barra ── */
  .presup-barra-wrap { background: #E2E8F0; border-radius: 99px; height: 14px; overflow: hidden; margin: 14px 0 6px; }
  .presup-barra-fill { height: 100%; border-radius: 99px; }
  .presup-verde { background: linear-gradient(90deg, #15803D 0%, #16A34A 100%); }
  .presup-ambar { background: linear-gradient(90deg, #B45309 0%, #D97706 100%); }
  .presup-rojo  { background: linear-gradient(90deg, #B91C1C 0%, #DC2626 100%); }
  .presup-meta  { display: flex; justify-content: space-between; font-size: 11px; color: #64748B; margin-top: 4px; }
  .presup-alerta {
    border-radius: 6px; padding: 10px 14px; margin-top: 14px;
    font-size: 12px; line-height: 1.5;
  }
  .presup-alerta.verde { background: #F0FDF4; border-left: 3px solid #15803D; color: #14532D; }
  .presup-alerta.ambar { background: #FFFBEB; border-left: 3px solid #D97706; color: #78350F; }
  .presup-alerta.rojo  { background: #FFF5F5; border-left: 3px solid #DC2626; color: #7F1D1D; }

  /* ── Footer ── */
  .footer {
    text-align: center; font-size: 10.5px; color: #94A3B8;
    margin-top: 22px; padding: 16px 0 4px;
    border-top: 1px solid #E8EDF2;
  }
  .footer-brand { font-weight: 700; color: #0D1B2A; font-size: 11px; }
  .footer-dot { color: #C8A951; margin: 0 5px; }
</style>
"""


# ─── Presupuesto semanal ──────────────────────────────────────────────────────
PRESUPUESTO_SEMANAL = 500_000.0


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _mxn(v: float) -> str:
    return f"${v:,.0f}"


def _dias_badge(dias: int) -> str:
    if dias > 30:
        return f'<span class="badge-rojo">{dias}d</span>'
    if dias > 7:
        return f'<span class="badge-ambar">{dias}d</span>'
    return f'<span class="badge-verde">{dias}d</span>'


def _row_class(dias: int) -> str:
    if dias > 30:
        return ' class="row-rojo"'
    if dias > 7:
        return ' class="row-ambar"'
    return ""


def _fmt_fecha(s: str) -> str:
    try:
        return datetime.strptime(s, "%Y-%m-%d").strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return str(s)


# ─── Secciones ────────────────────────────────────────────────────────────────

def _seccion_presupuesto(df_semana: Optional[pd.DataFrame]) -> str:
    hoy_iso  = date.today().isoformat()
    gastado  = 0.0
    if df_semana is not None and not df_semana.empty and "monto_facturas" in df_semana.columns:
        gastado = float(df_semana.loc[df_semana["fecha"] <= hoy_iso, "monto_facturas"].sum())

    disponible = PRESUPUESTO_SEMANAL - gastado
    pct        = min(gastado / PRESUPUESTO_SEMANAL * 100, 100) if PRESUPUESTO_SEMANAL else 0

    if pct < 70:
        estado = "verde"; etiqueta = "Bajo control"
        bar_cls = "presup-verde"
        msg_alerta = (
            "El gasto de la semana está dentro del límite. "
            "Hay margen suficiente para recibir y pagar facturas pendientes."
        )
    elif pct < 90:
        estado = "ambar"; etiqueta = "Precaución"
        bar_cls = "presup-ambar"
        msg_alerta = (
            f"Se ha utilizado el {pct:.0f}% del presupuesto semanal. "
            "Evitar comprometer nuevas OC de alto valor esta semana sin autorización de dirección."
        )
    else:
        estado = "rojo"; etiqueta = "ALERTA — Presupuesto al límite"
        bar_cls = "presup-rojo"
        msg_alerta = (
            f"Se ha comprometido el {pct:.0f}% del presupuesto semanal ({_mxn(gastado)} de {_mxn(PRESUPUESTO_SEMANAL)}). "
            "Cualquier factura adicional esta semana REQUIERE autorización explícita de la Dirección General."
        )

    color_disp = "#15803D" if pct < 70 else ("#B45309" if pct < 90 else "#B91C1C")

    kpis = f"""
    <div class="kpis">
      <div class="kpi ambar">
        <div class="kpi-label">Presupuesto semanal</div>
        <div class="kpi-valor" style="font-size:20px">{_mxn(PRESUPUESTO_SEMANAL)}</div>
        <div class="kpi-sub">límite autorizado por semana</div>
      </div>
      <div class="kpi {'rojo' if pct >= 70 else 'verde'}">
        <div class="kpi-label">Facturado esta semana</div>
        <div class="kpi-valor" style="font-size:20px">{_mxn(gastado)}</div>
        <div class="kpi-sub">{pct:.1f}% del presupuesto</div>
      </div>
      <div class="kpi {'rojo' if disponible < 0 else 'verde'}">
        <div class="kpi-label">Disponible</div>
        <div class="kpi-valor" style="font-size:20px;color:{color_disp}">{_mxn(max(disponible, 0))}</div>
        <div class="kpi-sub">{"EXCEDIDO" if disponible < 0 else "restante esta semana"}</div>
      </div>
    </div>"""

    barra = f"""
    <div class="presup-barra-wrap">
      <div class="presup-barra-fill {bar_cls}" style="width:{pct:.1f}%"></div>
    </div>
    <div class="presup-meta">
      <span>$0</span>
      <span style="font-weight:700;color:{color_disp}">{etiqueta} — {pct:.1f}% utilizado</span>
      <span>{_mxn(PRESUPUESTO_SEMANAL)}</span>
    </div>"""

    nota_why = """
    <div style="font-size:11px;color:#64748B;margin-top:10px;line-height:1.6;padding:10px 12px;background:#F8FAFC;border-radius:6px">
      <strong style="color:#334155">¿Por qué existe este presupuesto?</strong>
      El límite semanal de $500,000 protege el flujo de efectivo de la empresa:
      superarlo compromete el capital operativo de semanas futuras,
      puede retrasar pagos a proveedores estratégicos y genera
      presión en la tesorería al coincidir con fechas de nómina y pagos fiscales.
    </div>"""

    alerta = f'<div class="presup-alerta {estado}">{msg_alerta}</div>'

    return f"""
    <div class="seccion">
      <div class="seccion-titulo">
        <div class="seccion-dot" style="background:#C8A951"></div>
        <h2>Presupuesto semanal de facturación</h2>
      </div>
      {kpis}
      {barra}
      {alerta}
      {nota_why}
    </div>"""


def _seccion_actividad(
    df_sisor: Optional[pd.DataFrame],
    df_oc: Optional[pd.DataFrame],
    fecha_actividad: Optional[str],
) -> str:
    tiene = (df_sisor is not None and not df_sisor.empty) or (df_oc is not None and not df_oc.empty)
    if not tiene:
        return ""

    lbl = _fmt_fecha(fecha_actividad) if fecha_actividad else "ayer"

    n_fact  = len(df_sisor) if df_sisor is not None else 0
    m_fact  = float(df_sisor["importe_num"].sum()) if df_sisor is not None and not df_sisor.empty else 0.0
    n_oc    = len(df_oc)    if df_oc    is not None else 0
    m_oc    = float(df_oc["total"].sum()) if df_oc is not None and not df_oc.empty else 0.0

    kpis = f"""
    <div class="kpis">
      <div class="kpi verde">
        <div class="kpi-label">Facturas capturadas</div>
        <div class="kpi-valor">{n_fact}</div>
        <div class="kpi-sub">ingresadas en SISOR</div>
      </div>
      <div class="kpi verde">
        <div class="kpi-label">Monto SISOR</div>
        <div class="kpi-valor" style="font-size:18px">{_mxn(m_fact)}</div>
        <div class="kpi-sub">MXN capturado</div>
      </div>
      <div class="kpi morado">
        <div class="kpi-label">OC generadas</div>
        <div class="kpi-valor">{n_oc}</div>
        <div class="kpi-sub">órdenes de compra</div>
      </div>
      <div class="kpi morado">
        <div class="kpi-label">Monto OC</div>
        <div class="kpi-valor" style="font-size:18px">{_mxn(m_oc)}</div>
        <div class="kpi-sub">MXN comprometido</div>
      </div>
    </div>"""

    # Solo KPIs — el detalle completo está en la app
    return f"""
    <div class="seccion">
      <div class="seccion-titulo">
        <h2>Actividad del {lbl}</h2>
        <div class="seccion-titulo-linea"></div>
      </div>
      {kpis}
      <p style="font-size:11px;color:#94A3B8;margin-top:4px">Detalle completo disponible en la app de control.</p>
    </div>"""


def _seccion_semana(df_semana: Optional[pd.DataFrame]) -> str:
    if df_semana is None or df_semana.empty:
        return ""

    hoy_str = date.today().isoformat()
    filas = ""
    for _, r in df_semana.iterrows():
        d_str  = str(r.get("fecha", ""))
        nombre = str(r.get("dia_nombre", ""))
        n_f    = int(r.get("n_facturas", 0))
        m_f    = float(r.get("monto_facturas", 0))
        n_o    = int(r.get("n_oc", 0))
        m_o    = float(r.get("monto_oc", 0))
        futuro      = d_str > hoy_str
        sin_activ   = (not futuro) and n_f == 0 and n_o == 0
        op          = ' style="opacity:.45"' if (futuro or sin_activ) else ""
        f_str       = datetime.strptime(d_str, "%Y-%m-%d").strftime("%d/%m") if d_str else ""
        mostrar_cero = not futuro and not sin_activ
        filas += f"""
        <tr{op}>
          <td><strong>{nombre}</strong></td><td>{f_str}</td>
          <td style="text-align:center">{"—" if not mostrar_cero else n_f}</td>
          <td style="text-align:right">{"—" if not mostrar_cero else _mxn(m_f)}</td>
          <td style="text-align:center">{"—" if not mostrar_cero else n_o}</td>
          <td style="text-align:right">{"—" if not mostrar_cero else _mxn(m_o)}</td>
        </tr>"""

    df_p = df_semana[df_semana["fecha"] <= hoy_str]
    t_f = int(df_p["n_facturas"].sum())
    t_mf = float(df_p["monto_facturas"].sum())
    t_o = int(df_p["n_oc"].sum())
    t_mo = float(df_p["monto_oc"].sum())
    filas += f"""
    <tr class="semana-total">
      <td colspan="2">Total semana</td>
      <td style="text-align:center">{t_f}</td>
      <td style="text-align:right">{_mxn(t_mf)}</td>
      <td style="text-align:center">{t_o}</td>
      <td style="text-align:right">{_mxn(t_mo)}</td>
    </tr>"""

    lunes  = df_semana.iloc[0]["fecha"]
    sabado = df_semana.iloc[-1]["fecha"]
    try:
        rango = f"{datetime.strptime(lunes, '%Y-%m-%d').strftime('%d/%m')} – {datetime.strptime(sabado, '%Y-%m-%d').strftime('%d/%m')}"
    except (ValueError, TypeError):
        rango = ""

    return f"""
    <div class="seccion">
      <div class="seccion-titulo">
        <h2>Semana en curso &nbsp;<span style="font-size:10px;color:#8BA0B4;font-weight:400;letter-spacing:.02em">({rango})</span></h2>
        <div class="seccion-titulo-linea"></div>
      </div>
      <table>
        <thead><tr>
          <th>Día</th><th>Fecha</th>
          <th style="text-align:center">Facturas cap.</th>
          <th style="text-align:right">Monto SISOR</th>
          <th style="text-align:center">OC gen.</th>
          <th style="text-align:right">Monto OC</th>
        </tr></thead>
        <tbody>{filas}</tbody>
      </table>
    </div>"""


def _seccion_pendientes(
    df_pendientes: pd.DataFrame,
    stats: dict,
    historial_prev: Optional[dict],
) -> str:
    n_pend    = stats.get("pendientes", 0)
    n_ok      = stats.get("en_sisor", 0)
    monto     = stats.get("monto_pendiente", 0.0)
    total_ofb = stats.get("total_cfdi", 0)

    delta_str = ""
    if historial_prev:
        diff = n_pend - historial_prev.get("pendientes", n_pend)
        if diff < 0:
            delta_str = f'<span style="color:#15803D">(-{abs(diff)}) menos que ayer</span>'
        elif diff > 0:
            delta_str = f'<span style="color:#B91C1C">(+{diff}) más que ayer</span>'
        else:
            delta_str = '<span style="color:#64748B">Sin cambio</span>'

    kpis = f"""
    <div class="kpis">
      <div class="kpi rojo">
        <div class="kpi-label">Pendientes</div>
        <div class="kpi-valor">{n_pend}</div>
        <div class="kpi-sub">{delta_str}</div>
      </div>
      <div class="kpi verde">
        <div class="kpi-label">Ya en SISOR</div>
        <div class="kpi-valor">{n_ok}</div>
        <div class="kpi-sub">de {total_ofb} facturas</div>
      </div>
      <div class="kpi ambar">
        <div class="kpi-label">Monto pendiente</div>
        <div class="kpi-valor" style="font-size:18px">{_mxn(monto)}</div>
        <div class="kpi-sub">MXN timbradas no recibidas</div>
      </div>
    </div>"""

    if df_pendientes.empty:
        tabla = '<p style="color:#15803D;font-weight:600">Todo al corriente. Ninguna factura pendiente.</p>'
    else:
        top = df_pendientes.copy()
        if "dias_pendiente" not in top.columns:
            if "fecha" in top.columns:
                top["dias_pendiente"] = top["fecha"].apply(
                    lambda f: (date.today() - f.date()).days if pd.notna(f) else 0
                )
            else:
                top["dias_pendiente"] = 0
        top = top.sort_values("dias_pendiente", ascending=False).head(5)

        filas = ""
        for _, r in top.iterrows():
            prov  = str(r.get("proveedor", "—"))[:40]
            _folio_raw = r.get("folio", None)
            folio = '<span style="color:#94A3B8;font-style:italic">Sin folio</span>' if (not _folio_raw or str(_folio_raw).strip().lower() in ("none", "", "nan")) else str(_folio_raw)
            tot   = f'${float(r.get("total", 0)):,.2f}'
            dias  = int(r.get("dias_pendiente", 0))
            filas += f'<tr{_row_class(dias)}><td>{prov}</td><td>{folio}</td><td style="text-align:right">{tot}</td><td style="text-align:center">{_dias_badge(dias)}</td></tr>'

        tabla = f"""
        <p style="font-size:12px;color:#64748B;margin-bottom:8px">Top 5 más antiguos (de {n_pend} pendientes):</p>
        <table>
          <thead><tr>
            <th>Proveedor</th><th>Folio</th>
            <th style="text-align:right">Total</th>
            <th style="text-align:center">Días pend.</th>
          </tr></thead>
          <tbody>{filas}</tbody>
        </table>"""

    return f"""
    <div class="seccion">
      <div class="seccion-titulo">
        <h2>Facturas timbradas no recibidas</h2>
        <div class="seccion-titulo-linea"></div>
      </div>
      {kpis}
      {tabla}
    </div>"""


def _seccion_oc(df_oc_resumen: Optional[pd.DataFrame]) -> str:
    if df_oc_resumen is None or df_oc_resumen.empty:
        return ""

    monto_oc   = df_oc_resumen["monto_pendiente"].sum()
    n_ocs      = int(df_oc_resumen["ocs_activas"].sum())
    n_provs_oc = len(df_oc_resumen)

    kpis = f"""
    <div class="kpis">
      <div class="kpi rojo">
        <div class="kpi-label">OCs con pendiente</div>
        <div class="kpi-valor">{n_ocs}</div>
        <div class="kpi-sub">{n_provs_oc} proveedores</div>
      </div>
      <div class="kpi ambar">
        <div class="kpi-label">Monto OC pendiente</div>
        <div class="kpi-valor" style="font-size:18px">{_mxn(monto_oc)}</div>
        <div class="kpi-sub">MXN por recibir</div>
      </div>
    </div>"""

    n_total = len(df_oc_resumen)
    filas = ""
    for _, r in df_oc_resumen.head(3).iterrows():
        prov = str(r.get("proveedor", "—"))[:40]
        ocs  = int(r.get("ocs_activas", 0))
        ren  = int(r.get("renglones_pendientes", 0))
        mp   = _mxn(float(r.get("monto_pendiente", 0)))
        filas += f"<tr><td>{prov}</td><td style='text-align:center'>{ocs}</td><td style='text-align:center'>{ren}</td><td style='text-align:right'>{mp}</td></tr>"

    resto = f'<tr><td colspan="4" style="color:#64748B;font-style:italic;text-align:center;font-size:11px">... y {n_total - 3} proveedores más — ver detalle completo en la app</td></tr>' if n_total > 3 else ""

    tabla = f"""
    <p style="font-size:12px;color:#64748B;margin-bottom:8px">Top 3 por monto pendiente (de {n_total} proveedores con OC activa):</p>
    <table>
      <thead><tr>
        <th>Proveedor</th>
        <th style="text-align:center">OCs</th>
        <th style="text-align:center">Renglones</th>
        <th style="text-align:right">Monto pend.</th>
      </tr></thead>
      <tbody>{filas}{resto}</tbody>
    </table>"""

    return f"""
    <div class="seccion">
      <div class="seccion-titulo">
        <h2>Órdenes de Compra — Pendientes de entrega</h2>
        <div class="seccion-titulo-linea"></div>
      </div>
      {kpis}
      {tabla}
    </div>"""


# ─── Secciones Compras ────────────────────────────────────────────────────────

def _seccion_semaforo_compras(
    semaforo_stats: dict,
    df_urgentes: Optional[pd.DataFrame],
) -> str:
    n_venc = semaforo_stats.get("vencidas", 0)
    n_prox = semaforo_stats.get("proximas", 0)
    n_ok   = semaforo_stats.get("a_tiempo", 0)

    kpis = f"""
    <div class="kpis">
      <div class="kpi rojo">
        <div class="kpi-label">Vencidas</div>
        <div class="kpi-valor">{n_venc}</div>
        <div class="kpi-sub">fecha de entrega pasada</div>
      </div>
      <div class="kpi ambar">
        <div class="kpi-label">Próximas a vencer</div>
        <div class="kpi-valor">{n_prox}</div>
        <div class="kpi-sub">vencen en ≤7 días</div>
      </div>
      <div class="kpi verde">
        <div class="kpi-label">A tiempo</div>
        <div class="kpi-valor">{n_ok}</div>
        <div class="kpi-sub">más de 7 días</div>
      </div>
    </div>"""

    tabla = ""
    if df_urgentes is not None and not df_urgentes.empty:
        # Solo mostrar las vencidas; si no hay, mostrar próximas ≤3 días — máximo 5 filas
        vencidas = df_urgentes[df_urgentes.get("dias_restantes", pd.Series(dtype=float)).lt(0)] if "dias_restantes" in df_urgentes.columns else df_urgentes.iloc[0:0]
        if vencidas.empty:
            top = df_urgentes.sort_values("dias_restantes").head(3)
            nota = "OC próximas a vencer (atención requerida):"
        else:
            top = vencidas.sort_values("dias_restantes").head(3)
            n_total_urg = len(vencidas)
            nota = f"OC vencidas — requieren acción inmediata ({n_total_urg} en total, se muestran las {min(3, n_total_urg)} más críticas):"
        filas = ""
        for _, r in top.iterrows():
            oc_n  = str(r.get("oc", "—"))
            prov  = str(r.get("proveedor", "—"))[:38]
            mat   = str(r.get("material",  "—"))[:35]
            fe    = str(r.get("fecha_entrega", ""))[:10]
            dias  = r.get("dias_restantes", None)
            try:
                fe_fmt = datetime.strptime(fe, "%Y-%m-%d").strftime("%d/%m/%Y")
            except (ValueError, TypeError):
                fe_fmt = fe or "—"
            try:
                dv = int(dias)
                badge = (
                    f'<span class="badge-rojo">{abs(dv)}d vencida</span>'
                    if dv < 0 else
                    f'<span class="badge-ambar">{dv}d restantes</span>'
                )
            except (TypeError, ValueError):
                badge = "—"
            filas += (
                f"<tr><td>{oc_n}</td><td>{prov}</td><td>{mat}</td>"
                f"<td>{fe_fmt}</td><td style='text-align:center'>{badge}</td></tr>"
            )
        tabla = f"""
        <p style="font-size:12px;color:#64748B;margin-bottom:8px">{nota}</p>
        <table>
          <thead><tr>
            <th>OC#</th><th>Proveedor</th><th>Material</th>
            <th>F. Entrega</th><th style="text-align:center">Estado</th>
          </tr></thead>
          <tbody>{filas}</tbody>
        </table>"""

    return f"""
    <div class="seccion">
      <div class="seccion-titulo">
        <div class="seccion-dot" style="background:#B91C1C"></div>
        <h2>Compras — Semáforo de entregas</h2>
      </div>
      {kpis}
      {tabla}
    </div>"""


def _seccion_ocs_sin_cfdi(df_ocs_sin_cfdi: Optional[pd.DataFrame]) -> str:
    if df_ocs_sin_cfdi is None or df_ocs_sin_cfdi.empty:
        return ""

    n_rengl = len(df_ocs_sin_cfdi)
    monto   = float(df_ocs_sin_cfdi["monto_pendiente"].sum()) if "monto_pendiente" in df_ocs_sin_cfdi.columns else 0.0

    prov_grp = (
        df_ocs_sin_cfdi.groupby("proveedor", as_index=False)
        .agg(
            renglones=("oc", "count"),
            monto=("monto_pendiente", "sum"),
        )
        .sort_values("monto", ascending=False)
    )
    n_provs = len(prov_grp)

    kpis = f"""
    <div class="kpis">
      <div class="kpi rojo">
        <div class="kpi-label">Proveedores sin CFDI</div>
        <div class="kpi-valor">{n_provs}</div>
        <div class="kpi-sub">{n_rengl} renglones OC</div>
      </div>
      <div class="kpi ambar">
        <div class="kpi-label">Monto en riesgo</div>
        <div class="kpi-valor" style="font-size:18px">{_mxn(monto)}</div>
        <div class="kpi-sub">sin factura en SAT</div>
      </div>
    </div>"""

    n_total_sin = len(prov_grp)
    filas = ""
    for _, r in prov_grp.head(3).iterrows():
        prov  = str(r.get("proveedor", "—"))[:42]
        rengl = int(r.get("renglones", 0))
        mp    = _mxn(float(r.get("monto", 0)))
        filas += (
            f"<tr><td>{prov}</td>"
            f"<td style='text-align:center'>{rengl}</td>"
            f"<td style='text-align:right'>{mp}</td></tr>"
        )
    if n_total_sin > 3:
        filas += f'<tr><td colspan="3" style="color:#64748B;font-style:italic;text-align:center;font-size:11px">... y {n_total_sin - 3} proveedores más</td></tr>'

    tabla = f"""
    <p style="font-size:12px;color:#64748B;margin-bottom:8px">
      Top 3 por monto — llamar para que presenten factura en SAT ({n_total_sin} proveedores en total):
    </p>
    <table>
      <thead><tr>
        <th>Proveedor</th>
        <th style="text-align:center">Renglones</th>
        <th style="text-align:right">Monto pend.</th>
      </tr></thead>
      <tbody>{filas}</tbody>
    </table>"""

    return f"""
    <div class="seccion">
      <div class="seccion-titulo">
        <div class="seccion-dot" style="background:#92400E"></div>
        <h2>Compras — Proveedores sin factura en SAT</h2>
      </div>
      {kpis}
      {tabla}
    </div>"""


def _seccion_saldo_proveedor(df_saldo: Optional[pd.DataFrame]) -> str:
    if df_saldo is None or df_saldo.empty:
        return ""

    _color_est = {
        "Sin OC":    ("#FEE2E2", "#991B1B"),
        "Excedente": ("#FEF9C3", "#854D0E"),
        "Cubierto":  ("#F0FDF4", "#166534"),
        "Solo OC":   ("#EFF6FF", "#1E40AF"),
    }
    _label_est = {
        "Sin OC":    "🔴 Sin OC",
        "Excedente": "🟡 Excedente",
        "Cubierto":  "🟢 Cubierto",
        "Solo OC":   "🔵 Solo OC",
    }

    n_sin    = int((df_saldo["estado"] == "Sin OC").sum())
    mto_sin  = float(df_saldo.loc[df_saldo["estado"] == "Sin OC", "monto_cfdi"].sum())
    n_exc    = int((df_saldo["estado"] == "Excedente").sum())
    mto_exc  = float(df_saldo.loc[df_saldo["estado"] == "Excedente", "diferencia"].sum())
    n_ok     = int((df_saldo["estado"] == "Cubierto").sum())
    n_solo   = int((df_saldo["estado"] == "Solo OC").sum())

    kpis = f"""
    <div class="kpis">
      <div class="kpi rojo">
        <div class="kpi-label">Sin OC</div>
        <div class="kpi-valor">{n_sin}</div>
        <div class="kpi-sub">{_mxn(mto_sin)} sin respaldo</div>
      </div>
      <div class="kpi ambar">
        <div class="kpi-label">Excedente facturado</div>
        <div class="kpi-valor">{n_exc}</div>
        <div class="kpi-sub">{_mxn(mto_exc)} sobre OC</div>
      </div>
      <div class="kpi verde">
        <div class="kpi-label">Cubiertos</div>
        <div class="kpi-valor">{n_ok}</div>
        <div class="kpi-sub">OC ≥ CFDI</div>
      </div>
      <div class="kpi morado">
        <div class="kpi-label">Solo OC</div>
        <div class="kpi-valor">{n_solo}</div>
        <div class="kpi-sub">aún no facturan</div>
      </div>
    </div>"""

    # Solo mostrar los que requieren atención: Sin OC y Excedente
    df_atencion = df_saldo[df_saldo["estado"].isin(["Sin OC", "Excedente"])].copy()
    df_atencion["_orden"] = df_atencion["estado"].map({"Sin OC": 0, "Excedente": 1}).fillna(99)
    df_atencion = df_atencion.sort_values(["_orden", "diferencia"], ascending=[True, False])
    n_cubiertos = int((df_saldo["estado"] == "Cubierto").sum())
    n_solo_oc   = int((df_saldo["estado"] == "Solo OC").sum())

    filas = ""
    for _, r in df_atencion.head(5).iterrows():
        est   = str(r.get("estado", ""))
        prov  = str(r.get("proveedor", "—"))[:40]
        m_oc  = _mxn(float(r.get("monto_oc",   0) or 0))
        m_cfd = _mxn(float(r.get("monto_cfdi", 0) or 0))
        dif   = float(r.get("diferencia", 0) or 0)
        dif_s = _mxn(dif)
        bg, fg = _color_est.get(est, ("#fff", "#000"))
        lbl = _label_est.get(est, est)
        badge = f'<span style="background:{bg};color:{fg};padding:2px 7px;border-radius:4px;font-size:11px;font-weight:700">{lbl}</span>'
        dif_color = "#B91C1C" if dif > 0 else ("#15803D" if dif < 0 else "#64748B")
        filas += (
            f"<tr><td>{badge}</td><td>{prov}</td>"
            f"<td style='text-align:right'>{m_oc}</td>"
            f"<td style='text-align:right'>{m_cfd}</td>"
            f"<td style='text-align:right;color:{dif_color};font-weight:700'>{dif_s}</td></tr>"
        )

    omitidos = []
    if n_cubiertos: omitidos.append(f"{n_cubiertos} Cubiertos")
    if n_solo_oc:   omitidos.append(f"{n_solo_oc} Solo OC")
    nota_omit = f' Se omiten {" y ".join(omitidos)} (sin riesgo).' if omitidos else ""
    n_atencion_total = len(df_atencion)
    if n_atencion_total > 5:
        nota_omit += f' Y {n_atencion_total - 5} alertas más.'

    if not filas:
        filas = '<tr><td colspan="5" style="text-align:center;color:#15803D;font-style:italic">Sin alertas — todos los proveedores están en orden</td></tr>'

    tabla = f"""
    <p style="font-size:11px;color:#64748B;margin-bottom:8px">
      Solo se muestran proveedores con riesgo (Sin OC o Excedente).
      Diferencia = CFDI − OC. Positivo (rojo) = facturaron más de lo comprometido en OC.{nota_omit}
    </p>
    <table>
      <thead><tr>
        <th>Estado</th><th>Proveedor</th>
        <th style="text-align:right">Total OC</th>
        <th style="text-align:right">Total CFDI</th>
        <th style="text-align:right">Diferencia</th>
      </tr></thead>
      <tbody>{filas}</tbody>
    </table>"""

    return f"""
    <div class="seccion">
      <div class="seccion-titulo">
        <div class="seccion-dot" style="background:#991B1B"></div>
        <h2>Compras — Saldo OC vs Factura por Proveedor</h2>
      </div>
      {kpis}
      {tabla}
    </div>"""


# ─── Sección acciones prioritarias ───────────────────────────────────────────

def _seccion_acciones(
    df_pendientes: pd.DataFrame,
    semaforo_stats: Optional[dict],
    df_oc_urgentes: Optional[pd.DataFrame],
    df_ocs_sin_cfdi: Optional[pd.DataFrame],
    df_saldo_proveedor: Optional[pd.DataFrame],
    stats: dict,
) -> str:
    acciones = []

    # OCs vencidas
    if df_oc_urgentes is not None and not df_oc_urgentes.empty:
        vencidas = df_oc_urgentes[df_oc_urgentes.get("dias_restantes", pd.Series(dtype=float)) < 0] if "dias_restantes" in df_oc_urgentes.columns else df_oc_urgentes
        for _, r in vencidas.iterrows():
            prov = str(r.get("proveedor", "—"))[:45]
            oc_n = str(r.get("oc", "—"))
            mat  = str(r.get("material", "—"))[:40]
            dias = abs(int(r.get("dias_restantes", 0)))
            acciones.append((
                "rojo", "Compras",
                "OC vencida — contactar proveedor",
                f"{prov} · OC {oc_n} · {dias} días vencida · {mat}"
            ))

    # Proveedores sin CFDI
    if df_ocs_sin_cfdi is not None and not df_ocs_sin_cfdi.empty:
        monto_riesgo = float(df_ocs_sin_cfdi["monto_pendiente"].sum()) if "monto_pendiente" in df_ocs_sin_cfdi.columns else 0.0
        provs = ", ".join(df_ocs_sin_cfdi["proveedor"].unique()[:6]) if "proveedor" in df_ocs_sin_cfdi.columns else "—"
        n_p = len(df_ocs_sin_cfdi["proveedor"].unique()) if "proveedor" in df_ocs_sin_cfdi.columns else 0
        if n_p > 0:
            acciones.append((
                "rojo", "CxP / Compras",
                f"Solicitar CFDI a {n_p} proveedores",
                f"{_mxn(monto_riesgo)} en riesgo. Llamar a: {provs}"
            ))

    # Facturas más antiguas pendientes (top 2)
    if not df_pendientes.empty:
        top2 = df_pendientes.copy()
        if "dias_pendiente" not in top2.columns:
            if "fecha" in top2.columns:
                top2["dias_pendiente"] = top2["fecha"].apply(
                    lambda f: (date.today() - f.date()).days if pd.notna(f) else 0
                )
            else:
                top2["dias_pendiente"] = 0
        top2 = top2.sort_values("dias_pendiente", ascending=False).head(2)
        if not top2.empty:
            detalle_parts = []
            for _, r in top2.iterrows():
                prov  = str(r.get("proveedor", "—"))[:35]
                folio = str(r.get("folio", ""))
                if not folio or folio.lower() in ("none", "nan", ""):
                    folio = "sin folio"
                dias  = int(r.get("dias_pendiente", 0))
                tot   = f'${float(r.get("total", 0)):,.0f}'
                detalle_parts.append(f"{prov} {folio} · {dias}d · {tot}")
            acciones.append((
                "rojo", "CxP",
                "Ingresar las 2 facturas más antiguas pendientes",
                " &nbsp;|&nbsp; ".join(detalle_parts)
            ))

    # Proveedores Sin OC de mayor monto
    if df_saldo_proveedor is not None and not df_saldo_proveedor.empty:
        sin_oc = df_saldo_proveedor[df_saldo_proveedor["estado"] == "Sin OC"] if "estado" in df_saldo_proveedor.columns else pd.DataFrame()
        if not sin_oc.empty:
            mto = float(sin_oc["monto_cfdi"].sum()) if "monto_cfdi" in sin_oc.columns else 0.0
            top5 = sin_oc.sort_values("monto_cfdi", ascending=False).head(5) if "monto_cfdi" in sin_oc.columns else sin_oc.head(5)
            top5_txt = ", ".join(
                f"{str(r.get('proveedor',''))[:20]} {_mxn(float(r.get('monto_cfdi',0)))}"
                for _, r in top5.iterrows()
            )
            acciones.append((
                "ambar", "CxP / Dirección",
                f"Revisar {len(sin_oc)} proveedores sin OC",
                f"{_mxn(mto)} sin respaldo de OC. Top: {top5_txt}"
            ))

    # Total pendientes de ingresar
    n_pend = stats.get("pendientes", 0)
    monto_pend = stats.get("monto_pendiente", 0.0)
    if n_pend > 0:
        acciones.append((
            "ambar", "CxP",
            f"Gestionar {n_pend} facturas timbradas no recibidas",
            f"{_mxn(monto_pend)} timbradas en SAT pero no recibidas físicamente"
        ))

    if not acciones:
        return ""

    filas = ""
    for nivel, area, accion, detalle in acciones:
        badge_cls = "badge-rojo" if nivel == "rojo" else "badge-ambar"
        emoji     = "🔴 Alta"   if nivel == "rojo" else "🟡 Media"
        row_cls   = "row-rojo"  if nivel == "rojo" else "row-ambar"
        filas += (
            f'<tr class="{row_cls}">'
            f'<td style="text-align:center"><span class="{badge_cls}">{emoji}</span></td>'
            f"<td><strong>{area}</strong></td>"
            f"<td>{accion}</td>"
            f'<td style="font-size:11.5px;color:#475569">{detalle}</td>'
            f"</tr>"
        )

    return f"""
    <div class="seccion">
      <div class="seccion-titulo">
        <div class="seccion-dot" style="background:#0D1B2A"></div>
        <h2>Acciones prioritarias del día</h2>
      </div>
      <table>
        <thead><tr>
          <th style="text-align:center">Prioridad</th>
          <th>Área responsable</th>
          <th>Acción requerida</th>
          <th>Detalle</th>
        </tr></thead>
        <tbody>{filas}</tbody>
      </table>
    </div>"""


# ─── Función principal ────────────────────────────────────────────────────────

def generar_html(
    df_pendientes: pd.DataFrame,
    stats: dict,
    df_oc_resumen: Optional[pd.DataFrame] = None,
    historial_prev: Optional[dict] = None,
    df_sisor_ayer: Optional[pd.DataFrame] = None,
    df_oc_ayer: Optional[pd.DataFrame] = None,
    df_semana: Optional[pd.DataFrame] = None,
    fecha_actividad: Optional[str] = None,
    semaforo_stats: Optional[dict] = None,
    df_oc_urgentes: Optional[pd.DataFrame] = None,
    df_ocs_sin_cfdi: Optional[pd.DataFrame] = None,
    df_saldo_proveedor: Optional[pd.DataFrame] = None,
) -> str:
    """
    Construye el HTML del reporte diario.
    Orden: Actividad → Semana → Pendientes CxP → OC resumen → Compras (3 bloques).
    Todos los parámetros de Compras son opcionales para compatibilidad con reporte_diario.py.
    """
    hoy = date.today().strftime("%d/%m/%Y")

    seccion_compras = ""
    if semaforo_stats is not None:
        seccion_compras += _seccion_semaforo_compras(semaforo_stats, df_oc_urgentes)
    seccion_compras += _seccion_ocs_sin_cfdi(df_ocs_sin_cfdi)
    seccion_compras += _seccion_saldo_proveedor(df_saldo_proveedor)

    seccion_acciones = _seccion_acciones(
        df_pendientes, semaforo_stats, df_oc_urgentes,
        df_ocs_sin_cfdi, df_saldo_proveedor, stats,
    )

    # Orden ejecutivo: lo urgente primero, el detalle del día al final
    cuerpo = (
        seccion_acciones                                              # 1. Qué hacer hoy
        + _seccion_presupuesto(df_semana)                            # 2. Presupuesto semanal
        + _seccion_semana(df_semana)                                 # 3. Semana en curso
        + _seccion_pendientes(df_pendientes, stats, historial_prev)  # 4. Facturas no recibidas
        + _seccion_oc(df_oc_resumen)                                 # 5. OC pendientes
        + seccion_compras                                            # 6. Compras (semáforo, sin CFDI, saldo)
        + _seccion_actividad(df_sisor_ayer, df_oc_ayer, fecha_actividad)  # 7. Detalle del día (al final)
    )

    hora       = datetime.now().strftime("%H:%M")
    dia_nombre = date.today().strftime("%A").capitalize()
    mes_anio   = date.today().strftime("%B %Y").capitalize()

    # ── Valores para la barra de estado del header ──
    _n_fact_hoy = len(df_sisor_ayer) if df_sisor_ayer is not None and not df_sisor_ayer.empty else 0
    _m_fact_hoy = float(df_sisor_ayer["importe_num"].sum()) if df_sisor_ayer is not None and not df_sisor_ayer.empty else 0.0
    _n_pend     = stats.get("pendientes", 0)
    _n_venc     = semaforo_stats.get("vencidas", 0) if semaforo_stats else 0
    _n_sin_cfdi = len(df_ocs_sin_cfdi["proveedor"].unique()) if df_ocs_sin_cfdi is not None and not df_ocs_sin_cfdi.empty else 0
    _hoy_iso    = date.today().isoformat()
    _t_semana   = float(df_semana.loc[df_semana["fecha"] <= _hoy_iso, "monto_facturas"].sum()) if df_semana is not None and not df_semana.empty else 0.0
    _pct_presup = min(_t_semana / PRESUPUESTO_SEMANAL * 100, 100) if PRESUPUESTO_SEMANAL else 0
    _presup_cls = "red" if _pct_presup >= 90 else ("gold" if _pct_presup >= 70 else "")

    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8">{_ESTILOS}</head>
<body>
<div class="wrapper">
  <div class="header">
    <div class="header-inner">
      <div class="header-brand">
        <div class="header-titles">
          <div class="eyebrow">Oak Footwear &nbsp;·&nbsp; Cuentas por Pagar</div>
          <h1>Reporte Diario de Control</h1>
        </div>
      </div>
      <div class="header-meta">
        <div class="header-fecha-dia">{hoy}</div>
        <div class="header-fecha-sub">{dia_nombre} &nbsp;·&nbsp; {mes_anio}</div>
      </div>
    </div>
    <div class="header-status">
      <div class="hstat">
        <div class="hstat-k">Facturas hoy</div>
        <div class="hstat-v gold">{_n_fact_hoy}</div>
      </div>
      <div class="hstat">
        <div class="hstat-k">Monto SISOR</div>
        <div class="hstat-v gold">{_mxn(_m_fact_hoy)}</div>
      </div>
      <div class="hstat">
        <div class="hstat-k">No recibidas</div>
        <div class="hstat-v {'red' if _n_pend > 0 else ''}">{_n_pend}</div>
      </div>
      <div class="hstat">
        <div class="hstat-k">OCs vencidas</div>
        <div class="hstat-v {'red' if _n_venc > 0 else ''}">{_n_venc}</div>
      </div>
      <div class="hstat">
        <div class="hstat-k">Sin CFDI SAT</div>
        <div class="hstat-v {'red' if _n_sin_cfdi > 0 else ''}">{_n_sin_cfdi} prov.</div>
      </div>
      <div class="hstat">
        <div class="hstat-k">Presupuesto</div>
        <div class="hstat-v {_presup_cls}">{_pct_presup:.0f}% de $500K</div>
      </div>
    </div>
  </div>
  <div class="body">{cuerpo}</div>
  <div class="footer">
    <span class="footer-brand">Oak Footwear</span>
    <span class="footer-dot">·</span>
    Sistema de Control CxP
    <span class="footer-dot">·</span>
    Generado: {hoy} a las {hora} hrs
    <span class="footer-dot">·</span>
    Datos: SISOR + SAT
  </div>
</div>
</body></html>"""


# ─── Guardar HTML en disco ────────────────────────────────────────────────────

def guardar_html(html: str, carpeta: Path) -> Path:
    """Guarda el HTML en carpeta/reporte_YYYY-MM-DD.html y retorna la ruta."""
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"reporte_{date.today().isoformat()}.html"
    ruta.write_text(html, encoding="utf-8")
    return ruta


# ─── Envío por Gmail ──────────────────────────────────────────────────────────

def enviar_reporte(
    html: str,
    destinatario: str,
    asunto: Optional[str] = None,
) -> bool:
    """Envía el HTML por Gmail SMTP con App Password. Retorna True si OK."""
    gmail_user = os.getenv("GMAIL_USER", "")
    gmail_pass = os.getenv("GMAIL_APP_PASSWORD", "")

    if not gmail_user or not gmail_pass:
        raise ValueError(
            "Faltan credenciales Gmail. Configura GMAIL_USER y GMAIL_APP_PASSWORD en el archivo .env"
        )

    if asunto is None:
        asunto = f"[Oak Footwear] Control CxP — {date.today().strftime('%d/%m/%Y')}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"]    = gmail_user
    msg["To"]      = destinatario
    msg.attach(MIMEText(html, "html", "utf-8"))

    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as server:
        server.login(gmail_user, gmail_pass)
        server.sendmail(gmail_user, destinatario, msg.as_string())

    return True
