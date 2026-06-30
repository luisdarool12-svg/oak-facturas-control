"""
Parser de CFDIs (XMLs del SAT).
Soporta CFDI 3.3 y 4.0. Lee un ZIP con múltiples XMLs o XMLs sueltos.
"""
import zipfile
import io
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional, List
import pandas as pd

# Namespaces del SAT
NS = {
    "cfdi33": "http://www.sat.gob.mx/cfd/3",
    "cfdi40": "http://www.sat.gob.mx/cfd/4",
    "tfd":    "http://www.sat.gob.mx/TimbreFiscalDigital",
}

def _get_ns(root_tag: str) -> str:
    if "cfd/4" in root_tag:
        return "cfdi40"
    return "cfdi33"


def _parse_xml(content: bytes) -> Optional[dict]:
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return None

    ns_key = _get_ns(root.tag)
    ns = NS[ns_key]

    # Datos del comprobante
    total_str = root.get("Total", "0").replace(",", "")
    fecha_str = root.get("Fecha", "")
    moneda    = root.get("Moneda", "MXN")
    serie     = root.get("Serie", "")
    folio     = root.get("Folio", "")
    tipo      = root.get("TipoDeComprobante", "")

    # Solo procesar facturas de egreso (I = Ingreso desde perspectiva del emisor → gasto para receptor)
    # TipoDeComprobante I = Ingreso (factura de compra para Oak)
    # Tomamos todas excepto notas de crédito (E) para no confundir
    if tipo == "E":
        return None  # notas de crédito se ignoran aquí

    # Emisor
    emisor = root.find(f"{{{ns}}}Emisor")
    rfc_emisor    = emisor.get("Rfc", "")    if emisor is not None else ""
    nombre_emisor = emisor.get("Nombre", "") if emisor is not None else ""

    # Receptor (confirmar que somos el receptor)
    receptor = root.find(f"{{{ns}}}Receptor")
    rfc_receptor = receptor.get("Rfc", "") if receptor is not None else ""

    # UUID desde TimbreFiscalDigital
    uuid = ""
    complemento = root.find(f"{{{ns}}}Complemento")
    if complemento is not None:
        tfd = complemento.find(f"{{{NS['tfd']}}}TimbreFiscalDigital")
        if tfd is not None:
            uuid = tfd.get("UUID", "").upper()

    if not uuid:
        return None  # sin UUID no podemos comparar

    # Convertir fecha
    try:
        fecha = datetime.strptime(fecha_str[:19], "%Y-%m-%dT%H:%M:%S").date()
    except ValueError:
        fecha = None

    try:
        total = float(total_str)
    except ValueError:
        total = 0.0

    folio_completo = f"{serie}{folio}".strip() or "—"

    return {
        "uuid":          uuid,
        "rfc_emisor":    rfc_emisor.upper(),
        "proveedor":     nombre_emisor.upper(),
        "rfc_receptor":  rfc_receptor.upper(),
        "fecha":         fecha,
        "total":         total,
        "moneda":        moneda,
        "folio":         folio_completo,
        "tipo":          tipo,
    }


def parse_zip(file_bytes: bytes) -> pd.DataFrame:
    """Lee un ZIP que contiene XMLs de CFDIs. Retorna DataFrame."""
    records = []
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
            for name in zf.namelist():
                if not name.lower().endswith(".xml"):
                    continue
                with zf.open(name) as f:
                    content = f.read()
                rec = _parse_xml(content)
                if rec:
                    records.append(rec)
    except zipfile.BadZipFile:
        # Tal vez es un XML directo, no un ZIP
        rec = _parse_xml(file_bytes)
        if rec:
            records.append(rec)

    if not records:
        return pd.DataFrame(columns=["uuid", "rfc_emisor", "proveedor", "rfc_receptor",
                                     "fecha", "total", "moneda", "folio", "tipo"])

    df = pd.DataFrame(records)
    df["fecha"] = pd.to_datetime(df["fecha"])
    df = df.sort_values("fecha", ascending=False).reset_index(drop=True)
    return df


def parse_xml_files(uploaded_files) -> pd.DataFrame:
    """Acepta lista de archivos subidos en Streamlit (XMLs sueltos o ZIP)."""
    records = []
    for f in uploaded_files:
        content = f.read()
        if f.name.lower().endswith(".zip"):
            df_zip = parse_zip(content)
            records.extend(df_zip.to_dict("records"))
        elif f.name.lower().endswith(".xml"):
            rec = _parse_xml(content)
            if rec:
                records.append(rec)

    if not records:
        return pd.DataFrame(columns=["uuid", "rfc_emisor", "proveedor", "rfc_receptor",
                                     "fecha", "total", "moneda", "folio", "tipo"])

    df = pd.DataFrame(records)
    df["fecha"] = pd.to_datetime(df["fecha"])
    return df.sort_values("fecha", ascending=False).reset_index(drop=True)
