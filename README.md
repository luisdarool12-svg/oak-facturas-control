# Control de Facturas de Proveedores — Oak Footwear

Compara automáticamente los CFDIs timbrados en el SAT contra las facturas ingresadas en SISOR para identificar cuáles faltan por registrar.

---

## Requisitos

- macOS con Python 3.10 o superior instalado
- Conexión a internet solo para la instalación inicial de dependencias

Verificar versión de Python:
```bash
python3 --version
```

---

## Instalación (primera vez)

Abrir Terminal, navegar a esta carpeta y ejecutar:

```bash
cd "/Users/luisdarool12/Documents/OAK FOOTWEAR /WORK FLOWS /WF CONCILIACION DE CUENTAS /facturas-control"
pip3 install -r requirements.txt
```

---

## Iniciar la app

```bash
streamlit run app.py
```

Se abrirá automáticamente el navegador en `http://localhost:8501`

Para cerrar: presionar `Ctrl + C` en la Terminal.

---

## Cómo usar

### Paso 1 — Obtener los XMLs del SAT (via el contador)

Pedirle al contador que haga lo siguiente:

1. Entrar a `sat.gob.mx` → iniciar sesión con e.firma o contraseña
2. Ir a **Facturación** → **Consultar facturas recibidas**
3. Seleccionar el RFC de Oak Footwear como receptor
4. Elegir el período (mes o rango de fechas)
5. Descargar los **XMLs** (no PDFs) — el SAT los entrega en un ZIP
6. Enviar el ZIP a Luis

### Paso 2 — Exportar facturas de SISOR

1. Entrar a SISOR
2. Ir al módulo de Facturas / Cuentas por Pagar
3. Seleccionar el mismo período
4. Exportar a Excel (.xlsx)
5. Guardar el archivo

### Paso 3 — Comparar en la app

1. Abrir la Terminal y ejecutar `streamlit run app.py`
2. En el panel izquierdo, subir el **ZIP del SAT**
3. Subir el **Excel de SISOR**
4. Clic en **"Comparar facturas"**
5. Revisar el tab **"Pendientes"** — esas son las facturas que faltan ingresar

### Paso 4 — Exportar reporte

1. Ir al tab **"Exportar"**
2. Clic en **"Generar Excel"**
3. Descargar el archivo
4. Compartir con el contador o supervisor si se requiere

---

## Cómo funciona la comparación

### Modo UUID (exacto — recomendado)

Si el Excel de SISOR tiene una columna de UUID / Folio Fiscal, la app hace un **anti-join exacto**: todas las facturas del SAT cuyo UUID no aparece en SISOR quedan marcadas como pendientes.

### Modo fuzzy (aproximado)

Si SISOR no exporta el UUID, la app compara por:
- RFC del emisor (igual)
- Monto total (diferencia ≤ 1%)
- Fecha de emisión (diferencia ≤ 5 días)

Este modo puede tener falsos positivos si un mismo proveedor emite facturas similares.

**Recomendación:** solicitar al área de sistemas que SISOR exporte el campo UUID en su reporte de Excel para usar el modo exacto.

---

## Columnas que detecta en el Excel de SISOR

La app intenta detectar automáticamente las columnas. Si el Excel tiene nombres distintos, se puede ver en el tab "Exportar" → "Columnas detectadas en SISOR" qué columnas encontró.

Nombres reconocidos automáticamente:
- UUID: `uuid`, `folio fiscal`, `folio_fiscal`, `timbre`
- RFC: `rfc`, `rfc emisor`, `rfc proveedor`
- Proveedor: `proveedor`, `nombre`, `razon social`
- Monto: `total`, `importe`, `monto`
- Fecha: `fecha`, `fecha factura`, `fecha emision`

---

## Estructura del proyecto

```
facturas-control/
├── app.py              # App principal
├── comparator.py       # Lógica de comparación
├── exporter.py         # Generación de reporte Excel
├── requirements.txt    # Dependencias Python
├── parsers/
│   ├── cfdi_parser.py  # Lectura de XMLs del SAT
│   └── sisor_parser.py # Lectura del Excel de SISOR
└── README.md
```

---

## Solución de problemas

**Error: "command not found: streamlit"**
```bash
pip3 install streamlit
```

**Error al leer el ZIP del SAT**
- Verificar que el ZIP contiene archivos `.xml`, no `.pdf`
- Algunos SAT entregan un ZIP dentro de un ZIP — descomprimir el exterior primero

**La columna UUID no se detecta en SISOR**
- Revisar el nombre exacto de la columna en el Excel
- La comparación fuzzy sigue funcionando como alternativa

**La app no abre el navegador**
- Abrir manualmente: `http://localhost:8501`
