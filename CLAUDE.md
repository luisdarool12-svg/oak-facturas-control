# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Cómo iniciar la app

```bash
# Desde la carpeta facturas-control/
/Users/luisdarool12/Library/Python/3.9/bin/streamlit run app.py
```

O doble clic en `INICIAR_APP.command` desde el Finder.

## Instalar dependencias (primera vez)

```bash
pip3 install -r requirements.txt
```

## Verificar módulos sin levantar Streamlit

```bash
python3 -c "from parsers.ofb_parser import parse_ofb; from parsers.sisor_parser import parse_sisor; from comparator import comparar; print('OK')"
```

---

## Arquitectura

### Flujo de datos

```
OFB Excel (contador)          SISOR Excel (Luis)
        ↓                              ↓
  parsers/ofb_parser.py     parsers/sisor_parser.py
        ↓                              ↓
              comparator.py
                    ↓
         exclusion_manager.py  ←  exclusiones.json
                    ↓
              app.py (Streamlit UI)
                    ↓
              exporter.py  →  Excel de reporte
```

### Módulos clave

**`parsers/ofb_parser.py`** — Lee el Excel OFB del contador (`OFB211130F78_Recibidas-*.xlsx`). Filtra solo `TipoComprobante = "I - Ingreso"`. Produce columnas: `uuid`, `rfc_emisor`, `proveedor`, `total`, `moneda`, `folio`, `folio_num`, `fecha`.

**`parsers/sisor_parser.py`** — Lee el Excel de SISOR (`FACTURAS DD-MM-YYYY.XLS`). Detecta dos formatos: `sisor_standard` (con encabezado "RESUMEN DE FACTURAS CAPTURADAS", datos a partir de la fila ~12) y `generico` (tabla con encabezado en fila 0-3). En el formato estándar, las columnas por posición son: col 0=fecha_captura, col 1=proveedor, col 5=factura, col 7=importe, col 9=fecha_factura. Limpia sufijos SISOR como `(2026)` del nombre de proveedor.

**`comparator.py`** — Anti-join en dos estrategias (elegidas automáticamente):
1. **UUID exacto** — si SISOR exporta columna UUID (campo len > 30)
2. **Folio + Monto ±2%** — estrategia actual con el SISOR real (sin UUID). Fallback: primera palabra del nombre + monto ±2% + fecha ±7 días.

**`exclusion_manager.py`** — Lee/escribe `exclusiones.json` ({RFC: nombre}). Si el archivo no existe, lo crea con 10 proveedores default (bancos, IMSS, INFONAVIT, servicios, arrendamiento, consultoría). El filtro se aplica en `app.py` **después** de `comparar()`, no dentro del comparador.

**`exporter.py`** — Genera Excel con xlsxwriter con 3 hojas: "Facturas Pendientes", "Ya en SISOR", "Resumen Ejecutivo". Formatos de columna pre-configurados por nombre de encabezado.

**`app.py`** — UI Streamlit con 6 tabs: Pendientes / Ya en SISOR / Por proveedor / Vista SISOR / Exportar / ⚙️ Exclusiones. El tab de Exclusiones permite marcar proveedores y guarda en `exclusiones.json` con `guardar_exclusiones()`.

---

## Archivos de datos (no código)

| Archivo | Descripción |
|---------|-------------|
| `exclusiones.json` | RFCs excluidos persistentes — editado desde el tab ⚙️ Exclusiones |
| `OFB211130F78_Recibidas-05_2026-Facturas.xlsx` | Excel del contador (mayo 2026) — **no en este directorio**, está un nivel arriba en `WF CONCILIACION DE CUENTAS/` |
| `FACTURAS 25-05-2026.XLS` | Export de SISOR — también un nivel arriba |

---

## Decisiones de diseño importantes

- **Python 3.9** — usar `Optional[X]` y `List[X]` de `typing` en vez de `X | None` y `list[X]` (sintaxis 3.10+).
- El comparador **no filtra exclusiones** — solo hace el match OFB vs SISOR. La exclusión ocurre en `app.py` sobre `resultado["pendientes"]`.
- El SISOR estándar no exporta UUID. Si en el futuro SISOR agrega UUID, `comparator.py` lo detecta automáticamente (`tiene_uuid_sisor`) y cambia de estrategia sin intervención.
- `xlrd` se usa para `.xls` (SISOR), `openpyxl` para `.xlsx` (OFB y exportes).
