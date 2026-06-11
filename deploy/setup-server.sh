#!/bin/bash
# Nutzerverwaltung – Server-Ersteinrichtung
# Aufruf: sudo bash deploy/setup-server.sh
set -e

APP_DIR=/apps/user-admin
REPO=https://github.com/wetterheidi/user-admin.git
DOMAIN=verwaltung.wetterheidi.de
NGINX_CONF=/etc/nginx/sites-available/$DOMAIN
ROLES_DIR=/etc/wetterheidi
HTPASSWD=/etc/nginx/.htpasswd-wetterheidi

echo "=== Nutzerverwaltung Setup ==="

# 1. Repo klonen oder aktualisieren
if [ -d "$APP_DIR/.git" ]; then
    git -C "$APP_DIR" pull
else
    git clone "$REPO" "$APP_DIR"
fi
chown -R www-data:www-data "$APP_DIR"

# 2. Python venv
cd "$APP_DIR"
python3 -m venv venv
venv/bin/pip install --quiet --upgrade pip
venv/bin/pip install --quiet -r requirements.txt

# 3. Zentrale Rollen-Datei anlegen wenn nicht vorhanden
mkdir -p "$ROLES_DIR"
if [ ! -f "$ROLES_DIR/roles.json" ]; then
    cp "$APP_DIR/roles.json.template" "$ROLES_DIR/roles.json"
fi
chown -R www-data:www-data "$ROLES_DIR"
chmod 664 "$ROLES_DIR/roles.json"

# 4. htpasswd-Datei für die App beschreibbar machen (nginx liest weiterhin)
chown root:www-data "$HTPASSWD"
chmod 664 "$HTPASSWD"

# 5. nginx konfigurieren (nur beim ersten Mal — überschreibt keine certbot-Config!)
if [ ! -f "$NGINX_CONF" ]; then
    cp "$APP_DIR/deploy/nginx-verwaltung.conf" "$NGINX_CONF"
    ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/$DOMAIN
    nginx -t && systemctl reload nginx
    certbot --nginx --redirect --non-interactive -d "$DOMAIN"
else
    echo "nginx-Config existiert bereits – nicht überschrieben (certbot-Zeilen!)."
fi

# 6. systemd-Dienst
cp "$APP_DIR/deploy/user-admin.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable user-admin
systemctl restart user-admin

echo ""
echo "=== Setup abgeschlossen ==="
echo "Tool:   https://$DOMAIN"
echo "Rollen: $ROLES_DIR/roles.json (globale Admins dort eintragen)"
