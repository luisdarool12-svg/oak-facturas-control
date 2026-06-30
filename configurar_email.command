#!/bin/bash
# configurar_email.command
# Doble clic en este archivo para configurar el reporte diario por email.
# ─────────────────────────────────────────────────────────────────────────────

# Ir a la carpeta del script
cd "$(dirname "$0")"

clear
echo "=================================================="
echo "  Oak Footwear — Configurar reporte diario email  "
echo "=================================================="
echo ""
echo "Este script hace 3 cosas:"
echo "  1. Guarda tu App Password de Gmail"
echo "  2. Instala el reporte automático (8:00am L-V)"
echo "  3. Manda un email de prueba"
echo ""
echo "──────────────────────────────────────────────────"
echo "PASO 1: Necesitas un App Password de Google"
echo "──────────────────────────────────────────────────"
echo ""
echo "  a) Abre esta URL en tu navegador:"
echo "     https://myaccount.google.com/apppasswords"
echo ""
echo "  b) Si pide que inicies sesión, hazlo con:"
echo "     luisdarool12@gmail.com"
echo ""
echo "  c) En 'Nombre de la app' escribe: OakFootwear"
echo ""
echo "  d) Haz clic en 'Crear' — Google te mostrará"
echo "     un código de 16 letras como:"
echo "     xxxx xxxx xxxx xxxx"
echo ""
echo "  e) Copia ese código y pégalo aquí."
echo ""
open "https://myaccount.google.com/apppasswords" 2>/dev/null || true
echo ""

# Pedir el App Password
while true; do
    read -rp "Pega el App Password aquí (16 letras con o sin espacios): " APP_PASS
    APP_PASS="${APP_PASS// /}"   # quitar espacios
    if [ "${#APP_PASS}" -eq 16 ]; then
        break
    fi
    echo "  ⚠️  El código debe tener exactamente 16 caracteres. Intenta de nuevo."
done

# Guardar en .env
ENV_FILE=".env"
cat > "$ENV_FILE" <<EOF
GMAIL_USER=luisdarool12@gmail.com
GMAIL_APP_PASSWORD=$APP_PASS
EOF

echo ""
echo "✅ Credenciales guardadas en .env"
echo ""

# ── Instalar LaunchAgent ──────────────────────────────────────────────────────
echo "──────────────────────────────────────────────────"
echo "PASO 2: Instalando reporte automático (8:00am)"
echo "──────────────────────────────────────────────────"
echo ""

PLIST_SRC="$(pwd)/launchd/com.oakfootwear.reporte.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.oakfootwear.reporte.plist"

# Desinstalar si ya existe
if launchctl list | grep -q "com.oakfootwear.reporte" 2>/dev/null; then
    launchctl unload "$PLIST_DST" 2>/dev/null || true
fi

cp "$PLIST_SRC" "$PLIST_DST"
chmod 644 "$PLIST_DST"
launchctl load "$PLIST_DST"

echo "✅ Reporte automático instalado para las 8:00am (lunes a viernes)"
echo ""

# ── Email de prueba ───────────────────────────────────────────────────────────
echo "──────────────────────────────────────────────────"
echo "PASO 3: Enviando email de prueba..."
echo "──────────────────────────────────────────────────"
echo ""

PYTHON3="$HOME/Library/Python/3.9/bin/python3"
if [ ! -f "$PYTHON3" ]; then
    PYTHON3=$(which python3)
fi

"$PYTHON3" reporte_diario.py
EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "══════════════════════════════════════════════════"
    echo "  ✅ ¡Todo listo!"
    echo "     Recibirás el reporte a las 8:00am L-V"
    echo "     en luisdarool12@gmail.com"
    echo "══════════════════════════════════════════════════"
else
    echo "══════════════════════════════════════════════════"
    echo "  ⚠️  El email de prueba no se pudo enviar."
    echo "     Revisa que el App Password sea correcto"
    echo "     y que Gmail tenga 2FA activado."
    echo ""
    echo "  El App Password se puede regenerar en:"
    echo "  https://myaccount.google.com/apppasswords"
    echo "══════════════════════════════════════════════════"
fi

echo ""
echo "Presiona Enter para cerrar..."
read -r
