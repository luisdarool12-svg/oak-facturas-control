"""
Control de Facturas de Proveedores — Oak Footwear
Compara CFDIs del contador (OFB Excel o ZIP de XMLs) vs facturas ingresadas en SISOR.
Con base de datos SQLite acumulativa y control de Órdenes de Compra.

Iniciar:
    streamlit run app.py
"""
import streamlit as st
import pandas as pd
import hashlib
from datetime import date, timedelta
from parsers.ofb_parser   import parse_ofb
from parsers.cfdi_parser  import parse_zip
from parsers.sisor_parser import parse_sisor
from parsers.oc_parser    import parse_oc
from comparator           import comparar
from exporter             import generar_excel
from exclusion_manager    import cargar_exclusiones, guardar_exclusiones
from email_reporter       import generar_html, enviar_reporte, guardar_html
from database import (
    init_db,
    insertar_facturas_ofb,
    eliminar_facturas_ofb,
    insertar_sisor,
    limpiar_sisor,
    insertar_oc,
    get_facturas_ofb,
    get_sisor_entradas,
    get_oc_pendientes,
    get_oc_resumen_proveedor,
    get_oc_proveedores_todos,
    get_oc_total_proveedor,
    get_historial_runs,
    registrar_run,
    get_stats_db,
    get_sisor_del_dia,
    get_oc_del_dia,
    get_actividad_semanal,
    _get_lunes_de_semana,
    _max_fecha_captura,
)

# ─── Página ────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Control de Facturas · OAK",
    page_icon="🟡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Login ────────────────────────────────────────────────────────────────────

import streamlit.components.v1 as _components

_LS_KEY   = "oak_facturas_auth_v1"
_EXPECTED = hashlib.sha256(st.secrets.get("APP_PASSWORD", "").encode()).hexdigest()

# Auto-login: si el navegador guardó el token, llega vía query param desde JS
if not st.session_state.get("autenticado"):
    if st.query_params.get("_oa", "") == _EXPECTED:
        st.session_state["autenticado"] = True
        st.query_params.clear()
        st.rerun()

if not st.session_state.get("autenticado"):
    # JS silencioso: revisa localStorage del PARENT y redirige si hay token guardado
    _components.html(f"""<script>
    (function(){{
        try {{
            var t = window.parent.localStorage.getItem('{_LS_KEY}');
            if (t && t === '{_EXPECTED}') {{
                var u = new URL(window.parent.location.href);
                if (!u.searchParams.get('_oa')) {{
                    u.searchParams.set('_oa', t);
                    window.parent.location.replace(u.toString());
                }}
            }}
        }} catch(e) {{}}
    }})();
    </script>""", height=1)

    st.markdown("## 🔒 Control de Facturas · OAK Footwear")
    _pwd = st.text_input("Contraseña", type="password")
    _recordar = st.checkbox("Recordar sesión (30 días)", value=False)
    if st.button("Entrar", type="primary"):
        if _pwd == st.secrets.get("APP_PASSWORD", ""):
            st.session_state["autenticado"] = True
            if _recordar:
                # Marcar para guardar en localStorage DESPUÉS del rerun
                st.session_state["_guardar_ls"] = True
            st.rerun()
        else:
            st.error("Contraseña incorrecta.")
    st.stop()

# Guardar token en localStorage del PARENT tras login exitoso con "Recordar sesión"
if st.session_state.pop("_guardar_ls", False):
    _components.html(f"""<script>
    try {{ window.parent.localStorage.setItem('{_LS_KEY}', '{_EXPECTED}'); }} catch(e) {{}}
    </script>""", height=1)

