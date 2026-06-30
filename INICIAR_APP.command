#!/bin/bash
# Script de inicio — doble clic para abrir la app

cd "$(dirname "$0")"

echo "================================================"
echo "  Control de Facturas — Oak Footwear"
echo "================================================"
echo ""

# Buscar streamlit en rutas comunes
STREAMLIT=""
for path in \
    "$HOME/Library/Python/3.9/bin/streamlit" \
    "$HOME/Library/Python/3.10/bin/streamlit" \
    "$HOME/Library/Python/3.11/bin/streamlit" \
    "/usr/local/bin/streamlit" \
    "/opt/homebrew/bin/streamlit" \
    "$(python3 -m site --user-base)/bin/streamlit"
do
    if [ -f "$path" ]; then
        STREAMLIT="$path"
        break
    fi
done

if [ -z "$STREAMLIT" ]; then
    echo "❌ No se encontró streamlit. Instalando..."
    pip3 install -r requirements.txt
    STREAMLIT="$(python3 -m site --user-base)/bin/streamlit"
fi

echo "✅ Abriendo la app en el navegador..."
echo "   Para cerrar: presiona Ctrl+C aquí"
echo ""

"$STREAMLIT" run app.py --server.headless false
