#!/usr/bin/env python3
"""
Zentrale Nutzerverwaltung für *.wetterheidi.de

- verwaltet Konten in der zentralen htpasswd-Datei (anlegen, Passwort ändern, löschen)
- verwaltet Admin-Tool-Freischaltungen in der zentralen Rollen-Datei (roles.json)
- Zugriff nur für globale Administratoren (roles.json → "global")

Authentifizierung übernimmt nginx per Basic Auth; der Login-Name kommt als
X-Remote-User-Header. Die App lauscht nur auf 127.0.0.1 hinter nginx und ist
nie direkt von außen erreichbar.
"""

import json
import os
import re
import shutil
import subprocess
import threading
import time

from flask import Flask, Response, jsonify, request, send_from_directory

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
ROLES_FILE    = os.environ.get('ROLES_FILE',    '/etc/wetterheidi/roles.json')
HTPASSWD_FILE = os.environ.get('HTPASSWD_FILE', '/etc/nginx/.htpasswd-wetterheidi')
HTPASSWD_BIN  = os.environ.get('HTPASSWD_BIN',  'htpasswd')
BACKUP_DIR    = os.path.join(BASE_DIR, 'backups')
MAX_BACKUPS   = 50

# Bekannte Admin-Tools: Schlüssel = Eintrag in roles.json, Wert = Anzeigename
TOOLS = {
    'mwsviewer': 'MWS Viewer – Geräte-Verwaltung',
    'tlogp':     'TLogP Viewer – Stations-Verwaltung',
}

USERNAME_RE = re.compile(r'^[a-z0-9][a-z0-9._-]{1,31}$')
MIN_PW_LEN  = 8

app   = Flask(__name__)
_lock = threading.Lock()


# ── Rollen-Datei ───────────────────────────────────────────────────────────────

def _load_roles() -> dict:
    try:
        with open(ROLES_FILE, encoding='utf-8') as fh:
            roles = json.load(fh)
    except FileNotFoundError:
        roles = {}
    roles.setdefault('global', [])
    roles.setdefault('tools', {})
    for tool in TOOLS:
        roles['tools'].setdefault(tool, [])
    return roles


def _save_roles(roles: dict):
    tmp = ROLES_FILE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(roles, fh, ensure_ascii=False, indent=2)
        fh.write('\n')
    os.replace(tmp, ROLES_FILE)


def _current_user() -> str:
    return request.headers.get('X-Remote-User', '').strip().lower()


def _is_global() -> bool:
    user = _current_user()
    return bool(user) and user in {u.lower() for u in _load_roles()['global']}


# ── htpasswd ──────────────────────────────────────────────────────────────────

def _htpasswd_users() -> list:
    try:
        with open(HTPASSWD_FILE, encoding='utf-8') as fh:
            return sorted({ln.split(':', 1)[0].strip().lower()
                           for ln in fh if ':' in ln})
    except FileNotFoundError:
        return []


def _backup_htpasswd():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = time.strftime('%Y%m%d-%H%M%S')
    shutil.copy2(HTPASSWD_FILE, os.path.join(BACKUP_DIR, f'htpasswd-{stamp}'))
    backups = sorted(os.listdir(BACKUP_DIR))
    for old in backups[:-MAX_BACKUPS]:
        os.remove(os.path.join(BACKUP_DIR, old))


def _run_htpasswd(args, password=None):
    """htpasswd aufrufen; Passwort geht über stdin, nie über die Kommandozeile."""
    r = subprocess.run([HTPASSWD_BIN, *args], input=password,
                       capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or f'htpasswd exit {r.returncode}')


# ── Routen ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if not _is_global():
        return Response('Zugriff nur für globale Administratoren.', status=403,
                        mimetype='text/plain; charset=utf-8')
    return send_from_directory(BASE_DIR, 'verwaltung.html')


@app.route('/api/state')
def api_state():
    if not _is_global():
        return jsonify({'error': 'Zugriff nur für globale Administratoren'}), 403
    roles = _load_roles()
    glob  = {u.lower() for u in roles['global']}
    users = []
    for name in _htpasswd_users():
        users.append({
            'name':   name,
            'global': name in glob,
            'tools':  [t for t in TOOLS
                       if name in {u.lower() for u in roles['tools'][t]}],
        })
    return jsonify({'me': _current_user(), 'tools': TOOLS, 'users': users})