# Inyectar botón flotante para abrir/cerrar sidebar (JS real — CSS no funciona en stToolbar)
_components.html("""<script>
(function(){
    var p = window.parent.document;
    if (p.getElementById('oak-sb-btn')) return;
    var btn = p.createElement('button');
    btn.id = 'oak-sb-btn';
    btn.title = 'Abrir / cerrar barra lateral';
    btn.innerHTML = '&#9776;';
    btn.style.cssText = [
        'position:fixed','top:10px','left:10px','z-index:2147483647',
        'width:38px','height:38px','background:#C8A951','color:#0D1B2A',
        'border:none','border-radius:8px','font-size:20px','font-weight:bold',
        'cursor:pointer','display:flex','align-items:center','justify-content:center',
        'box-shadow:0 2px 10px rgba(200,169,81,.5)','transition:background .2s'
    ].join(';');
    btn.onmouseenter = function(){ btn.style.background='#D4B564'; };
    btn.onmouseleave = function(){ btn.style.background='#C8A951'; };
    btn.onclick = function(){
        var selectors = [
            '[data-testid="collapsedControl"]',
            '[data-testid="stSidebarCollapseButton"] button',
            '[data-testid="stSidebarCollapseButton"]',
            'button[aria-label*="sidebar" i]',
            'button[aria-label*="Sidebar"]'
        ];
        for (var i = 0; i < selectors.length; i++) {
            var el = p.querySelector(selectors[i]);
            if (el) { el.click(); return; }
        }
    };
    p.body.appendChild(btn);
})();
</script>""", height=1)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ── Tokens OAK ── */
:root{
  --oak-navy:#0D1B2A; --oak-navy-2:#13283C; --oak-navy-3:#1C3852;
  --oak-gold:#C8A951; --oak-gold-deep:#D4B564; --oak-gold-soft:rgba(200,169,81,.18);
  --oak-ink:#E2E8F0; --oak-muted:#94A3B8; --oak-faint:#64748B;
  --oak-line:rgba(255,255,255,.08); --oak-line-soft:rgba(255,255,255,.05);
  --oak-card:#13283C; --oak-card-2:#1C3852;
  --oak-red:#EF4444; --oak-amber:#F59E0B; --oak-green:#22C55E; --oak-purple:#A78BFA; --oak-blue:#60A5FA;
  --oak-shadow:0 1px 3px rgba(0,0,0,.3),0 4px 16px rgba(0,0,0,.2);
  --oak-shadow-h:0 2px 6px rgba(0,0,0,.4),0 12px 28px rgba(0,0,0,.3);
}
html,body,[class*="css"],.stApp{ font-family:'Inter',sans-serif; color:#CBD5E1; }
.stApp{ background:#0B1520; }
/* Ocultar menú/toolbar pero NO el botón de sidebar */
header[data-testid="stHeader"]{
  background:transparent !important;
  height:3.75rem !important;
  overflow:visible !important;
}
/* Ocultar hijos del toolbar EXCEPTO el collapsedControl */
[data-testid="stToolbar"] > *:not([data-testid="collapsedControl"]){ display:none !important; }
[data-testid="stStatusWidget"],
[data-testid="stDecoration"]{ display:none !important; }
#MainMenu{ display:none !important; }
.block-container{ padding-top:0 !important; max-width:1640px; }

/* ── Sidebar ── */
section[data-testid="stSidebar"]{ background:#0D1B2A; border-right:1px solid var(--oak-line); }
section[data-testid="stSidebar"] > div > div > div{ padding-top:20px !important; }

/* ── Botón abrir/cerrar sidebar ── */
[data-testid="collapsedControl"]{
  display:flex !important;
  visibility:visible !important;
  opacity:1 !important;
  align-items:center !important;
  justify-content:center !important;
  position:fixed !important;
  top:10px !important; left:10px !important;
  z-index:2147483647 !important;
  background:var(--oak-gold) !important;
  border-radius:8px !important;
  width:38px !important; height:38px !important;
  box-shadow:0 2px 10px rgba(200,169,81,.45) !important;
  transition:background .2s,box-shadow .2s !important;
  cursor:pointer !important;
}
[data-testid="collapsedControl"]:hover{
  background:var(--oak-gold-deep) !important;
  box-shadow:0 4px 16px rgba(200,169,81,.65) !important;
}
[data-testid="collapsedControl"] svg{
  color:#0D1B2A !important; fill:#0D1B2A !important;
  width:20px !important; height:20px !important;
}

/* ── Sidebar: texto visible en modo oscuro ── */
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"],
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] span,
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] label {
  color: #E2E8F0 !important;
  font-weight: 600 !important;
}
section[data-testid="stSidebar"] .stRadio label,
section[data-testid="stSidebar"] .stRadio p,
section[data-testid="stSidebar"] .stSlider label,
section[data-testid="stSidebar"] .stSlider p,
section[data-testid="stSidebar"] .stFileUploader label,
section[data-testid="stSidebar"] .stFileUploader p {
  color: #CBD5E1 !important;
}
section[data-testid="stSidebar"] .stMarkdown p { color: #CBD5E1 !important; }
section[data-testid="stSidebar"] .stMarkdown h2 {
  color: #E2E8F0 !important; font-size: .85rem !important; font-weight: 700 !important;
  letter-spacing: .4px !important; text-transform: none !important;
}
section[data-testid="stSidebar"] .stMarkdown h3 {
  color: #E2E8F0 !important; font-size: .78rem !important; font-weight: 700 !important;
}
section[data-testid="stSidebar"] .stCaption,
section[data-testid="stSidebar"] .stCaption p { color: #64748B !important; }
[data-testid="stFileUploaderDropzone"] span,
[data-testid="stFileUploaderDropzone"] small { color: #94A3B8 !important; }

/* ── Sidebar section label ── */
.oak-side-label{
  font-size:.63rem; font-weight:700; letter-spacing:1.6px; text-transform:uppercase;
  color:var(--oak-faint); margin:18px 0 12px; display:flex; align-items:center; gap:8px;
}
.oak-side-label::after{ content:""; flex:1; height:1px; background:var(--oak-line); }

/* ── DB card grid (2-col) ── */
.oak-db-grid{ display:grid; grid-template-columns:1fr 1fr; gap:9px; }
.oak-db{ background:var(--oak-card); border:1px solid var(--oak-line); border-radius:12px; padding:13px; }
.oak-db.full{ grid-column:1 / -1; display:flex; align-items:center; justify-content:space-between; }
.oak-db .dk{ font-size:.62rem; font-weight:700; color:#64748B; text-transform:uppercase; letter-spacing:.3px; }
.oak-db .dv{ font-size:1.25rem; font-weight:700; color:#F1F5F9; margin-top:5px; font-variant-numeric:tabular-nums; line-height:1.1; }
.oak-db.full .dv{ font-size:.92rem; margin-top:2px; }
.oak-db .ds{ font-size:.64rem; color:#64748B; margin-top:4px; }
.oak-status-pill{ display:inline-flex; align-items:center; gap:6px; font-size:.74rem; font-weight:700; color:#22C55E; white-space:nowrap; }
.oak-status-pill .led{ width:8px; height:8px; border-radius:50%; background:#22C55E; box-shadow:0 0 0 3px rgba(34,197,94,.15); flex-shrink:0; }

/* ── st.metric native ── */
[data-testid="stMetric"]{ background:var(--oak-card) !important; border:1px solid var(--oak-line);
  border-left:4px solid var(--oak-gold); border-radius:14px; padding:16px 18px;
  box-shadow:var(--oak-shadow); transition:.18s; }
[data-testid="stMetric"]:hover{ transform:translateY(-2px); box-shadow:var(--oak-shadow-h); }
[data-testid="stMetricLabel"] p{ color:#94A3B8 !important; font-weight:700 !important;
  text-transform:uppercase; letter-spacing:.6px; font-size:.72rem !important; }
[data-testid="stMetricValue"]{ color:#F1F5F9 !important; font-weight:700; font-variant-numeric:tabular-nums; }
[data-testid="stMetricDelta"]{ color:#94A3B8 !important; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"]{ gap:4px; border-bottom:1px solid var(--oak-line); background:transparent !important; }
.stTabs [data-baseweb="tab"]{ color:#64748B; font-weight:600; background:transparent !important;
  border-bottom:2.5px solid transparent; padding:10px 15px; }
.stTabs [aria-selected="true"]{ color:#F1F5F9 !important; border-bottom-color:var(--oak-gold) !important; }
.stTabs [data-baseweb="tab-highlight"]{ background:var(--oak-gold) !important; }
.stTabs [data-baseweb="tab-panel"]{ background:transparent !important; }

/* ── Buttons ── */
.stButton > button{ border-radius:10px; font-weight:600; color:#CBD5E1;
  border:1px solid var(--oak-line); background:var(--oak-card-2); transition:.18s; }
.stButton > button:hover{ border-color:var(--oak-gold); color:var(--oak-gold-deep); background:var(--oak-gold-soft); }
.stButton > button[kind="primary"],
button[data-testid="baseButton-primary"],
.stButton button[data-testid*="primary"]{
  background:var(--oak-gold) !important; color:#0D1B2A !important; border-color:var(--oak-gold) !important; font-weight:700 !important;
}
.stButton > button[kind="primary"]:hover,
button[data-testid="baseButton-primary"]:hover{
  background:var(--oak-gold-deep) !important; box-shadow:var(--oak-shadow-h); transform:translateY(-1px);
}

/* ── File uploader ── */
[data-testid="stFileUploaderDropzone"]{ border:1.5px dashed #334155; border-radius:12px;
  background:var(--oak-card); transition:.18s; }
[data-testid="stFileUploaderDropzone"]:hover{ border-color:var(--oak-gold); background:var(--oak-gold-soft); }

/* ── Dataframe / table ── */
[data-testid="stDataFrame"] thead tr th{ background:var(--oak-navy-3, #1C3852) !important;
  color:var(--oak-gold) !important; font-weight:700; text-transform:uppercase;
  letter-spacing:.6px; font-size:.7rem; }
[data-testid="stDataFrame"] tbody tr td{ background:#0F2035 !important; color:#CBD5E1 !important; }
[data-testid="stDataFrame"] tbody tr:hover td{ background:#1C3852 !important; }

/* ── Radio / checkbox / input ── */
.stRadio [data-testid="stMarkdownContainer"] p { color:#CBD5E1 !important; }
.stTextInput input, .stNumberInput input, .stSelectbox select,
.stDateInput input { background:#13283C !important; color:#E2E8F0 !important; border-color:#334155 !important; }
.stSelectbox [data-baseweb="select"] { background:#13283C !important; }
.stSelectbox [data-baseweb="select"] div { color:#E2E8F0 !important; }

/* ── Divider ── */
hr{ border-color:var(--oak-line) !important; }

/* ── Expander ── */
[data-testid="stExpander"]{ background:var(--oak-card); border:1px solid var(--oak-line); border-radius:12px; }
[data-testid="stExpander"] summary p { color:#CBD5E1 !important; }

/* ── Alerts / info / warning ── */
[data-testid="stAlert"]{ background:var(--oak-card-2) !important; border-radius:10px; }
[data-testid="stAlert"] p { color:#E2E8F0 !important; }

/* ── Caption / small text ── */
.stCaption, .stCaption p { color:#64748B !important; }
p, li, span { color:#CBD5E1; }

/* ── Header OAK ── */
.oak-header{
  display:flex; align-items:center; justify-content:space-between;
  background:linear-gradient(180deg,#0D1B2A,#0B1724);
  border-bottom:2px solid #C8A951;
  border-radius:14px; padding:0 24px; height:72px; margin-bottom:18px;
}
.oak-brand{ display:flex; align-items:center; gap:16px; }
.oak-logo{ height:30px; width:auto; display:block; }
.oak-hdr-div{ width:1px; height:32px; background:rgba(255,255,255,.15); flex-shrink:0; }
.oak-titles .oak-eyebrow{ color:#C8A951; font-size:.62rem; font-weight:600; letter-spacing:2.4px; text-transform:uppercase; margin-bottom:3px; }
.oak-titles h1{ color:#fff; font-size:1rem; font-weight:700; letter-spacing:.1px; margin:0; }
.oak-header-right{ display:flex; align-items:center; gap:18px; }
.oak-stat-k{ color:rgba(255,255,255,.5); font-size:.59rem; letter-spacing:1.4px; text-transform:uppercase; font-weight:600; }
.oak-stat-v{ color:#fff; font-size:.8rem; font-weight:600; margin-top:2px; display:flex; align-items:center; gap:6px; }
.oak-stat-v .led{ width:7px; height:7px; border-radius:50%; background:#C8A951; flex-shrink:0; }
.oak-user-pill{ display:flex; align-items:center; gap:10px; padding:6px 8px 6px 13px;
  background:rgba(255,255,255,.07); border:1px solid rgba(255,255,255,.11); border-radius:999px; }
.oak-user-who{ color:#fff; font-size:.74rem; font-weight:600; line-height:1.2; text-align:right; }
.oak-user-role{ color:rgba(255,255,255,.5); font-size:.62rem; text-align:right; }
.oak-avatar{ width:28px; height:28px; border-radius:50%; background:#C8A951;
  color:#0D1B2A; display:flex; align-items:center; justify-content:center;
  font-weight:800; font-size:.68rem; letter-spacing:.3px; flex-shrink:0; }

/* ── Badges ── */
.oak-badge{display:inline-flex;align-items:center;gap:5px;font-size:.7rem;font-weight:600;padding:3px 9px;border-radius:999px;}
.oak-badge i{width:6px;height:6px;border-radius:50%;background:currentColor;}
.oak-badge.green{color:#4ADE80;background:rgba(74,222,128,.12);}
.oak-badge.amber{color:#FCD34D;background:rgba(252,211,77,.12);}
.oak-badge.red{color:#F87171;background:rgba(248,113,113,.12);}
.oak-badge.blue{color:#60A5FA;background:rgba(96,165,250,.12);}
.oak-badge.purple{color:#A78BFA;background:rgba(167,139,250,.12);}

/* ── Metric card HTML (oak-metric) ── */
.oak-metric{ background:var(--oak-card); border:1px solid var(--oak-line); border-left:4px solid #C8A951;
  border-radius:14px; padding:18px 18px 16px; box-shadow:var(--oak-shadow); transition:.18s; }
.oak-metric:hover{ transform:translateY(-2px); box-shadow:var(--oak-shadow-h); border-color:rgba(255,255,255,.12); }
.oak-metric.red{ border-left-color:#EF4444; }
.oak-metric.amber{ border-left-color:#F59E0B; }
.oak-metric.green{ border-left-color:#22C55E; }
.oak-metric.navy{ border-left-color:#1C3852; }
.oak-metric .ml{ font-size:.72rem; font-weight:700; color:#64748B; text-transform:uppercase;
  letter-spacing:.5px; display:flex; align-items:center; justify-content:space-between; margin-bottom:0; }
.oak-metric .micon{ opacity:.75; flex-shrink:0; color:#C8A951; }
.oak-metric.red .micon{ color:#EF4444; }
.oak-metric.amber .micon{ color:#F59E0B; }
.oak-metric.green .micon{ color:#22C55E; }
.oak-metric.navy .micon{ color:#1C3852; }
.oak-metric .mv{ font-size:1.85rem; font-weight:700; color:#F1F5F9; margin-top:12px;
  font-variant-numeric:tabular-nums; letter-spacing:-.3px; line-height:1; }
.oak-metric .mv small{ font-size:.85rem; font-weight:600; color:#64748B; letter-spacing:0; }
.oak-metric .md{ font-size:.74rem; font-weight:600; color:#64748B; margin-top:10px;
  display:inline-flex; align-items:center; gap:4px; }
</style>
""", unsafe_allow_html=True)

# ─── Init DB ──────────────────────────────────────────────────────────────────

init_db()

stats_db = get_stats_db()

# ─── Logo ─────────────────────────────────────────────────────────────────────

_OAK_LOGO_B64 = "iVBORw0KGgoAAAANSUhEUgAAAVkAAACSCAYAAADvqrkYAAAQAElEQVR4AeydC7xVVbX/x+Rx4IAgJ0C4IiQR4jXSUhCSfOArTUvTJK//e1MrqfxnmfzLf2Gp3ateK8zyUWKlda9eQlNJFHyFRZiImJpaSqShkITI4XnO4bXv/C72PMy99nruvfbrMOfnjDPfY4451lq/NdZYc83dTVxwGnAacBpwGqiYBhzIVky1jrHTgNOA04CIA1l3FjgNOA04DaTRQMq2DmRTKsw1dxpwGnAaSKMBB7JptOXaOg04DTgNpNSAA9mUCnPNs9PAbx5/JDd79uzcvHnzcsuXL89lx9lxchpIo4HKtnUgW1n9Ou4hGliyZEnu+ef/KBvW/UNWrlguDz4wRwBcB7YhCnPFDasBB7INe+gaW/Atm1ulT6/eovS7V4j0xnVvyeOPPiRz5szJrVy50lm24kJX0IAD2a5wFBtwDlvatodK/dabK2X+3DmCO8GBbaiaXEW4BuqqxoFsXR2OPUeYjRs3Fk02Jzs7y0jjTli0aJHgWuiscAmngQbTgAPZBjtgXUVcXAP+uSjtOhAdAFgdSXOvJs9n+/wzSzwXgvPXohVHjaYBB7KNdsS6iLxbOtpDZ6LyYGti0WHNm677/lpWIuis+9vDNNDI03Ug28hHr0FlT+JnVXmgFR2MZUvMSoQf33Jj7oUXXnAvxrRu3F/9a8CBbP0foy4nYXt7uBXrn6zSYGuT5MOCXz/suRDyWRc5DdStBhzI1u2h6bqCvf32297ksEy9RP6fP58vLoiUBl3RAX8tLoSf/fQWZ9VqfTTc3x4ksAPZPehg18tUN23a5L3UMvIArpDKA6jEBGW127Ztmzy56HHBV5vEDSEuOA1UWQMOZKus8HobDt8m61H52mrBggVV8XNu2LCh8yMEwNXoxE6bsrBYWUArOqxcsVwefWiuW+6ldeH+6ksDDmTr63hUXBqsPdadAqo8ai9e9FtZ9vLL3lKp5a+8KNUA2ta1bwqACqWdMH0MKQ20NmHVstyLuTFPcaGKGnBDhWnAgWyYZrpIOWADqPKpKm/l7/nlLwQgYs8AQAnAMlNVGrSqAbSMK/mg9JiGRAfkgXSypD/6Mrd5c++VJ56siqWeUmCuk97jAYcyHahQ81ifQDVPP7f8IPrcoDqc88sFj5VVRrQ2CMAIJJ8ULpMdFA6ppwYoIWPVCi0dWzt5LzviJFy0qmnycGHjvfKlJZDEgbkhWhuYtKGljz9hLfpDDcaU+Zip4Fqa8CBbLU1HjAe4IhvNIwAPEM8zgOivOjBOuXR+Gf6DftPbrk5x05WWKnm8Z888BBDAkKGyEMqD2gmFiu89MdnBLmsosyTPXv2lIMPPliGDRumxo8fr7o39fXcCCovlwQEFVDHvCQflFXP3PmyzPlqpZTg+mSkAQeyGSmyVDaAJztPse4ziPCZYokCnhBW5l9eXiarVrzqWaeAyPZtO7zhsVJJKA00SUh8Qel+kg888gBLh15YqSTg+AXKC05QHZQuEx2UjiHJB6Xzkg9Kpw2JDiqfl4ig8m2IRQf8s6xa0En3V0UNOJCtorLNUM3NzV4SEPESe8C/f/x9Regse/Xq5dWx6uCMMz8hk489MdS63ZN05iklwT9lgamdlnywdcbub/liF1VJAw5kq6RoexiWlhZvvajSF4e44GmgrWOrHHbYYTJs2DCFdbv/u97l+SCVT0f+vLgQqQEbYGlobvCkHVVHAw5kq6PnglEAEgq4ACDSXZ0GDBwaOEWWevGRApUrVuyydilrXb/Fc6nkZKcXU+8oXAOcRxAtiA2RV/pGxU1s0NBhwg1MXKiqBhzIVlXduwfjRQQ5pS8A6eJB6Tnuu+++EhT4xJjF++iDBfx82cRnqiwFs9sb0CC2y126UANB+qHs3aP/WU477TRV2NrlqqEBB7LV0HLAGPgfA4q7XJGxoFiuFTQ5/SKmwFLlyya+WLLbKg3SkLgQqgGldSQBYdiIUTL5+JPl5JNPdgAboJ9qFDmQrYaWA8YYOXKk55fFygio7hJFWzraJciCMpPj23pjsSofSJA3JPmgdBtIXAjUgNL6ER3atH979JgxcvKpH/PAla/sdLH7q5EGHMjWSPF+yw6wNYRIpImrSYxpkz22XR6UNm1NHf6/i754iQqzoNjs5C8vL+t8uWX6GT5dOTZzJY6bJ20gux35MAJc0fvRx5ygjO/f7uvS1deAA9nq67xzxCFD9/PSXDBeosb/lLaEbBIrKF+dPy/5oHQ7LKlx48aJP/BCC+v1hh9cl3vrzZUF1Ur3s0nqJHBsbMpCLGXNVXzBP5bKtw0r57PkwUOHy8RJx8hnPvsFBbiKC3WlAQeyNTwcxmVgi6D0RSV1FLi4EYc4jEQ3MHU6KbzECrKi+H6enaGopz1tTUy6HgnfOWRkq4S8hqeJVf4cMHnRQeXLRAeAddDQYcLeD8d/6FTvhZZbNaAVU6d/DmRreGBwGfTfq6/3yFxDMYqGNhe3Hav8RU4MST4oXW7aST5gWeWTnZH9Wa3SfUQH08/Euqiu/vq1DJJJkyYJu4bxGG6Ey0JePw87T1pZOiLfo2d3Qa+HHDpBPnj08R6wcv4E3czEhbrSgAPZGh+OMQce4n1GasTggoJMvpox40KMSazyF7r4AnWmiLSy2m3RL7uClmvxWS0bxkg+qHwfYgg+NkkdhCH7tHgfRyDKfsPf5b2oVHm5pYzAPOlODKk8TxOLDuhR6XJWB0zUrgBjsQKs7kWWNFRwIFvjwzX8ncNlSN43a4ui9AUmNQpKunVa1236TTW0RYNPm25vyceIxmMrhMXHIzWWFnMJAtlBgwZ5lhjt4QG15fnByyZVw7mLFV77618792HVlrjnBgEUrSYlJ5WeoyF4Gl2gH6xmNjf/9Gcv9F4c4gpwFqs0bOjWsJJ3EcG5eA466KC6mQ0XOaC574iR8u4xo2XiB44U9hJgTwHeWhviJcu5n/qsgngehljsTsyc/BPCAqOe9oYHPOHNOMNGjPJ+MUFp8AF0pA4CG6rMnztH+LUCs9SsXLHsuZHGDTB6zBhPx+gF/Rx9zAnKWavlarp++juQrYNjgaWCr01pgBFf4EJMQnY3u70p52KGbACdMOkoOeb4D8lJp54mWE0GOAFKll5xsQOOyBcEnIZ3qTE84c04jMe4Rg5i5ELGd2uwHzR0mCA7czDj2fM0aepIE0N2mrxNUXWmnWmj9LExJPlAXRQhqyFkZw6jNaBO1I//zM3o+2gNqugHz9ZFXUwDDmTr5IACZgcH/FKA0he36KB0DElI4GLmQoZ4bOdihgCpY47/kByv30JjJQFkAJq5sLGYALsQtjUtRi7AB1mxgpGdOXBjQFfMj7niqoCwwtGD0boy4Cc6mLQ/1lXe12b+cjtvtzFpMw5jGkIOrHEIuQ7RL6gOO3yS95IKmZGdOTAX5sTc4Oeo62vAgWwdHWOAFjDkAt1XP65zAXdave2/SMGQCkzF/SoA94htMYy4o3zpPybcHMxmwu6noG0FPUzH3TF/JgrAMbc0QHAxo0FvUBj3ztO0BPABw3Tbokwot5uS5r+8IHgi64Zg7EYE2J85ODmBSEX8gGmyFrKHF2frqMBbS+0CwAAEABJREFUB7J1diyxcLhAuVi5gE888UTPCiUmb1/QkydPVrQ1FzN962w6VROHuQNo6AJCL9DEIyYq9ATwQeg1jKi325KmP3wg+BpiLMaEqjZJN1BDasCBbB0fNi5gPxlxXew04DTQGBpwINsYx8lJ6TTgNNCgGnAg26AHzontNOA00BgacCBbL8fJyeE04DTQJTXgQLZLHlY3KacBp4F60YAD2Xo5Ek4OpwGngS6pAQeyFTusjrHTgNOA00BKDbgQcCAbdAENOA04DTgNOA04DTgNOA04DTgNOA04DTgNOA04DaaTgNOA04DTQIW14TgNOA04DTgNOA04DaaTgNOA04DTgNOA04DTgNJBSAw5kU+rHNXcacBpwGkijAQeyabTl2joNOA04DaTUgAPZlApzzZ0GnAacBpwGnAYcyKbRlmvuNOA04DTQJTXgQLZLHlY3KacBp4F60YAAAAABJRU5ErkJggg=="

# ─── Header ──────────────────────────────────────────────────────────────────

if stats_db["db_vacia"]:
    _sync = "Sin datos cargados"
else:
    _sync = f"Última carga · {stats_db['ultima_carga'] or '—'}"

st.markdown(f"""
<div class="oak-header">
  <div class="oak-brand">
    <img src="data:image/png;base64,{_OAK_LOGO_B64}" alt="OAK Footwear" class="oak-logo">
    <div class="oak-hdr-div"></div>
    <div class="oak-titles">
      <div class="oak-eyebrow">Cuentas por Pagar</div>
      <h1>Control de Facturas de Proveedores</h1>
    </div>
  </div>
  <div class="oak-header-right">
    <div>
      <div class="oak-stat-k">Conciliación SAT · SISOR</div>
      <div class="oak-stat-v"><span class="led"></span>{_sync}</div>
    </div>
    <div class="oak-user-pill">
      <div>
        <div class="oak-user-who">Auxiliar CxP</div>
        <div class="oak-user-role">Cuentas&nbsp;por&nbsp;Pagar</div>
      </div>
      <div class="oak-avatar">CP</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ─── Sidebar ─────────────────────────────────────────────────────────────────

with st.sidebar:

    # Estado de la DB
    st.markdown("## Base de datos")
    if stats_db["db_vacia"]:
        st.info("DB vacía — sube tu primer archivo para comenzar.", icon="ℹ️")
    else:
        st.markdown(f"""
<div class="oak-db-grid">
  <div class="oak-db">
    <div class="dk">Facturas OFB</div>
    <div class="dv">{stats_db['n_ofb']}</div>
    <div class="ds">{stats_db['n_archivos_ofb']} archivos</div>
  </div>
  <div class="oak-db">
    <div class="dk">Entradas SISOR</div>
    <div class="dv">{stats_db['n_sisor']}</div>
    <div class="ds">capturadas</div>
  </div>
  <div class="oak-db">
    <div class="dk">OC renglones pend.</div>
    <div class="dv">{stats_db['n_oc_pendientes']}</div>
    <div class="ds">de {stats_db['n_oc_total']} totales</div>
  </div>
  <div class="oak-db full">
    <div>
      <div class="dk">Última carga</div>
      <div class="dv" style="font-size:.95rem">{stats_db['ultima_carga'] or '—'}</div>
    </div>
    <div class="oak-status-pill"><span class="led"></span>Activa</div>
  </div>
</div>
""", unsafe_allow_html=True)

    st.divider()

    # ── Actualizar OFB ────────────────────────────────────────────────────────
    st.markdown("### Actualizar datos")

    fuente_sat = st.radio(
        "Tipo de archivo del contador:",
        options=["Excel OFB (recomendado)", "ZIP de XMLs del SAT"],
        index=0,
        key="fuente_sat",
    )
    if fuente_sat == "Excel OFB (recomendado)":
        archivos_sat = st.file_uploader(
            "📊 Excel OFB del contador",
            type=["xlsx", "xls"],
            help="OFB211130F78_Recibidas-MM_YYYY-Facturas.xlsx",
            key="up_ofb",
            accept_multiple_files=True,
        )
    else:
        archivos_sat = st.file_uploader(
            "📦 ZIP de XMLs (SAT)", type=["zip", "xml"], key="up_zip",
            accept_multiple_files=True,
        )

    if archivos_sat:
        if st.button("⬆️ Cargar OFB a la DB", use_container_width=True):
            with st.spinner("Leyendo..."):
                total_nuevas, total_existian = 0, 0
                errores_ofb = []
                for archivo_sat in archivos_sat:
                    try:
                        if fuente_sat == "Excel OFB (recomendado)":
                            df_nuevo, _ = parse_ofb(archivo_sat.read(), archivo_sat.name)
                        else:
                            df_nuevo = parse_zip(archivo_sat.read())
                        nuevas, existian = insertar_facturas_ofb(df_nuevo, archivo_sat.name)
                        total_nuevas += nuevas
                        total_existian += existian
                    except Exception as e:
                        errores_ofb.append(f"{archivo_sat.name}: {e}")
                for err in errores_ofb:
                    st.error(f"Error: {err}")
                if total_nuevas > 0 or total_existian > 0:
                    n_arch = len(archivos_sat) - len(errores_ofb)
                    st.success(f"✅ {n_arch} archivo(s) · {total_nuevas} nuevas · {total_existian} ya existían")
                    st.session_state.resultado = None
                    st.rerun()

    st.divider()

    # ── Actualizar SISOR ──────────────────────────────────────────────────────
    if not stats_db["db_vacia"] and stats_db["n_sisor"] > 0:
        with st.expander(f"🗑️ Limpiar SISOR ({stats_db['n_sisor']} registros)", expanded=False):
            st.warning(
                f"Esto borrará **todos** los {stats_db['n_sisor']} registros de SISOR. "
                "Úsalo cuando quieras subir el archivo mensual completo desde cero."
            )
            if st.button("Borrar todos los registros SISOR", type="primary", use_container_width=True):
                n_borradas = limpiar_sisor()
                st.success(f"✅ {n_borradas} registros eliminados. Ahora sube el archivo mensual.")
                st.session_state.resultado = None
                st.rerun()

    archivos_sisor = st.file_uploader(
        "📋 Excel de SISOR",
        type=["xlsx", "xls", "csv"],
        help="FACTURAS DD-MM-YYYY.XLS",
        key="up_sisor",
        accept_multiple_files=True,
    )
    if archivos_sisor:
        if st.button("⬆️ Cargar SISOR a la DB", use_container_width=True):
            with st.spinner("Leyendo..."):
                total_insertadas, total_omitidas = 0, 0
                todas_fechas_omitidas = []
                errores_sisor = []
                for archivo_sisor in archivos_sisor:
                    try:
                        df_s, _ = parse_sisor(archivo_sisor.read(), archivo_sisor.name)
                        insertadas, omitidas, fechas_omitidas = insertar_sisor(df_s, archivo_sisor.name)
                        total_insertadas += insertadas
                        total_omitidas += omitidas
                        todas_fechas_omitidas.extend(fechas_omitidas)
                    except Exception as e:
                        errores_sisor.append(f"{archivo_sisor.name}: {e}")
                for err in errores_sisor:
                    st.error(f"Error: {err}")
                if total_insertadas > 0 or total_omitidas > 0:
                    n_arch = len(archivos_sisor) - len(errores_sisor)
                    st.success(f"✅ {n_arch} archivo(s) · {total_insertadas} entradas nuevas cargadas")
                    if total_omitidas > 0:
                        fechas_str = ", ".join(
                            pd.to_datetime(f).strftime("%d/%m/%Y")
                            for f in todas_fechas_omitidas[:6]
                        )
                        if len(todas_fechas_omitidas) > 6:
                            fechas_str += f" (+{len(todas_fechas_omitidas) - 6} más)"
                        st.info(
                            f"ℹ️ {total_omitidas} registros omitidos — esos días ya estaban "
                            f"en la DB:\n{fechas_str}"
                        )
                    st.session_state.resultado = None
                    st.rerun()

    st.divider()

    # ── Actualizar OC ─────────────────────────────────────────────────────────
    semanas_oc = st.slider(
        "📅 Semanas a cargar de OC:",
        min_value=4, max_value=52, value=8, step=4,
        help="Solo carga filas recientes del archivo pesado de OC",
    )
    archivo_oc = st.file_uploader(
        "📦 SEGUIMIENTO_OC.xlsx",
        type=["xlsx", "xls"],
        help="Archivo de órdenes de compra (puede ser pesado — se filtra automáticamente)",
        key="up_oc",
    )
    if archivo_oc:
        if st.button("⬆️ Cargar OC a la DB", use_container_width=True):
            with st.spinner(f"Leyendo últimas {semanas_oc} semanas..."):
                try:
                    df_oc_raw, oc_meta = parse_oc(
                        archivo_oc.read(), archivo_oc.name, semanas_atras=semanas_oc
                    )
                    nuevas_oc, act_oc = insertar_oc(df_oc_raw, archivo_oc.name)
                    total_arch  = oc_meta.get("total_filas", "?")
                    cargadas    = oc_meta.get("filas_cargadas", len(df_oc_raw))
                    con_fecha   = oc_meta.get("filas_con_fecha", "?")
                    f_min       = oc_meta.get("fecha_min_arch", "?")
                    f_max       = oc_meta.get("fecha_max_arch", "?")
                    corte_str   = oc_meta.get("fecha_corte", "?")
                    if nuevas_oc == 0 and act_oc == 0:
                        st.warning(
                            f"⚠️ Archivo leído ({total_arch} filas, {con_fecha} con fecha) "
                            f"pero **ninguna pasó el filtro de fecha**.\n\n"
                            f"- Rango en el archivo: {f_min} → {f_max}\n"
                            f"- Filtro aplicado: desde {corte_str} ({semanas_oc} semanas)\n\n"
                            f"Sube el slider de semanas o revisa el formato de fecha del archivo."
                        )
                    else:
                        st.success(
                            f"✅ {nuevas_oc} nuevas · {act_oc} actualizadas  "
                            f"({cargadas} de {total_arch} filas · fechas: {f_min} → {f_max})"
                        )
                        st.rerun()
                except Exception as e:
                    st.error(f"Error cargando OC: {e}")
                    st.exception(e)

    st.divider()

    # ── Reporte para el contador ───────────────────────────────────────────────
    if not stats_db["db_vacia"]:
        st.markdown("### Reporte para el contador")

        def _generar_html_reporte():
            import re as _re_rpt
            from comparator import comparar as _comparar
            _df_ofb   = get_facturas_ofb()
            _df_sisor = get_sisor_entradas()
            _resultado = _comparar(_df_ofb, _df_sisor, {"formato": "db"})
            _excl = cargar_exclusiones()
            _rfcs = {k.upper() for k in _excl.keys()} if _excl else set()
            _pend_raw = _resultado["pendientes"]
            if not _pend_raw.empty and "rfc_emisor" in _pend_raw.columns and _rfcs:
                _pend = _pend_raw[~_pend_raw["rfc_emisor"].str.upper().isin(_rfcs)].reset_index(drop=True)
            else:
                _pend = _pend_raw
            # OFB sin excluidas — para Bloques Compras (Bloque 2 y 3)
            if not _df_ofb.empty and "rfc_emisor" in _df_ofb.columns and _rfcs:
                _df_ofb_filt = _df_ofb[
                    ~_df_ofb["rfc_emisor"].str.upper().isin(_rfcs)
                ].reset_index(drop=True)
            else:
                _df_ofb_filt = _df_ofb
            _stats = dict(_resultado["resumen"])
            _stats["pendientes"]      = len(_pend)
            _stats["monto_pendiente"] = _pend["total"].sum() if not _pend.empty and "total" in _pend.columns else 0.0
            _oc_res    = get_oc_resumen_proveedor()
            _hist      = get_historial_runs(n=2)
            _hist_prev = _hist.iloc[-2].to_dict() if len(_hist) >= 2 else None
            _fecha_act = _max_fecha_captura()
            _sisor_d   = get_sisor_del_dia(_fecha_act)
            _oc_d      = get_oc_del_dia(_fecha_act)
            _lunes     = _get_lunes_de_semana(date.today().isoformat())
            _semana    = get_actividad_semanal(_lunes)

            # ── Datos Compras (Bloques 1, 2, 3) ──────────────────────────────
            _hoy_rpt = date.today()

            def _calc_estado_rpt(f_str):
                try:
                    if not f_str:
                        return "sin_fecha"
                    f = date.fromisoformat(str(f_str).strip()[:10])
                    d = (f - _hoy_rpt).days
                    if d < 0:
                        return "vencida"
                    if d <= 7:
                        return "proxima"
                    return "a_tiempo"
                except Exception:
                    return "sin_fecha"

            def _calc_dias_rpt(f_str):
                try:
                    if not f_str:
                        return None
                    return (date.fromisoformat(str(f_str).strip()[:10]) - _hoy_rpt).days
                except Exception:
                    return None

            _oc_det_rpt = get_oc_pendientes()
            _semaforo_stats = None
            _oc_urgentes    = None
            _ocs_sin_cfdi   = None

            if not _oc_det_rpt.empty:
                _oc_det_rpt = _oc_det_rpt.copy()
                _oc_det_rpt["estado_entrega"] = _oc_det_rpt["fecha_entrega"].apply(_calc_estado_rpt)
                _oc_det_rpt["dias_restantes"] = _oc_det_rpt["fecha_entrega"].apply(_calc_dias_rpt)
                if "monto_pendiente" not in _oc_det_rpt.columns:
                    _oc_det_rpt["monto_pendiente"] = (_oc_det_rpt["pendiente"] * _oc_det_rpt["costo"]).round(2)

                _semaforo_stats = {
                    "vencidas":  int((_oc_det_rpt["estado_entrega"] == "vencida").sum()),
                    "proximas":  int((_oc_det_rpt["estado_entrega"] == "proxima").sum()),
                    "a_tiempo":  int((_oc_det_rpt["estado_entrega"] == "a_tiempo").sum()),
                    "sin_fecha": int((_oc_det_rpt["estado_entrega"] == "sin_fecha").sum()),
                }
                _oc_urgentes = _oc_det_rpt[
                    _oc_det_rpt["estado_entrega"].isin(["vencida", "proxima"])
                ].copy()

                # OCs cuyo proveedor no tiene CFDI en SAT (usa OFB filtrado)
                if not _df_ofb_filt.empty:
                    _ofb_provs = set(
                        _df_ofb_filt["proveedor"]
                        .fillna("").astype(str).str.upper().str.strip()
                        .apply(lambda x: _re_rpt.sub(r"\s*\(\d{4}\)\s*$", "", x).strip())
                        .tolist()
                    )
                else:
                    _ofb_provs = set()

                _oc_det_rpt["prov_norm"] = (
                    _oc_det_rpt["proveedor"]
                    .fillna("").astype(str).str.upper().str.strip()
                )
                _ocs_sin_cfdi = _oc_det_rpt[
                    ~_oc_det_rpt["prov_norm"].isin(_ofb_provs)
                ].copy()

            # Bloque 3: Saldo OC vs CFDI por proveedor
            _saldo_prov = None
            _df_oc_b3_rpt = get_oc_total_proveedor()
            if not _df_ofb_filt.empty or not _df_oc_b3_rpt.empty:
                if not _df_ofb_filt.empty:
                    _cfdi_grp_rpt = (
                        _df_ofb_filt.assign(
                            prov_k=_df_ofb_filt["proveedor"]
                            .fillna("").astype(str).str.upper().str.strip()
                        )
                        .groupby("prov_k")
                        .agg(monto_cfdi=("total", "sum"), n_cfdi=("total", "count"))
                        .reset_index()
                        .rename(columns={"prov_k": "proveedor"})
                    )
                else:
                    _cfdi_grp_rpt = pd.DataFrame(columns=["proveedor", "monto_cfdi", "n_cfdi"])

                _saldo_prov = pd.merge(
                    _cfdi_grp_rpt,
                    _df_oc_b3_rpt[["proveedor", "monto_oc", "ocs_distintas"]],
                    on="proveedor",
                    how="outer",
                ).fillna({"monto_cfdi": 0.0, "n_cfdi": 0, "monto_oc": 0.0, "ocs_distintas": 0})
                _saldo_prov["diferencia"] = (_saldo_prov["monto_cfdi"] - _saldo_prov["monto_oc"]).round(2)

                def _est_rpt(row):
                    if row["monto_oc"] == 0 and row["monto_cfdi"] > 0:
                        return "Sin OC"
                    if row["monto_cfdi"] == 0 and row["monto_oc"] > 0:
                        return "Solo OC"
                    if row["diferencia"] > 0:
                        return "Excedente"
                    return "Cubierto"

                _saldo_prov["estado"] = _saldo_prov.apply(_est_rpt, axis=1)
                _saldo_prov = _saldo_prov.sort_values(
                    ["estado", "diferencia"], ascending=[True, False]
                ).reset_index(drop=True)
                if _saldo_prov.empty:
                    _saldo_prov = None

            return generar_html(
                _pend, _stats,
                df_oc_resumen=_oc_res,
                historial_prev=_hist_prev,
                df_sisor_ayer=_sisor_d,
                df_oc_ayer=_oc_d,
                df_semana=_semana,
                fecha_actividad=_fecha_act,
                semaforo_stats=_semaforo_stats,
                df_oc_urgentes=_oc_urgentes,
                df_ocs_sin_cfdi=_ocs_sin_cfdi,
                df_saldo_proveedor=_saldo_prov,
            )

        col_email, col_html = st.columns(2)

        with col_email:
            if st.button("Enviar reporte por correo", use_container_width=True, type="primary"):
                with st.spinner("Generando y enviando reporte..."):
                    try:
                        import os
                        _html = _generar_html_reporte()
                        _dest = os.getenv("GMAIL_USER", "luisdarool12@gmail.com")
                        enviar_reporte(_html, _dest)
                        st.success(f"Reporte enviado a {_dest}")
                    except ValueError as e:
                        st.error(f"Credenciales faltantes: {e}\nEjecuta configurar_email.command")
                    except Exception as e:
                        st.error(f"Error al enviar: {e}")

        with col_html:
            if st.button("Generar HTML para descargar", use_container_width=True):
                with st.spinner("Generando reporte..."):
                    try:
                        _html = _generar_html_reporte()
                        st.session_state["_html_reporte"] = _html
                    except Exception as e:
                        st.error(f"Error generando reporte: {e}")

        if st.session_state.get("_html_reporte"):
            from datetime import date as _date
            _nombre = f"reporte_oak_{_date.today().isoformat()}.html"
            st.download_button(
                label="Descargar archivo HTML",
                data=st.session_state["_html_reporte"].encode("utf-8"),
                file_name=_nombre,
                mime="text/html",
                use_container_width=True,
            )

    st.divider()
    st.caption(f"Hoy: {date.today().strftime('%d/%m/%Y')}")
    st.caption("App local · Sin internet · Datos privados")

# ─── Estado ──────────────────────────────────────────────────────────────────

if "resultado" not in st.session_state:
    st.session_state.resultado = None

# ─── Pantalla inicial si DB vacía ────────────────────────────────────────────

if stats_db["db_vacia"]:
    c1, c2, c3 = st.columns(3)
    with c1:
        st.info(
            "**Paso 1 — Sube el Excel OFB**\n\n"
            "Archivo del contador con facturas del mes.\n\n"
            "`OFB211130F78_Recibidas-05_2026.xlsx`",
            icon="📊",
        )
    with c2:
        st.info(
            "**Paso 2 — Sube el SISOR**\n\n"
            "Exportación de facturas capturadas en SISOR.\n\n"
            "`FACTURAS 25-05-2026.XLS`",
            icon="📋",
        )
    with c3:
        st.info(
            "**Paso 3 — Sube el OC (opcional)**\n\n"
            "Archivo de seguimiento de Órdenes de Compra.\n\n"
            "`SEGUIMIENTO_OC.xlsx`",
            icon="📦",
        )
    st.stop()

# ─── Botón Comparar ───────────────────────────────────────────────────────────

procesar = st.button(
    "🔍 Comparar desde base de datos",
    type="primary",
    use_container_width=True,
    help="Compara todas las facturas acumuladas en la DB",
)

if procesar or st.session_state.resultado:

    if procesar:
        with st.spinner("Cargando datos de la base de datos..."):
            df_ofb   = get_facturas_ofb()
            df_sisor = get_sisor_entradas()

        if df_ofb.empty:
            st.error("Sin facturas OFB en la base de datos. Sube un archivo OFB primero.")
            st.stop()

        sisor_meta = {"formato": "db"}

        with st.spinner("Comparando..."):
            resultado = comparar(df_ofb, df_sisor, sisor_meta)
            st.session_state.resultado    = resultado
            st.session_state.df_ofb       = df_ofb
            st.session_state.df_sisor     = df_sisor
            st.session_state.sisor_meta   = sisor_meta

    resultado  = st.session_state.resultado
    df_ofb     = st.session_state.get("df_ofb", pd.DataFrame())
    df_sisor   = st.session_state.get("df_sisor", pd.DataFrame())
    sisor_meta = st.session_state.get("sisor_meta", {})
    modo       = resultado["modo"]

    pendientes_raw = resultado["pendientes"]
    en_sisor       = resultado["en_sisor"]
    resumen_raw    = resultado["resumen"]

    # ── Filtro exclusiones ────────────────────────────────────────────────────
    exclusiones = cargar_exclusiones()
    if not pendientes_raw.empty and "rfc_emisor" in pendientes_raw.columns and exclusiones:
        rfcs_excluidos = {k.upper() for k in exclusiones.keys()}
        mask_excluir = pendientes_raw["rfc_emisor"].str.upper().isin(rfcs_excluidos)
        pendientes   = pendientes_raw[~mask_excluir].reset_index(drop=True)
        excluidos_df = pendientes_raw[mask_excluir].reset_index(drop=True)
    else:
        pendientes   = pendientes_raw
        excluidos_df = pd.DataFrame()

    # Métricas filtradas (sin proveedores excluidos)
    n_pend      = len(pendientes)
    n_ok        = resumen_raw["en_sisor"]
    n_excluidos = len(excluidos_df)
    total_ofb   = resumen_raw["total_cfdi"]
    pct_pend    = round(n_pend / total_ofb * 100, 1) if total_ofb > 0 else 0
    monto_pend  = pendientes["total"].sum() if not pendientes.empty and "total" in pendientes.columns else 0.0
    monto_ok    = en_sisor["total"].sum()   if not en_sisor.empty   and "total" in en_sisor.columns   else 0.0

    # Guardar historial con stats ya filtrados (excluidos fuera del monto)
    if procesar:
        registrar_run({
            "total_cfdi":       total_ofb - n_excluidos,
            "total_sisor_rows": resumen_raw["total_sisor_rows"],
            "pendientes":       n_pend,
            "en_sisor":         n_ok,
            "monto_pendiente":  float(monto_pend),
            "monto_en_sisor":   float(monto_ok),
            "modo":             modo,
        })

    # Badge modo
    badge_map = {
        "uuid":        ("green", "UUID exacto"),
        "folio+monto": ("blue",  "Folio + Monto"),
    }
    badge_tone, badge_txt = badge_map.get(modo, ("amber", modo))
    st.markdown(
        f'Modo: <span class="oak-badge {badge_tone}"><i></i>{badge_txt}</span>'
        + (f' &nbsp;·&nbsp; <span class="oak-badge amber"><i></i>{n_excluidos} excluidos</span>'
           if n_excluidos else ""),
        unsafe_allow_html=True,
    )
    if modo == "folio+monto":
        st.caption(
            "SISOR no tiene columna UUID. Comparación por Folio + Monto (±2%). "
            "Si un proveedor usa folios duplicados con distintos montos, revisar manualmente."
        )

    st.divider()

    # ── Métricas ──────────────────────────────────────────────────────────────

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""<div class="oak-metric">
            <div class="ml">Total en OFB (DB)</div>
            <div class="mv">{total_ofb}</div>
            <div class="md">facturas acumuladas</div></div>""",
            unsafe_allow_html=True)
    with c2:
        pct_ok = round(n_ok / total_ofb * 100, 1) if total_ofb > 0 else 0
        st.markdown(f"""<div class="oak-metric green">
            <div class="ml">Ya en SISOR</div>
            <div class="mv">{n_ok}</div>
            <div class="md">{pct_ok:.1f}% ingresadas</div></div>""",
            unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class="oak-metric red">
            <div class="ml">Pendientes</div>
            <div class="mv">{n_pend}</div>
            <div class="md">{pct_pend}% no recibidas</div></div>""",
            unsafe_allow_html=True)
    with c4:
        monto_fmt = f"${monto_pend:,.2f}"
        st.markdown(f"""<div class="oak-metric amber">
            <div class="ml">Monto pendiente</div>
            <div class="mv" style="font-size:1.3rem">{monto_fmt}</div>
            <div class="md">MXN timbradas no recibidas</div></div>""",
            unsafe_allow_html=True)

    st.divider()

    # ── Tabs ──────────────────────────────────────────────────────────────────

    (tab_pend, tab_ok, tab_prov, tab_sisor_v,
     tab_export, tab_excl, tab_hist, tab_oc, tab_act, tab_gestionar) = st.tabs([
        f"🔴 Pendientes ({n_pend})",
        f"✅ Ya en SISOR ({n_ok})",
        "🏢 Por proveedor",
        "📋 Vista SISOR",
        "📥 Exportar",
        "⚙️ Exclusiones",
        "📊 Historial",
        "📦 Órdenes de Compra",
        "📅 Actividad",
        "🗑️ Gestionar OFB",
    ])

    # ── Tab Pendientes ────────────────────────────────────────────────────────

    with tab_pend:
        if pendientes.empty:
            st.success("¡Todo al corriente! Todas las facturas del OFB ya están en SISOR.")
        else:
            st.markdown(f"**{n_pend} facturas** que debes ingresar a SISOR:")

            fc1, fc2, fc3 = st.columns([2, 2, 1])
            with fc1:
                provs = sorted(pendientes["proveedor"].dropna().unique().tolist()) if "proveedor" in pendientes.columns else []
                sel_prov = st.multiselect("Filtrar por proveedor", provs, key="f_prov")
            with fc2:
                if "fecha" in pendientes.columns and pendientes["fecha"].notna().any():
                    min_f = pendientes["fecha"].min().date()
                    max_f = pendientes["fecha"].max().date()
                    rango = st.date_input("Rango fechas", value=(min_f, max_f),
                                          min_value=min_f, max_value=max_f, key="f_fecha")
                else:
                    rango = None
            with fc3:
                monto_min = st.number_input("Monto mín $", min_value=0.0, value=0.0,
                                            step=100.0, key="f_monto")

            df_f = pendientes.copy()
            if sel_prov and "proveedor" in df_f.columns:
                df_f = df_f[df_f["proveedor"].isin(sel_prov)]
            if rango and len(rango) == 2 and "fecha" in df_f.columns:
                df_f = df_f[(df_f["fecha"].dt.date >= rango[0]) &
                            (df_f["fecha"].dt.date <= rango[1])]
            if monto_min > 0 and "total" in df_f.columns:
                df_f = df_f[df_f["total"] >= monto_min]

            # Calcular días pendiente
            if "fecha" in df_f.columns:
                df_f["dias_pendiente"] = df_f["fecha"].apply(
                    lambda f: (date.today() - f.date()).days if pd.notna(f) else 0
                )
            else:
                df_f["dias_pendiente"] = 0
            df_f = df_f.sort_values("dias_pendiente", ascending=False)

            cols_show = [c for c in ["proveedor","rfc_emisor","folio","uuid",
                                     "fecha","total","moneda","dias_pendiente"]
                         if c in df_f.columns]
            labels = {
                "proveedor": "Proveedor", "rfc_emisor": "RFC", "folio": "Folio",
                "uuid": "UUID / Folio Fiscal", "fecha": "Fecha",
                "total": "Total", "moneda": "Moneda", "dias_pendiente": "Días pend.",
            }

            def _color_dias(val: int) -> str:
                if val > 30:
                    return "background-color:#FEE2E2; color:#991B1B; font-weight:600"
                if val > 7:
                    return "background-color:#FEF3C7; color:#92400E; font-weight:600"
                return ""

            df_show = df_f[cols_show].rename(columns=labels)
            styled = df_show.style.map(
                _color_dias, subset=["Días pend."]
            ) if "Días pend." in df_show.columns else df_show

            st.dataframe(
                styled,
                use_container_width=True,
                height=min(600, 60 + len(df_f) * 35),
                column_config={
                    "Total":      st.column_config.NumberColumn(format="$%.2f"),
                    "Días pend.": st.column_config.NumberColumn(format="%d días"),
                    "Fecha":      st.column_config.DateColumn(format="DD/MM/YYYY"),
                },
            )

            # Leyenda de colores
            st.markdown(
                '<small>'
                '<span style="background:#FEE2E2;padding:2px 8px;border-radius:4px;color:#991B1B">■ +30 días</span> &nbsp;'
                '<span style="background:#FEF3C7;padding:2px 8px;border-radius:4px;color:#92400E">■ 7–30 días</span> &nbsp;'
                '<span style="background:#F0FDF4;padding:2px 8px;border-radius:4px;color:#15803D">■ menos de 7 días</span>'
                '</small>',
                unsafe_allow_html=True,
            )

    # ── Tab Ya en SISOR ───────────────────────────────────────────────────────

    with tab_ok:
        if en_sisor.empty:
            st.info("No hay facturas del OFB confirmadas en SISOR.")
        else:
            cols_show = [c for c in ["proveedor","rfc_emisor","folio","uuid","fecha","total","moneda"]
                         if c in en_sisor.columns]
            labels = {
                "proveedor": "Proveedor", "rfc_emisor": "RFC", "folio": "Folio",
                "uuid": "UUID", "fecha": "Fecha", "total": "Total", "moneda": "Moneda",
            }
            st.dataframe(
                en_sisor[cols_show].rename(columns=labels),
                use_container_width=True,
                column_config={
                    "Total": st.column_config.NumberColumn(format="$%.2f"),
                    "Fecha": st.column_config.DateColumn(format="DD/MM/YYYY"),
                },
            )

    # ── Tab Por proveedor ─────────────────────────────────────────────────────

    with tab_prov:
        if "proveedor" not in df_ofb.columns:
            st.info("Sin datos de proveedor.")
        else:
            df_ofb_filtrado = df_ofb.copy()
            if exclusiones and "rfc_emisor" in df_ofb_filtrado.columns:
                rfcs_excluidos = {k.upper() for k in exclusiones.keys()}
                df_ofb_filtrado = df_ofb_filtrado[
                    ~df_ofb_filtrado["rfc_emisor"].str.upper().isin(rfcs_excluidos)
                ]

            grupos = df_ofb_filtrado.groupby("proveedor").agg(
                total_ofb=("uuid", "count"),
                monto_total=("total", "sum"),
            ).reset_index()

            if not pendientes.empty and "proveedor" in pendientes.columns:
                pend_g = pendientes.groupby("proveedor").agg(
                    pendientes=("uuid", "count"),
                    monto_pend=("total", "sum"),
                ).reset_index()
                resumen_prov = grupos.merge(pend_g, on="proveedor", how="left").fillna(0)
            else:
                resumen_prov = grupos.copy()
                resumen_prov["pendientes"] = 0
                resumen_prov["monto_pend"] = 0.0

            resumen_prov["en_sisor"] = resumen_prov["total_ofb"] - resumen_prov["pendientes"]
            resumen_prov["pct_pend"] = (
                resumen_prov["pendientes"] / resumen_prov["total_ofb"] * 100
            ).round(1)
            resumen_prov = resumen_prov.sort_values("pendientes", ascending=False)

            st.dataframe(
                resumen_prov.rename(columns={
                    "proveedor": "Proveedor", "total_ofb": "En OFB",
                    "monto_total": "Monto Total", "pendientes": "Pendientes",
                    "en_sisor": "En SISOR", "monto_pend": "Monto Pendiente",
                    "pct_pend": "% Pendiente",
                }),
                use_container_width=True,
                column_config={
                    "Monto Total":     st.column_config.NumberColumn(format="$%.2f"),
                    "Monto Pendiente": st.column_config.NumberColumn(format="$%.2f"),
                    "% Pendiente":     st.column_config.NumberColumn(format="%.1f%%"),
                },
            )

            if not resumen_prov.empty:
                top10 = resumen_prov.head(10).set_index("proveedor")
                st.bar_chart(
                    top10[["en_sisor", "pendientes"]].rename(
                        columns={"en_sisor": "En SISOR", "pendientes": "Pendientes"}
                    ),
                    color=["#16A34A", "#DC2626"],
                )

    # ── Tab Vista SISOR ───────────────────────────────────────────────────────

    with tab_sisor_v:
        st.markdown(f"**{len(df_sisor)}** entradas de SISOR en la base de datos:")
        cols_s = [c for c in ["proveedor","factura","importe","fecha_factura","archivo_origen"]
                  if c in df_sisor.columns]
        st.dataframe(
            df_sisor[cols_s].head(300) if cols_s else df_sisor.head(300),
            use_container_width=True,
            height=400,
        )

    # ── Tab Exportar ──────────────────────────────────────────────────────────

    with tab_export:
        st.markdown("### Exportar reporte a Excel")
        st.markdown("Genera un Excel con **Facturas Pendientes**, **Ya en SISOR** y **Resumen**.")

        resumen_export = {
            "total_cfdi":       total_ofb,
            "total_sisor_rows": resumen_raw["total_sisor_rows"],
            "pendientes":       n_pend,
            "en_sisor":         n_ok,
            "pct_pendiente":    pct_pend,
            "monto_pendiente":  monto_pend,
            "monto_en_sisor":   monto_ok,
        }

        if st.button("📥 Generar Excel", type="primary"):
            with st.spinner("Generando..."):
                excel_bytes = generar_excel(pendientes, en_sisor, resumen_export)
            nombre = f"Conciliacion_OFB_SISOR_{date.today().strftime('%Y%m%d')}.xlsx"
            st.download_button(
                "⬇️ Descargar Excel",
                data=excel_bytes,
                file_name=nombre,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True,
            )

        st.divider()
        ca, cb = st.columns(2)
        with ca:
            st.metric("Facturas en OFB (DB)", total_ofb)
            st.metric("Excluidas (no van a SISOR)", n_excluidos)
            st.metric("Modo comparación", modo)
        with cb:
            st.metric("Timbradas no recibidas", n_pend)
            st.metric("Ya en SISOR", n_ok)

    # ── Tab Exclusiones ───────────────────────────────────────────────────────

    with tab_excl:
        st.markdown("### ⚙️ Proveedores excluidos del análisis")
        st.markdown(
            "Marca ✅ en la columna **Excluir** los proveedores que **no** son tuyos. "
            "La configuración se guarda permanentemente."
        )

        # Forzar recarga desde disco para evitar estado de sesión desactualizado
        exclusiones_actuales = cargar_exclusiones()
        rfcs_excluidos_act   = {k.upper() for k in exclusiones_actuales.keys()}

        if "rfc_emisor" in df_ofb.columns and "proveedor" in df_ofb.columns:
            prov_ofb = (
                df_ofb.groupby(["rfc_emisor", "proveedor"])
                .size()
                .reset_index(name="facturas")
                .sort_values("proveedor")
            )

            # Construir DataFrame para el editor — siempre desde JSON, nunca desde sesión
            df_editor = pd.DataFrame([
                {
                    "Excluir":   str(row["rfc_emisor"]).upper().strip() in rfcs_excluidos_act,
                    "Proveedor": str(row["proveedor"]).strip(),
                    "RFC":       str(row["rfc_emisor"]).upper().strip(),
                    "Facturas":  int(row["facturas"]),
                }
                for _, row in prov_ofb.iterrows()
            ])

            n_excl_act = df_editor["Excluir"].sum()
            st.caption(
                f"{len(df_editor)} proveedores en la DB · "
                f"**{n_excl_act} excluidos** actualmente"
            )

            edited = st.data_editor(
                df_editor,
                column_config={
                    "Excluir":   st.column_config.CheckboxColumn(
                        "Excluir", help="✅ = no va a SISOR", width="small"
                    ),
                    "Proveedor": st.column_config.TextColumn("Proveedor", width="large"),
                    "RFC":       st.column_config.TextColumn("RFC", width="medium"),
                    "Facturas":  st.column_config.NumberColumn("Facturas", width="small"),
                },
                disabled=["Proveedor", "RFC", "Facturas"],
                hide_index=True,
                use_container_width=True,
                height=min(700, 60 + len(df_editor) * 35),
                key="excl_editor",
            )

            st.divider()
            col_btn, col_res = st.columns([2, 3])
            with col_btn:
                if st.button("💾 Guardar configuración", type="primary", use_container_width=True):
                    # Exclusiones elegidas en la tabla
                    nuevas = {
                        row["RFC"]: row["Proveedor"]
                        for _, row in edited.iterrows()
                        if row["Excluir"]
                    }
                    # Preservar exclusiones del JSON que no están en df_ofb (bancos, etc.)
                    rfcs_en_tabla = {str(r["rfc_emisor"]).upper().strip() for _, r in prov_ofb.iterrows()}
                    for rfc_extra, nombre_extra in exclusiones_actuales.items():
                        if rfc_extra.upper() not in rfcs_en_tabla:
                            nuevas[rfc_extra.upper()] = nombre_extra
                    guardar_exclusiones(nuevas)
                    n_saved = len(nuevas)
                    st.session_state.resultado = None
                    st.success(f"✅ {n_saved} proveedor(es) excluidos. Haz clic en 'Comparar' para actualizar.")
                    st.rerun()
            with col_res:
                n_marcados = int(edited["Excluir"].sum())
                st.caption(f"Marcados para excluir en esta vista: **{n_marcados}**")
        else:
            st.info("Sin datos en la DB.")

    # ── Tab Historial ─────────────────────────────────────────────────────────

    with tab_hist:
        st.markdown("### 📊 Historial de comparaciones")
        hist_df = get_historial_runs(n=60)

        if hist_df.empty:
            st.info("Aún no hay historial. El historial se acumula con cada comparación.")
        else:
            import plotly.graph_objects as go

            # Agrupar por día: último run de cada día como valor representativo
            hist_df["_dia"] = hist_df["fecha_run"].dt.date
            chart_df = (
                hist_df
                .groupby("_dia", as_index=False)
                .last()
                .drop(columns=["_dia"])
                .reset_index(drop=True)
            )
            hist_df = hist_df.drop(columns=["_dia"])
            chart_df["fecha_dia"] = pd.to_datetime(chart_df["fecha_run"].dt.date)

            curr = hist_df.iloc[-1]
            total_ofb_curr = int(curr["total_ofb"]) if curr["total_ofb"] > 0 else 1
            pct_capturado  = curr["en_sisor"] / total_ofb_curr * 100

            # ── 4 KPIs ────────────────────────────────────────────────────────
            k1, k2, k3, k4 = st.columns(4)
            # Delta KPIs: comparar último día con el día anterior
            if len(chart_df) >= 2:
                prev = chart_df.iloc[-2]
                total_ofb_prev = int(prev["total_ofb"]) if prev["total_ofb"] > 0 else 1
                delta_pend  = int(curr["pendientes"])        - int(prev["pendientes"])
                delta_monto = float(curr["monto_pendiente"]) - float(prev["monto_pendiente"])
                delta_cub   = float(curr["monto_en_sisor"])  - float(prev["monto_en_sisor"])
                delta_pct   = pct_capturado - (prev["en_sisor"] / total_ofb_prev * 100)
            else:
                delta_pend = delta_monto = delta_cub = delta_pct = None

            with k1:
                st.metric(
                    "Facturas pendientes",
                    int(curr["pendientes"]),
                    delta=f"{delta_pend:+d}" if delta_pend is not None else None,
                    delta_color="inverse",
                    help="Facturas del SAT aún no capturadas en SISOR",
                )
            with k2:
                st.metric(
                    "% Capturado",
                    f"{pct_capturado:.1f}%",
                    delta=f"{delta_pct:+.1f}pp" if delta_pct is not None else None,
                    delta_color="normal",
                    help="Porcentaje de facturas OFB ya ingresadas en SISOR",
                )
            with k3:
                st.metric(
                    "Monto pendiente",
                    f"${float(curr['monto_pendiente']):,.0f}",
                    delta=f"${delta_monto:+,.0f}" if delta_monto is not None else None,
                    delta_color="inverse",
                    help="Monto total en MXN aún no capturado en SISOR",
                )
            with k4:
                st.metric(
                    "Monto cubierto",
                    f"${float(curr['monto_en_sisor']):,.0f}",
                    delta=f"${delta_cub:+,.0f}" if delta_cub is not None else None,
                    delta_color="normal",
                    help="Monto total en MXN ya capturado en SISOR",
                )

            st.divider()

            # ── Gráfica 1: Captura vs Pendientes + % cobertura ────────────────
            st.markdown("**Evolución de captura vs pendientes por día:**")
            pct_serie = (chart_df["en_sisor"] / chart_df["total_ofb"].replace(0, 1) * 100).round(1)

            fig1 = go.Figure()
            fig1.add_trace(go.Scatter(
                x=chart_df["fecha_dia"], y=chart_df["en_sisor"],
                name="En SISOR", mode="lines+markers",
                line=dict(color="#16A34A", width=2),
                marker=dict(size=6),
                hovertemplate="%{x|%d/%m/%Y}<br>En SISOR: %{y}<extra></extra>",
            ))
            fig1.add_trace(go.Scatter(
                x=chart_df["fecha_dia"], y=chart_df["pendientes"],
                name="Pendientes", mode="lines+markers",
                line=dict(color="#DC2626", width=2),
                marker=dict(size=6),
                hovertemplate="%{x|%d/%m/%Y}<br>Pendientes: %{y}<extra></extra>",
            ))
            fig1.add_trace(go.Scatter(
                x=chart_df["fecha_dia"], y=pct_serie,
                name="% Capturado", mode="lines",
                line=dict(color="#D97706", width=2, dash="dot"),
                yaxis="y2",
                hovertemplate="%{x|%d/%m/%Y}<br>% Capturado: %{y:.1f}%<extra></extra>",
            ))
            fig1.update_layout(
                xaxis=dict(tickformat="%d/%m", dtick="D1"),
                yaxis=dict(title="Facturas", rangemode="tozero"),
                yaxis2=dict(title="% Capturado", overlaying="y", side="right",
                            range=[0, 100], ticksuffix="%"),
                legend=dict(orientation="h", y=-0.2),
                hovermode="x unified",
                height=340,
                margin=dict(t=20, b=40),
            )
            st.plotly_chart(fig1, use_container_width=True)

            # ── Gráfica 2: Monto cubierto vs pendiente (área apilada) ──────────
            st.markdown("**Composición del monto total por día:**")
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(
                x=chart_df["fecha_dia"], y=chart_df["monto_en_sisor"],
                name="Monto en SISOR", mode="lines",
                fill="tozeroy", stackgroup="one",
                line=dict(color="#16A34A"),
                hovertemplate="%{x|%d/%m/%Y}<br>$%{y:,.0f}<extra></extra>",
            ))
            fig2.add_trace(go.Scatter(
                x=chart_df["fecha_dia"], y=chart_df["monto_pendiente"],
                name="Monto pendiente", mode="lines",
                fill="tonexty", stackgroup="one",
                line=dict(color="#DC2626"),
                hovertemplate="%{x|%d/%m/%Y}<br>$%{y:,.0f}<extra></extra>",
            ))
            fig2.update_layout(
                xaxis=dict(tickformat="%d/%m", dtick="D1"),
                yaxis=dict(title="MXN", tickprefix="$", tickformat=",.0f"),
                legend=dict(orientation="h", y=-0.2),
                hovermode="x unified",
                height=300,
                margin=dict(t=20, b=40),
            )
            st.plotly_chart(fig2, use_container_width=True)

            # ── Gráfica 3: Facturas capturadas por día ────────────────────────
            if len(chart_df) >= 3:
                st.markdown("**Facturas nuevas capturadas en SISOR por día:**")
                velocidad = chart_df["en_sisor"].diff().fillna(0).astype(int)
                colores   = ["#16A34A" if v >= 0 else "#DC2626" for v in velocidad]
                fig3 = go.Figure(go.Bar(
                    x=chart_df["fecha_dia"],
                    y=velocidad,
                    marker_color=colores,
                    hovertemplate="%{x|%d/%m/%Y}<br>Capturadas ese día: %{y:+d}<extra></extra>",
                ))
                fig3.update_layout(
                    xaxis=dict(tickformat="%d/%m", dtick="D1"),
                    yaxis=dict(title="Facturas capturadas", zeroline=True),
                    height=250,
                    margin=dict(t=10, b=40),
                )
                st.plotly_chart(fig3, use_container_width=True)

            st.divider()

            # ── Tabla mejorada (un renglón por día) ────────────────────────────
            st.markdown("**Tabla de historial (último run por día):**")
            hist_show = chart_df[["fecha_dia","total_ofb","pendientes","en_sisor","monto_pendiente","monto_en_sisor","modo"]].copy()
            hist_show["% capturado"] = (
                hist_show["en_sisor"] / hist_show["total_ofb"].replace(0, 1) * 100
            ).round(1)
            hist_show["fecha_dia"]       = hist_show["fecha_dia"].dt.strftime("%d/%m/%Y")
            hist_show["monto_pendiente"] = hist_show["monto_pendiente"].round(2)
            hist_show["monto_en_sisor"]  = hist_show["monto_en_sisor"].round(2)
            st.dataframe(
                hist_show.rename(columns={
                    "fecha_dia":       "Fecha",
                    "total_ofb":       "Total OFB",
                    "pendientes":      "Pendientes",
                    "en_sisor":        "En SISOR",
                    "monto_pendiente": "Monto pend. $",
                    "monto_en_sisor":  "Monto cubierto $",
                    "% capturado":     "% Capturado",
                    "modo":            "Modo",
                }),
                use_container_width=True,
                height=300,
                column_config={
                    "Monto pend. $":    st.column_config.NumberColumn(format="$%.2f"),
                    "Monto cubierto $": st.column_config.NumberColumn(format="$%.2f"),
                    "% Capturado":      st.column_config.NumberColumn(format="%.1f%%"),
                },
            )

    # ── Tab Órdenes de Compra ─────────────────────────────────────────────────

    with tab_oc:
        st.markdown("### 📦 Órdenes de Compra — Control de pendientes")

        df_oc_res = get_oc_resumen_proveedor()
        df_oc_det = get_oc_pendientes()

        # ── Semáforo de entrega ───────────────────────────────────────────────
        _hoy_oc = date.today()

        def _estado_entrega(fecha_str):
            try:
                if not fecha_str:
                    return "sin_fecha"
                f = date.fromisoformat(str(fecha_str).strip()[:10])
                dias = (f - _hoy_oc).days
                if dias < 0:
                    return "vencida"
                if dias <= 7:
                    return "proxima"
                return "a_tiempo"
            except Exception:
                return "sin_fecha"

        def _dias_restantes_oc(fecha_str):
            try:
                if not fecha_str:
                    return None
                return (date.fromisoformat(str(fecha_str).strip()[:10]) - _hoy_oc).days
            except Exception:
                return None

        if not df_oc_det.empty:
            df_oc_det = df_oc_det.copy()
            df_oc_det["estado_entrega"] = df_oc_det["fecha_entrega"].apply(_estado_entrega)
            df_oc_det["dias_restantes"] = df_oc_det["fecha_entrega"].apply(_dias_restantes_oc)

        if df_oc_res.empty:
            st.info(
                "**No hay Órdenes de Compra cargadas.**\n\n"
                "Sube el archivo `SEGUIMIENTO_OC.xlsx` desde la barra lateral "
                "para ver el control de materiales pendientes de entrega.",
                icon="📦",
            )
        else:
            # KPIs de OC
            monto_oc_total = df_oc_res["monto_pendiente"].sum()
            n_ocs_activas  = int(df_oc_res["ocs_activas"].sum())
            n_rengl_pend   = int(df_oc_det["pendiente"].count()) if not df_oc_det.empty else 0

            co1, co2, co3 = st.columns(3)
            with co1:
                st.markdown(f"""<div class="oak-metric red">
                    <div class="ml">OCs con pendiente</div>
                    <div class="mv">{n_ocs_activas}</div>
                    <div class="md">{len(df_oc_res)} proveedores</div></div>""",
                    unsafe_allow_html=True)
            with co2:
                st.markdown(f"""<div class="oak-metric amber">
                    <div class="ml">Renglones pendientes</div>
                    <div class="mv">{n_rengl_pend}</div>
                    <div class="md">materiales por recibir</div></div>""",
                    unsafe_allow_html=True)
            with co3:
                st.markdown(f"""<div class="oak-metric">
                    <div class="ml">Monto OC pendiente</div>
                    <div class="mv" style="font-size:1.3rem">${monto_oc_total:,.0f}</div>
                    <div class="md">MXN por recibir</div></div>""",
                    unsafe_allow_html=True)

            # ── Semáforo de entrega ───────────────────────────────────────────
            if not df_oc_det.empty and "estado_entrega" in df_oc_det.columns:
                n_vencidas  = int((df_oc_det["estado_entrega"] == "vencida").sum())
                n_proximas  = int((df_oc_det["estado_entrega"] == "proxima").sum())
                n_a_tiempo  = int((df_oc_det["estado_entrega"] == "a_tiempo").sum())
                n_sin_fecha = int((df_oc_det["estado_entrega"] == "sin_fecha").sum())
            else:
                n_vencidas = n_proximas = n_a_tiempo = n_sin_fecha = 0

            st.markdown(
                "<p style='font-size:.78rem;font-weight:700;color:#374151;"
                "text-transform:uppercase;letter-spacing:.5px;margin:18px 0 10px'>"
                "Semáforo de entregas</p>",
                unsafe_allow_html=True,
            )
            cs1, cs2, cs3, cs4 = st.columns(4)
            with cs1:
                st.markdown(f"""<div class="oak-metric red">
                    <div class="ml">Vencidas</div>
                    <div class="mv">{n_vencidas}</div>
                    <div class="md">fecha entrega pasada</div></div>""",
                    unsafe_allow_html=True)
            with cs2:
                st.markdown(f"""<div class="oak-metric amber">
                    <div class="ml">Próximas a vencer</div>
                    <div class="mv">{n_proximas}</div>
                    <div class="md">vencen en ≤7 días</div></div>""",
                    unsafe_allow_html=True)
            with cs3:
                st.markdown(f"""<div class="oak-metric green">
                    <div class="ml">A tiempo</div>
                    <div class="mv">{n_a_tiempo}</div>
                    <div class="md">más de 7 días restantes</div></div>""",
                    unsafe_allow_html=True)
            with cs4:
                st.markdown(f"""<div class="oak-metric navy">
                    <div class="ml">Sin fecha</div>
                    <div class="mv">{n_sin_fecha}</div>
                    <div class="md">sin fecha de entrega</div></div>""",
                    unsafe_allow_html=True)

            st.divider()

            # Sub-tabs de OC
            oc_tab1, oc_tab2, oc_tab3, oc_tab4 = st.tabs([
                "📋 Resumen por proveedor",
                "🔍 Detalle por renglón",
                "🔗 Cruce OC ↔ Factura SAT",
                "🚨 Facturas sin OC",
            ])

            with oc_tab1:
                st.dataframe(
                    df_oc_res.rename(columns={
                        "proveedor": "Proveedor",
                        "ocs_activas": "OCs",
                        "total_comprometido": "Total comprometido $",
                        "monto_pendiente": "Monto pendiente $",
                        "renglones_pendientes": "Renglones pend.",
                        "primera_oc": "Primera OC",
                        "ultima_oc": "Última OC",
                    }),
                    use_container_width=True,
                    column_config={
                        "Total comprometido $": st.column_config.NumberColumn(format="$%.2f"),
                        "Monto pendiente $":    st.column_config.NumberColumn(format="$%.2f"),
                    },
                )

                # Gráfica top proveedores por monto pendiente
                if len(df_oc_res) > 0:
                    top_oc = df_oc_res.head(10).set_index("proveedor")
                    st.bar_chart(
                        top_oc[["monto_pendiente"]].rename(
                            columns={"monto_pendiente": "Monto pendiente"}
                        ),
                        color=["#D97706"],
                    )

            with oc_tab2:
                if df_oc_det.empty:
                    st.info("Sin renglones pendientes.")
                else:
                    # Filtros
                    dc1, dc2, dc3 = st.columns(3)
                    with dc1:
                        provs_oc = sorted(df_oc_det["proveedor"].dropna().unique().tolist())
                        sel_prov_oc = st.multiselect("Filtrar por proveedor", provs_oc, key="f_prov_oc")
                    with dc2:
                        familias = sorted(df_oc_det["familia"].dropna().unique().tolist())
                        sel_familia = st.multiselect("Filtrar por familia", familias, key="f_familia_oc")
                    with dc3:
                        _estados_map = {
                            "Todos": None,
                            "Vencidas": "vencida",
                            "Próximas a vencer": "proxima",
                            "A tiempo": "a_tiempo",
                            "Sin fecha": "sin_fecha",
                        }
                        sel_estado_oc = st.selectbox(
                            "Estado de entrega", list(_estados_map.keys()), key="f_estado_oc"
                        )

                    df_det_f = df_oc_det.copy()
                    if sel_prov_oc:
                        df_det_f = df_det_f[df_det_f["proveedor"].isin(sel_prov_oc)]
                    if sel_familia:
                        df_det_f = df_det_f[df_det_f["familia"].isin(sel_familia)]
                    if _estados_map[sel_estado_oc] and "estado_entrega" in df_det_f.columns:
                        df_det_f = df_det_f[
                            df_det_f["estado_entrega"] == _estados_map[sel_estado_oc]
                        ]

                    # Ordenar: vencidas primero, luego próximas, a tiempo, sin fecha
                    if "estado_entrega" in df_det_f.columns and not df_det_f.empty:
                        _ord = {"vencida": 0, "proxima": 1, "a_tiempo": 2, "sin_fecha": 3}
                        df_det_f = df_det_f.copy()
                        df_det_f["_s"] = df_det_f["estado_entrega"].map(_ord).fillna(9)
                        df_det_f = df_det_f.sort_values(["_s", "dias_restantes"]).drop(columns=["_s"])

                    cols_det = [c for c in [
                        "estado_entrega", "dias_restantes",
                        "oc", "fecha", "proveedor", "familia", "material",
                        "cantidad", "facturado", "pendiente", "unidad",
                        "monto_pendiente", "fecha_entrega",
                    ] if c in df_det_f.columns]

                    _labels_det = {
                        "estado_entrega":  "Estado",
                        "dias_restantes":  "Días rest.",
                        "oc":              "OC",
                        "fecha":           "Fecha OC",
                        "proveedor":       "Proveedor",
                        "familia":         "Familia",
                        "material":        "Material",
                        "cantidad":        "Cantidad",
                        "facturado":       "Facturado",
                        "pendiente":       "Pendiente",
                        "unidad":          "Unidad",
                        "monto_pendiente": "Monto pend. $",
                        "fecha_entrega":   "F. Entrega",
                    }

                    df_show_det = df_det_f[cols_det].rename(columns=_labels_det).copy()

                    # Etiquetas legibles para la columna Estado
                    if "Estado" in df_show_det.columns:
                        _etiq = {
                            "vencida":   "Vencida",
                            "proxima":   "Próxima",
                            "a_tiempo":  "A tiempo",
                            "sin_fecha": "Sin fecha",
                        }
                        df_show_det["Estado"] = df_show_det["Estado"].map(_etiq).fillna("—")

                    def _style_estado(val: str) -> str:
                        _m = {
                            "Vencida":  "background-color:#FEE2E2;color:#991B1B;font-weight:700",
                            "Próxima":  "background-color:#FEF3C7;color:#92400E;font-weight:600",
                            "A tiempo": "background-color:#F0FDF4;color:#166534;font-weight:600",
                        }
                        return _m.get(str(val), "color:#64748B")

                    def _style_dias(val) -> str:
                        try:
                            if val is None or pd.isna(val):
                                return "color:#94A3B8"
                            v = int(val)
                            if v < 0:
                                return "background-color:#FEE2E2;color:#991B1B;font-weight:700"
                            if v <= 7:
                                return "background-color:#FEF3C7;color:#92400E;font-weight:600"
                            return "color:#15803D;font-weight:600"
                        except Exception:
                            return ""

                    styled_det = df_show_det.style
                    if "Estado" in df_show_det.columns and not df_show_det.empty:
                        styled_det = styled_det.map(_style_estado, subset=["Estado"])
                    if "Días rest." in df_show_det.columns and not df_show_det.empty:
                        styled_det = styled_det.map(_style_dias, subset=["Días rest."])

                    st.dataframe(
                        styled_det,
                        use_container_width=True,
                        height=min(600, 60 + len(df_det_f) * 35),
                        column_config={
                            "Monto pend. $": st.column_config.NumberColumn(format="$%.2f"),
                            "Días rest.":    st.column_config.NumberColumn(format="%d días"),
                            "F. Entrega":    st.column_config.DateColumn(format="DD/MM/YYYY"),
                        },
                    )

                    st.markdown(
                        '<small>'
                        '<span style="background:#FEE2E2;padding:2px 8px;border-radius:4px;'
                        'color:#991B1B">■ Vencida</span> &nbsp;'
                        '<span style="background:#FEF3C7;padding:2px 8px;border-radius:4px;'
                        'color:#92400E">■ Próxima ≤7 días</span> &nbsp;'
                        '<span style="background:#F0FDF4;padding:2px 8px;border-radius:4px;'
                        'color:#166534">■ A tiempo &gt;7 días</span>'
                        '</small>',
                        unsafe_allow_html=True,
                    )

            with oc_tab3:
                # ── Bloque 2: Cruce OC ↔ Factura SAT ────────────────────────
                st.markdown("#### 🔗 ¿Qué OCs ya tienen CFDI recibido en el SAT?")
                st.caption(
                    "Por cada renglón pendiente de OC se verifica si el proveedor "
                    "tiene facturas registradas en el archivo OFB (SAT). "
                    "Verde = sí llegó factura · Rojo = sin CFDI en SAT."
                )

                df_ofb_cruce = get_facturas_ofb()

                if df_ofb_cruce.empty:
                    st.info(
                        "No hay facturas OFB cargadas. "
                        "Sube el Excel del contador desde la barra lateral para ver el cruce.",
                        icon="📄",
                    )
                elif df_oc_det.empty:
                    st.info("No hay renglones OC pendientes para cruzar.", icon="📦")
                else:
                    # Normalizar proveedor en OFB (mismo criterio que oc_parser)
                    import re as _re
                    df_ofb_c = df_ofb_cruce.copy()
                    df_ofb_c["prov_norm"] = (
                        df_ofb_c["proveedor"]
                        .fillna("").astype(str).str.upper().str.strip()
                        .apply(lambda x: _re.sub(r"\s*\(\d{4}\)\s*$", "", x).strip())
                    )

                    # Agregar OFB por proveedor normalizado
                    ofb_agg = (
                        df_ofb_c.groupby("prov_norm")
                        .agg(
                            n_cfdi_sat   =("uuid",  "count"),
                            monto_cfdi   =("total", "sum"),
                            ult_cfdi_sat =("fecha", "max"),
                        )
                        .reset_index()
                    )
                    provs_ofb_set = set(ofb_agg["prov_norm"].tolist())

                    # Construir tabla de cruce desde OC pendientes
                    df_cruce = df_oc_det.copy()
                    df_cruce["prov_norm"] = (
                        df_cruce["proveedor"]
                        .fillna("").astype(str).str.upper().str.strip()
                    )
                    df_cruce["tiene_cfdi"] = df_cruce["prov_norm"].isin(provs_ofb_set)

                    df_cruce = df_cruce.merge(
                        ofb_agg,
                        on="prov_norm",
                        how="left",
                    )
                    df_cruce["n_cfdi_sat"]   = df_cruce["n_cfdi_sat"].fillna(0).astype(int)
                    df_cruce["monto_cfdi"]   = df_cruce["monto_cfdi"].fillna(0.0)
                    df_cruce["ult_cfdi_sat"] = df_cruce["ult_cfdi_sat"].fillna("")

                    # ── KPIs de cruce ────────────────────────────────────────
                    n_con_cfdi    = int(df_cruce["tiene_cfdi"].sum())
                    n_sin_cfdi    = int((~df_cruce["tiene_cfdi"]).sum())
                    monto_con     = df_cruce.loc[df_cruce["tiene_cfdi"], "monto_pendiente"].sum()
                    monto_sin     = df_cruce.loc[~df_cruce["tiene_cfdi"], "monto_pendiente"].sum()

                    ck1, ck2 = st.columns(2)
                    with ck1:
                        st.markdown(f"""<div class="oak-metric green">
                            <div class="ml">Con CFDI en SAT</div>
                            <div class="mv">{n_con_cfdi}</div>
                            <div class="md">renglones · ${monto_con:,.0f} pend.</div></div>""",
                            unsafe_allow_html=True)
                    with ck2:
                        st.markdown(f"""<div class="oak-metric red">
                            <div class="ml">Sin CFDI en SAT</div>
                            <div class="mv">{n_sin_cfdi}</div>
                            <div class="md">renglones · ${monto_sin:,.0f} pend.</div></div>""",
                            unsafe_allow_html=True)

                    st.markdown("")

                    # ── Filtro rápido ─────────────────────────────────────────
                    _cruce_opts = {
                        "Todos": None,
                        "✅ Con CFDI": True,
                        "❌ Sin CFDI": False,
                    }
                    sel_cruce = st.radio(
                        "Mostrar:",
                        list(_cruce_opts.keys()),
                        horizontal=True,
                        key="f_cruce_oc",
                    )

                    df_cruce_f = df_cruce.copy()
                    if _cruce_opts[sel_cruce] is not None:
                        df_cruce_f = df_cruce_f[
                            df_cruce_f["tiene_cfdi"] == _cruce_opts[sel_cruce]
                        ]

                    # Ordenar: sin CFDI primero (mayor riesgo)
                    df_cruce_f = df_cruce_f.sort_values(
                        ["tiene_cfdi", "monto_pendiente"],
                        ascending=[True, False],
                    ).reset_index(drop=True)

                    # Etiqueta legible
                    df_cruce_f["cfdi_status"] = df_cruce_f["tiene_cfdi"].map(
                        {True: "✅ Sí", False: "❌ No"}
                    )

                    # Convertir fecha max a string legible
                    df_cruce_f["ult_cfdi_sat"] = pd.to_datetime(
                        df_cruce_f["ult_cfdi_sat"], errors="coerce"
                    ).dt.strftime("%d/%m/%Y").fillna("—")

                    cols_cruce = [c for c in [
                        "cfdi_status", "oc", "proveedor", "familia", "material",
                        "pendiente", "monto_pendiente", "fecha_entrega",
                        "n_cfdi_sat", "monto_cfdi", "ult_cfdi_sat",
                    ] if c in df_cruce_f.columns]

                    _labels_cruce = {
                        "cfdi_status":      "CFDI en SAT",
                        "oc":               "OC",
                        "proveedor":        "Proveedor",
                        "familia":          "Familia",
                        "material":         "Material",
                        "pendiente":        "Pend.",
                        "monto_pendiente":  "Monto pend. $",
                        "fecha_entrega":    "F. Entrega",
                        "n_cfdi_sat":       "# CFDIs SAT",
                        "monto_cfdi":       "$ CFDIs SAT",
                        "ult_cfdi_sat":     "Últ. factura SAT",
                    }

                    df_show_cruce = df_cruce_f[cols_cruce].rename(columns=_labels_cruce).copy()

                    def _style_cfdi_status(val: str) -> str:
                        if "Sí" in str(val):
                            return "background-color:#F0FDF4;color:#166534;font-weight:700"
                        if "No" in str(val):
                            return "background-color:#FEE2E2;color:#991B1B;font-weight:700"
                        return ""

                    styled_cruce = df_show_cruce.style
                    if "CFDI en SAT" in df_show_cruce.columns and not df_show_cruce.empty:
                        styled_cruce = styled_cruce.map(
                            _style_cfdi_status, subset=["CFDI en SAT"]
                        )

                    st.dataframe(
                        styled_cruce,
                        use_container_width=True,
                        height=min(600, 60 + len(df_cruce_f) * 35),
                        column_config={
                            "Monto pend. $":  st.column_config.NumberColumn(format="$%.2f"),
                            "$ CFDIs SAT":    st.column_config.NumberColumn(format="$%.2f"),
                            "F. Entrega":     st.column_config.DateColumn(format="DD/MM/YYYY"),
                        },
                    )

                    st.markdown(
                        '<small>'
                        '<span style="background:#F0FDF4;padding:2px 8px;border-radius:4px;'
                        'color:#166534">✅ Con CFDI</span> — el proveedor tiene facturas en SAT · '
                        '<span style="background:#FEE2E2;padding:2px 8px;border-radius:4px;'
                        'color:#991B1B">❌ Sin CFDI</span> — no hay factura recibida de ese proveedor'
                        '</small>',
                        unsafe_allow_html=True,
                    )

            with oc_tab4:
                # ── Bloque 3: Saldo OC vs CFDI por proveedor ─────────────────
                st.markdown("#### 📊 Saldo OC vs Factura por Proveedor")
                st.caption(
                    "Compara el monto total de OC registrado en el sistema con el monto "
                    "total de CFDIs timbrados en el SAT, agrupado por proveedor. "
                    "No relaciona facturas individuales — muestra el saldo global por proveedor."
                )

                _df_ofb_b3 = get_facturas_ofb()

                # Filtrar excluidas
                _excl_b3 = cargar_exclusiones()
                if _excl_b3 and not _df_ofb_b3.empty and "rfc_emisor" in _df_ofb_b3.columns:
                    _rfcs_b3 = {k.upper() for k in _excl_b3.keys()}
                    _df_ofb_b3 = _df_ofb_b3[
                        ~_df_ofb_b3["rfc_emisor"].str.upper().isin(_rfcs_b3)
                    ].reset_index(drop=True)

                _df_oc_b3 = get_oc_total_proveedor()

                if _df_ofb_b3.empty and _df_oc_b3.empty:
                    st.info(
                        "No hay datos cargados. Sube el OFB y el archivo de OC.",
                        icon="📄",
                    )
                else:
                    # Agrupar OFB por proveedor (normalizado)
                    if not _df_ofb_b3.empty:
                        _cfdi_grp = (
                            _df_ofb_b3.assign(
                                prov_k=_df_ofb_b3["proveedor"]
                                .fillna("").astype(str).str.upper().str.strip()
                            )
                            .groupby("prov_k")
                            .agg(monto_cfdi=("total", "sum"), n_cfdi=("total", "count"))
                            .reset_index()
                            .rename(columns={"prov_k": "proveedor"})
                        )
                    else:
                        _cfdi_grp = pd.DataFrame(columns=["proveedor", "monto_cfdi", "n_cfdi"])

                    # Join OC (ya normalizado) con CFDIs
                    _saldo = pd.merge(
                        _cfdi_grp,
                        _df_oc_b3[["proveedor", "monto_oc", "ocs_distintas"]],
                        on="proveedor",
                        how="outer",
                    ).fillna({"monto_cfdi": 0.0, "n_cfdi": 0, "monto_oc": 0.0, "ocs_distintas": 0})

                    _saldo["diferencia"] = (_saldo["monto_cfdi"] - _saldo["monto_oc"]).round(2)

                    def _est_saldo(row):
                        if row["monto_oc"] == 0 and row["monto_cfdi"] > 0:
                            return "🔴 Sin OC"
                        if row["monto_cfdi"] == 0 and row["monto_oc"] > 0:
                            return "🔵 Solo OC"
                        if row["diferencia"] > 0:
                            return "🟡 Excedente"
                        return "🟢 Cubierto"

                    _saldo["estado"] = _saldo.apply(_est_saldo, axis=1)

                    # KPIs
                    _n_sin_oc  = (_saldo["estado"] == "🔴 Sin OC").sum()
                    _mto_sin   = _saldo.loc[_saldo["estado"] == "🔴 Sin OC", "monto_cfdi"].sum()
                    _n_exc     = (_saldo["estado"] == "🟡 Excedente").sum()
                    _mto_exc   = _saldo.loc[_saldo["estado"] == "🟡 Excedente", "diferencia"].sum()
                    _n_ok      = (_saldo["estado"] == "🟢 Cubierto").sum()
                    _n_solo_oc = (_saldo["estado"] == "🔵 Solo OC").sum()

                    sk1, sk2, sk3, sk4 = st.columns(4)
                    with sk1:
                        st.markdown(f"""<div class="oak-metric red">
                            <div class="ml">Sin OC</div>
                            <div class="mv">{_n_sin_oc}</div>
                            <div class="md">${_mto_sin:,.0f} sin respaldo</div></div>""",
                            unsafe_allow_html=True)
                    with sk2:
                        st.markdown(f"""<div class="oak-metric amber">
                            <div class="ml">Excedente facturado</div>
                            <div class="mv">{_n_exc}</div>
                            <div class="md">${_mto_exc:,.0f} sobre OC</div></div>""",
                            unsafe_allow_html=True)
                    with sk3:
                        st.markdown(f"""<div class="oak-metric green">
                            <div class="ml">Cubiertos</div>
                            <div class="mv">{_n_ok}</div>
                            <div class="md">OC ≥ CFDI</div></div>""",
                            unsafe_allow_html=True)
                    with sk4:
                        st.markdown(f"""<div class="oak-metric blue">
                            <div class="ml">Solo OC (sin CFDI)</div>
                            <div class="mv">{_n_solo_oc}</div>
                            <div class="md">Aún no facturan</div></div>""",
                            unsafe_allow_html=True)

                    st.markdown("")

                    # Filtro por estado
                    _est_opts = ["Todos", "🔴 Sin OC", "🟡 Excedente", "🟢 Cubierto", "🔵 Solo OC"]
                    _sel_est = st.radio(
                        "Mostrar:",
                        _est_opts,
                        horizontal=True,
                        key="f_saldo_est",
                    )

                    _saldo_f = (
                        _saldo if _sel_est == "Todos"
                        else _saldo[_saldo["estado"] == _sel_est]
                    ).copy()

                    _saldo_f = _saldo_f.sort_values(
                        ["estado", "diferencia"], ascending=[True, False]
                    ).reset_index(drop=True)

                    # Columnas a mostrar
                    _cols_s = [c for c in [
                        "estado", "proveedor", "monto_oc", "monto_cfdi",
                        "diferencia", "ocs_distintas", "n_cfdi",
                    ] if c in _saldo_f.columns]
                    _labs_s = {
                        "estado":       "Estado",
                        "proveedor":    "Proveedor",
                        "monto_oc":     "Total OC $",
                        "monto_cfdi":   "Total CFDI $",
                        "diferencia":   "Diferencia $",
                        "ocs_distintas":"# OC",
                        "n_cfdi":       "# CFDI",
                    }
                    _df_show_s = _saldo_f[_cols_s].rename(columns=_labs_s)

                    def _color_estado_s(val: str) -> str:
                        v = str(val)
                        if "Sin OC"    in v: return "background:#FEE2E2;color:#991B1B;font-weight:700"
                        if "Excedente" in v: return "background:#FEF9C3;color:#854D0E;font-weight:700"
                        if "Cubierto"  in v: return "background:#F0FDF4;color:#166534;font-weight:700"
                        if "Solo OC"   in v: return "background:#EFF6FF;color:#1E40AF;font-weight:700"
                        return ""

                    def _color_dif_s(val) -> str:
                        try:
                            v = float(val)
                            if v > 0:   return "color:#991B1B;font-weight:700"
                            if v < 0:   return "color:#166534"
                        except (TypeError, ValueError):
                            pass
                        return ""

                    _styled_s = _df_show_s.style
                    if "Estado" in _df_show_s.columns and not _df_show_s.empty:
                        _styled_s = _styled_s.map(_color_estado_s, subset=["Estado"])
                    if "Diferencia $" in _df_show_s.columns and not _df_show_s.empty:
                        _styled_s = _styled_s.map(_color_dif_s, subset=["Diferencia $"])

                    st.dataframe(
                        _styled_s,
                        use_container_width=True,
                        height=min(600, 60 + len(_saldo_f) * 35),
                        column_config={
                            "Total OC $":   st.column_config.NumberColumn(format="$%.2f"),
                            "Total CFDI $": st.column_config.NumberColumn(format="$%.2f"),
                            "Diferencia $": st.column_config.NumberColumn(format="$%.2f"),
                        },
                    )

                    st.markdown(
                        '<small>⚠️ La comparación es a nivel de proveedor, no por factura individual. '
                        'Un proveedor "Excedente" facturó más de lo que tiene en OC. '
                        '"Sin OC" significa que no tiene ninguna OC registrada en el sistema.</small>',
                        unsafe_allow_html=True,
                    )

    # ── Tab Actividad ─────────────────────────────────────────────────────────

    with tab_act:
        st.markdown("### 📅 Actividad diaria y semanal")

        act_vista = st.radio(
            "Vista:",
            options=["📆 Por día", "📊 Por semana"],
            horizontal=True,
            key="act_vista",
        )

        # ── Vista diaria ──────────────────────────────────────────────────────
        if act_vista == "📆 Por día":
            fecha_max_db = _max_fecha_captura()
            fecha_default = (
                date.fromisoformat(fecha_max_db) if fecha_max_db else date.today()
            )
            fecha_sel = st.date_input(
                "Fecha a consultar:",
                value=fecha_default,
                max_value=date.today(),
                key="act_fecha_dia",
            )
            fecha_str = fecha_sel.isoformat()

            df_sisor_dia = get_sisor_del_dia(fecha_str)
            df_oc_dia    = get_oc_del_dia(fecha_str)

            n_fact_d = len(df_sisor_dia)
            m_fact_d = float(df_sisor_dia["importe_num"].sum()) if not df_sisor_dia.empty else 0.0
            n_oc_d   = len(df_oc_dia)
            m_oc_d   = float(df_oc_dia["total"].sum()) if not df_oc_dia.empty else 0.0

            ad1, ad2, ad3, ad4 = st.columns(4)
            with ad1:
                st.metric("Facturas capturadas", n_fact_d)
            with ad2:
                st.metric("Monto SISOR", f"${m_fact_d:,.0f}")
            with ad3:
                st.metric("OC generadas", n_oc_d)
            with ad4:
                st.metric("Monto OC", f"${m_oc_d:,.0f}")

            st.divider()

            if df_sisor_dia.empty and df_oc_dia.empty:
                st.info(f"Sin actividad registrada para el {fecha_sel.strftime('%d/%m/%Y')}.")
            else:
                if not df_sisor_dia.empty:
                    st.markdown("**Facturas ingresadas en SISOR:**")
                    cols_s = [c for c in ["proveedor","factura_str","importe_num","fecha_captura"] if c in df_sisor_dia.columns]
                    st.dataframe(
                        df_sisor_dia[cols_s].rename(columns={
                            "proveedor": "Proveedor", "factura_str": "Factura",
                            "importe_num": "Importe", "fecha_captura": "Fecha captura",
                        }),
                        use_container_width=True,
                        column_config={
                            "Importe": st.column_config.NumberColumn(format="$%.2f"),
                        },
                    )

                if not df_oc_dia.empty:
                    st.markdown("**OC generadas:**")
                    cols_o = [c for c in ["oc","proveedor","material","cantidad","unidad","total"] if c in df_oc_dia.columns]
                    st.dataframe(
                        df_oc_dia[cols_o].rename(columns={
                            "oc": "OC#", "proveedor": "Proveedor", "material": "Material",
                            "cantidad": "Cantidad", "unidad": "Unidad", "total": "Total",
                        }),
                        use_container_width=True,
                        column_config={
                            "Total": st.column_config.NumberColumn(format="$%.2f"),
                        },
                    )

        # ── Vista semanal ─────────────────────────────────────────────────────
        else:
            if "act_semana_offset" not in st.session_state:
                st.session_state.act_semana_offset = 0

            col_prev, col_titulo, col_next = st.columns([1, 4, 1])
            with col_prev:
                if st.button("← Anterior", use_container_width=True):
                    st.session_state.act_semana_offset -= 1
                    st.rerun()
            with col_next:
                if st.button("Siguiente →", use_container_width=True,
                             disabled=st.session_state.act_semana_offset >= 0):
                    st.session_state.act_semana_offset += 1
                    st.rerun()

            offset = st.session_state.act_semana_offset
            lunes_base = date.today() - timedelta(days=date.today().weekday())
            lunes_sel  = lunes_base + timedelta(weeks=offset)
            sabado_sel = lunes_sel + timedelta(days=5)

            with col_titulo:
                st.markdown(
                    f"**Semana del {lunes_sel.strftime('%d/%m')} al {sabado_sel.strftime('%d/%m/%Y')}**",
                )

            df_sem = get_actividad_semanal(lunes_sel.isoformat())

            # Totales
            hoy_str = date.today().isoformat()
            df_pasado = df_sem[df_sem["fecha"] <= hoy_str]
            t_f  = int(df_pasado["n_facturas"].sum())
            t_mf = float(df_pasado["monto_facturas"].sum())
            t_o  = int(df_pasado["n_oc"].sum())
            t_mo = float(df_pasado["monto_oc"].sum())

            ws1, ws2, ws3, ws4 = st.columns(4)
            with ws1:
                st.metric("Total facturas semana", t_f)
            with ws2:
                st.metric("Monto SISOR semana", f"${t_mf:,.0f}")
            with ws3:
                st.metric("Total OC semana", t_o)
            with ws4:
                st.metric("Monto OC semana", f"${t_mo:,.0f}")

            st.divider()

            # Tabla día por día
            filas_display = []
            for _, r in df_sem.iterrows():
                d_str  = str(r["fecha"])
                futuro = d_str > hoy_str
                filas_display.append({
                    "Día":             r["dia_nombre"],
                    "Fecha":           date.fromisoformat(d_str).strftime("%d/%m"),
                    "Facturas cap.":   None if futuro else int(r["n_facturas"]),
                    "Monto SISOR":     None if futuro else float(r["monto_facturas"]),
                    "OC generadas":    None if futuro else int(r["n_oc"]),
                    "Monto OC":        None if futuro else float(r["monto_oc"]),
                })
            df_display = pd.DataFrame(filas_display)
            st.dataframe(
                df_display,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Monto SISOR": st.column_config.NumberColumn(format="$%.0f"),
                    "Monto OC":    st.column_config.NumberColumn(format="$%.0f"),
                },
            )

    # ── Tab Gestionar OFB ────────────────────────────────────────────────────

    with tab_gestionar:
        st.markdown("### 🗑️ Eliminar facturas del OFB")
        st.info(
            "Usa esta pantalla para eliminar facturas timbradas que **no debes pagar** "
            "(por ejemplo: facturas que no recibiste o que fueron canceladas). "
            "La eliminación es **permanente** — solo borra de esta app, no del SAT.",
            icon="⚠️",
        )

        df_ofb_all = get_facturas_ofb()

        if df_ofb_all.empty:
            st.warning("No hay facturas OFB en la base de datos.")
        else:
            # ── Estado según comparación ──────────────────────────────────────
            uuids_pend   = set(pendientes_raw["uuid"].dropna().astype(str).str.upper()) if not pendientes_raw.empty and "uuid" in pendientes_raw.columns else set()
            uuids_sisor  = set(en_sisor["uuid"].dropna().astype(str).str.upper())       if not en_sisor.empty   and "uuid" in en_sisor.columns         else set()
            uuids_excl   = set(excluidos_df["uuid"].dropna().astype(str).str.upper())   if not excluidos_df.empty and "uuid" in excluidos_df.columns    else set()

            def _estado(uuid_val):
                u = str(uuid_val).upper().strip() if pd.notna(uuid_val) else ""
                if u in uuids_sisor:
                    return "✅ En SISOR"
                if u in uuids_excl:
                    return "⚙️ Excluida"
                if u in uuids_pend:
                    return "🔴 Pendiente"
                return "— Sin comparar"

            df_ofb_all["_estado"] = df_ofb_all["uuid"].apply(_estado)

            # ── Filtro por estado ─────────────────────────────────────────────
            filtro_estado = st.radio(
                "Mostrar:",
                ["Todas", "🔴 Pendientes", "✅ Ya en SISOR", "⚙️ Excluidas"],
                horizontal=True,
                key="g_estado",
            )
            estado_map = {
                "🔴 Pendientes":  "🔴 Pendiente",
                "✅ Ya en SISOR": "✅ En SISOR",
                "⚙️ Excluidas":   "⚙️ Excluida",
            }

            # ── Filtros adicionales — fila 1 ─────────────────────────────────
            gc1, gc2, gc3 = st.columns([2, 2, 2])
            with gc1:
                provs_g = ["— Todos —"] + sorted(df_ofb_all["proveedor"].dropna().unique().tolist())
                sel_prov_g = st.selectbox("Proveedor", provs_g, key="g_prov")
            with gc2:
                busq_folio = st.text_input("Buscar folio / UUID", key="g_folio",
                                           placeholder="folio, UUID o parte de él")
            with gc3:
                if "fecha" in df_ofb_all.columns and df_ofb_all["fecha"].notna().any():
                    min_fg = df_ofb_all["fecha"].min().date()
                    max_fg = df_ofb_all["fecha"].max().date()
                    rango_g = st.date_input("Rango de fechas", value=(min_fg, max_fg),
                                            min_value=min_fg, max_value=max_fg, key="g_fecha")
                else:
                    rango_g = None

            # ── Filtros — fila 2: monto y orden ──────────────────────────────
            gm1, gm2, gm3 = st.columns([2, 2, 2])
            _total_vals = df_ofb_all["total"].dropna() if "total" in df_ofb_all.columns else pd.Series(dtype=float)
            _monto_min_abs = float(_total_vals.min()) if not _total_vals.empty else 0.0
            _monto_max_abs = float(_total_vals.max()) if not _total_vals.empty else 0.0
            with gm1:
                monto_min_g = st.number_input(
                    "Monto mínimo $", min_value=0.0, value=0.0,
                    step=500.0, format="%.2f", key="g_monto_min",
                )
            with gm2:
                monto_max_g = st.number_input(
                    "Monto máximo $", min_value=0.0, value=_monto_max_abs,
                    step=500.0, format="%.2f", key="g_monto_max",
                )
            with gm3:
                orden_g = st.selectbox(
                    "Ordenar por",
                    ["Fecha ↓ (más reciente)", "Fecha ↑ (más antigua)",
                     "Monto ↓ (mayor primero)", "Monto ↑ (menor primero)",
                     "Proveedor A→Z"],
                    key="g_orden",
                )

            # ── Aplicar filtros ───────────────────────────────────────────────
            df_g = df_ofb_all.copy()
            if filtro_estado in estado_map:
                df_g = df_g[df_g["_estado"] == estado_map[filtro_estado]]
            if sel_prov_g != "— Todos —":
                df_g = df_g[df_g["proveedor"] == sel_prov_g]
            if busq_folio.strip():
                term = busq_folio.strip().lower()
                mask = (
                    df_g["folio"].fillna("").str.lower().str.contains(term) |
                    df_g["uuid"].fillna("").str.lower().str.contains(term)
                )
                df_g = df_g[mask]
            if rango_g and len(rango_g) == 2 and "fecha" in df_g.columns:
                df_g = df_g[(df_g["fecha"].dt.date >= rango_g[0]) &
                            (df_g["fecha"].dt.date <= rango_g[1])]
            if "total" in df_g.columns:
                if monto_min_g > 0:
                    df_g = df_g[df_g["total"] >= monto_min_g]
                if monto_max_g < _monto_max_abs:
                    df_g = df_g[df_g["total"] <= monto_max_g]

            # ── Ordenar ───────────────────────────────────────────────────────
            _sort_map = {
                "Fecha ↓ (más reciente)":  ("fecha",     False),
                "Fecha ↑ (más antigua)":   ("fecha",     True),
                "Monto ↓ (mayor primero)": ("total",     False),
                "Monto ↑ (menor primero)": ("total",     True),
                "Proveedor A→Z":           ("proveedor", True),
            }
            _sort_col, _sort_asc = _sort_map.get(orden_g, ("fecha", False))
            if _sort_col in df_g.columns:
                df_g = df_g.sort_values(_sort_col, ascending=_sort_asc, na_position="last")

            n_pend_g  = (df_ofb_all["_estado"] == "🔴 Pendiente").sum()
            n_sisor_g = (df_ofb_all["_estado"] == "✅ En SISOR").sum()
            n_excl_g  = (df_ofb_all["_estado"] == "⚙️ Excluida").sum()
            st.caption(
                f"**{len(df_g)}** mostradas · "
                f"Total OFB: {len(df_ofb_all)} — "
                f"🔴 {n_pend_g} pendientes · "
                f"✅ {n_sisor_g} en SISOR · "
                f"⚙️ {n_excl_g} excluidas"
            )

            cols_g = [c for c in ["id", "_estado", "proveedor", "rfc_emisor", "folio", "uuid",
                                   "fecha", "total", "moneda", "estado_sat"]
                      if c in df_g.columns]
            df_g_show = df_g[cols_g].copy()
            df_g_show.insert(0, "Eliminar", False)

            edited_g = st.data_editor(
                df_g_show,
                column_config={
                    "Eliminar":   st.column_config.CheckboxColumn("Eliminar", width="small"),
                    "id":         st.column_config.NumberColumn("ID", width="small"),
                    "_estado":    st.column_config.TextColumn("Estado", width="medium"),
                    "proveedor":  st.column_config.TextColumn("Proveedor"),
                    "rfc_emisor": st.column_config.TextColumn("RFC"),
                    "folio":      st.column_config.TextColumn("Folio"),
                    "uuid":       st.column_config.TextColumn("UUID / Folio Fiscal"),
                    "fecha":      st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
                    "total":      st.column_config.NumberColumn("Total", format="$%.2f"),
                    "moneda":     st.column_config.TextColumn("Moneda", width="small"),
                    "estado_sat": st.column_config.TextColumn("Estado SAT"),
                },
                disabled=[c for c in cols_g],
                hide_index=True,
                use_container_width=True,
                height=min(500, 60 + len(df_g_show) * 35),
                key="gestionar_editor",
            )

            n_sel = int(edited_g["Eliminar"].sum())
            ids_sel = edited_g.loc[edited_g["Eliminar"], "id"].tolist() if n_sel > 0 else []

            st.divider()
            gb1, gb2 = st.columns([2, 3])
            with gb1:
                boton_eliminar = st.button(
                    f"🗑️ Eliminar {n_sel} factura(s) seleccionada(s)",
                    type="primary",
                    disabled=n_sel == 0,
                    use_container_width=True,
                    key="btn_eliminar_ofb",
                )
            with gb2:
                if n_sel > 0:
                    monto_sel = edited_g.loc[edited_g["Eliminar"], "total"].sum() if "total" in edited_g.columns else 0.0
                    st.caption(
                        f"Seleccionadas: **{n_sel}** factura(s) · "
                        f"Monto total: **${monto_sel:,.2f}**"
                    )

            if boton_eliminar and ids_sel:
                n_eliminadas = eliminar_facturas_ofb(ids_sel)
                st.success(f"✅ {n_eliminadas} factura(s) eliminada(s) correctamente.")
                st.session_state.resultado = None
                st.rerun()
