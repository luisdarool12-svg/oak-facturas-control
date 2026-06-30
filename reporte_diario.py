"""
Script autónomo que genera y envía el reporte diario por email.
Ejecutado por el LaunchAgent de macOS a las 8:00am (lunes a sábado).

Uso manual:
    python3 reporte_diario.py

Requiere:
    - data/facturas.db con datos cargados
    - .env con GMAIL_USER y GMAIL_APP_PASSWORD
"""
import sys
import os
import traceback
from datetime import datetime, date
from pathlib import Path

# Asegurar que la carpeta del proyecto esté en el path
sys.path.insert(0, str(Path(__file__).parent))

from database import (
    init_db,
    get_facturas_ofb,
    get_sisor_entradas,
    get_oc_resumen_proveedor,
    get_historial_runs,
    registrar_run,
    get_stats_db,
    get_sisor_del_dia,
    get_oc_del_dia,
    get_actividad_semanal,
    _get_lunes_de_semana,
    _max_fecha_captura,
)
from comparator        import comparar
from exclusion_manager import cargar_exclusiones
from email_reporter    import generar_html, enviar_reporte, guardar_html

LOG_FILE = Path(__file__).parent / "data" / "reporte.log"
DESTINATARIO = os.getenv("GMAIL_USER", "luisdarool12@gmail.com")


def _log(msg: str) -> None:
    ts  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        LOG_FILE.parent.mkdir(exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def _solo_dia_habil() -> bool:
    """Retorna False solo si hoy es domingo (6). Sábado es laborable."""
    return date.today().weekday() <= 5


def main() -> int:
    _log("─" * 60)
    _log("Iniciando reporte diario Oak Footwear")

    if not _solo_dia_habil():
        _log("Hoy es fin de semana — reporte omitido.")
        return 0

    # 1. Init DB
    try:
        init_db()
        stats_db = get_stats_db()
        _log(f"DB OK  OFB={stats_db['n_ofb']}  SISOR={stats_db['n_sisor']}  OC={stats_db['n_oc_total']}")
    except Exception as e:
        _log(f"ERROR init_db: {e}")
        return 1

    # 2. Cargar datos
    try:
        df_ofb   = get_facturas_ofb()
        df_sisor = get_sisor_entradas()
        _log(f"Datos cargados  OFB={len(df_ofb)}  SISOR={len(df_sisor)}")
    except Exception as e:
        _log(f"ERROR cargando datos: {e}")
        return 1

    if df_ofb.empty:
        _log("Sin facturas OFB en la DB — reporte vacío no enviado.")
        return 0

    # 3. Comparar
    try:
        sisor_meta = {"formato": "db"}
        resultado  = comparar(df_ofb, df_sisor, sisor_meta)

        # Aplicar exclusiones
        exclusiones    = cargar_exclusiones()
        pendientes_raw = resultado["pendientes"]
        if not pendientes_raw.empty and "rfc_emisor" in pendientes_raw.columns and exclusiones:
            rfcs_excluidos = {k.upper() for k in exclusiones.keys()}
            mask           = pendientes_raw["rfc_emisor"].str.upper().isin(rfcs_excluidos)
            pendientes     = pendientes_raw[~mask].reset_index(drop=True)
        else:
            pendientes = pendientes_raw

        # Recalcular stats con pendientes filtrados
        stats = dict(resultado["resumen"])
        stats["pendientes"]      = len(pendientes)
        stats["monto_pendiente"] = (
            pendientes["total"].sum() if not pendientes.empty and "total" in pendientes.columns else 0.0
        )

        registrar_run(stats)
        _log(f"Comparación OK  pendientes={stats['pendientes']}  monto=${stats['monto_pendiente']:,.0f}")
    except Exception as e:
        _log(f"ERROR comparando: {e}\n{traceback.format_exc()}")
        return 1

    # 4. OC resumen
    try:
        df_oc_resumen = get_oc_resumen_proveedor()
        _log(f"OC resumen: {len(df_oc_resumen)} proveedores con pendiente")
    except Exception as e:
        _log(f"WARN get_oc_resumen: {e}")
        df_oc_resumen = None

    # 5. Delta vs corrida anterior
    historial_prev = None
    try:
        hist = get_historial_runs(n=2)
        if len(hist) >= 2:
            historial_prev = hist.iloc[-2].to_dict()
    except Exception:
        pass

    # 6. Actividad del día (usa MAX(fecha_captura) — el lunes muestra el sábado)
    df_sisor_ayer = None
    df_oc_ayer    = None
    df_semana     = None
    fecha_act     = None
    try:
        fecha_act     = _max_fecha_captura()
        df_sisor_ayer = get_sisor_del_dia(fecha_act)
        df_oc_ayer    = get_oc_del_dia(fecha_act)
        lunes         = _get_lunes_de_semana(date.today().isoformat())
        df_semana     = get_actividad_semanal(lunes)
        _log(f"Actividad: fecha={fecha_act}  sisor={len(df_sisor_ayer)}  oc={len(df_oc_ayer)}")
    except Exception as e:
        _log(f"WARN actividad: {e}")

    # 7. Generar HTML
    try:
        html = generar_html(
            pendientes, stats,
            df_oc_resumen=df_oc_resumen,
            historial_prev=historial_prev,
            df_sisor_ayer=df_sisor_ayer,
            df_oc_ayer=df_oc_ayer,
            df_semana=df_semana,
            fecha_actividad=fecha_act,
        )
        _log("HTML generado correctamente")
    except Exception as e:
        _log(f"ERROR generando HTML: {e}")
        return 1

    # 7b. Guardar HTML en disco
    try:
        ruta_html = guardar_html(html, Path(__file__).parent / "data" / "reportes")
        _log(f"HTML guardado en {ruta_html}")
    except Exception as e:
        _log(f"WARN guardando HTML: {e}")

    # 8. Enviar email
    try:
        destinatario = os.getenv("GMAIL_USER", DESTINATARIO)
        enviar_reporte(html, destinatario)
        _log(f"Email enviado a {destinatario}")
    except ValueError as e:
        _log(f"ERROR credenciales: {e}")
        _log("Ejecuta 'configurar_email.command' para configurar el email.")
        return 1
    except Exception as e:
        _log(f"ERROR enviando email: {e}\n{traceback.format_exc()}")
        return 1

    _log("Reporte diario completado exitosamente.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