@app.route('/api/users', methods=['POST'])
def api_user_create():
    if not _is_global():
        return jsonify({'error': 'Zugriff nur für globale Administratoren'}), 403
    body = request.get_json(force=True) or {}
    name = str(body.get('name', '')).strip().lower()
    pw   = str(body.get('password', ''))
    if not USERNAME_RE.match(name):
        return jsonify({'error': 'Ungültiger Name (2–32 Zeichen, nur a-z 0-9 . _ -)'}), 400
    if len(pw) < MIN_PW_LEN:
        return jsonify({'error': f'Passwort braucht mindestens {MIN_PW_LEN} Zeichen'}), 400
    with _lock:
        if name in _htpasswd_users():
            return jsonify({'error': f'Nutzer {name} existiert bereits'}), 409
        _backup_htpasswd()
        _run_htpasswd(['-i', HTPASSWD_FILE, name], password=pw)
    print(f'[USERS] {_current_user()!r} hat Nutzer {name!r} angelegt')
    return jsonify({'ok': True})


@app.route('/api/users/<name>/password', methods=['POST'])
def api_user_password(name):
    if not _is_global():
        return jsonify({'error': 'Zugriff nur für globale Administratoren'}), 403
    name = name.strip().lower()
    pw   = str((request.get_json(force=True) or {}).get('password', ''))
    if len(pw) < MIN_PW_LEN:
        return jsonify({'error': f'Passwort braucht mindestens {MIN_PW_LEN} Zeichen'}), 400
    with _lock:
        if name not in _htpasswd_users():
            return jsonify({'error': f'Nutzer {name} nicht gefunden'}), 404
        _backup_htpasswd()
        _run_htpasswd(['-i', HTPASSWD_FILE, name], password=pw)
    print(f'[USERS] {_current_user()!r} hat Passwort von {name!r} geändert')
    return jsonify({'ok': True})


@app.route('/api/users/<name>', methods=['DELETE'])
def api_user_delete(name):
    if not _is_global():
        return jsonify({'error': 'Zugriff nur für globale Administratoren'}), 403
    name  = name.strip().lower()
    roles = _load_roles()
    if name in {u.lower() for u in roles['global']}:
        return jsonify({'error': 'Globale Administratoren können nicht über die '
                                 'UI gelöscht werden'}), 403
    with _lock:
        if name not in _htpasswd_users():
            return jsonify({'error': f'Nutzer {name} nicht gefunden'}), 404
        _backup_htpasswd()
        _run_htpasswd(['-D', HTPASSWD_FILE, name])
        # Freischaltungen mit entfernen
        for tool in TOOLS:
            roles['tools'][tool] = [u for u in roles['tools'][tool]
                                    if u.lower() != name]
        _save_roles(roles)
    print(f'[USERS] {_current_user()!r} hat Nutzer {name!r} gelöscht')
    return jsonify({'ok': True})


@app.route('/api/users/<name>/tools', methods=['PUT'])
def api_user_tools(name):
    if not _is_global():
        return jsonify({'error': 'Zugriff nur für globale Administratoren'}), 403
    name  = name.strip().lower()
    tools = (request.get_json(force=True) or {}).get('tools', [])
    if not isinstance(tools, list) or any(t not in TOOLS for t in tools):
        return jsonify({'error': 'Unbekanntes Tool'}), 400
    with _lock:
        if name not in _htpasswd_users():
            return jsonify({'error': f'Nutzer {name} nicht gefunden'}), 404
        roles = _load_roles()
        for tool in TOOLS:
            entries = [u for u in roles['tools'][tool] if u.lower() != name]
            if tool in tools:
                entries.append(name)
            roles['tools'][tool] = entries
        _save_roles(roles)
    print(f'[USERS] {_current_user()!r} hat Freischaltungen von {name!r} '
          f'gesetzt: {tools}')
    return jsonify({'ok': True})


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Zentrale Nutzerverwaltung')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8090)
    args = parser.parse_args()
    print(f'Nutzerverwaltung läuft auf http://{args.host}:{args.port}')
    app.run(host=args.host, port=args.port, debug=False, threaded=True)
