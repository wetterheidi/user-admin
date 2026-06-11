# Nutzerverwaltung wetterheidi.de

Zentrales Web-Tool zur Verwaltung der htpasswd-Konten und Admin-Tool-Freischaltungen
für alle Anwendungen unter *.wetterheidi.de.

**URL:** https://verwaltung.wetterheidi.de — Zugriff nur für globale Administratoren.

## Konzept

| Ebene | Datei | Inhalt |
|---|---|---|
| **Authentifizierung** | `/etc/nginx/.htpasswd-wetterheidi` | ein Konto pro Person, gilt für alle Apps |
| **Autorisierung** | `/etc/wetterheidi/roles.json` | wer ist globaler Admin, wer darf welches Admin-Tool nutzen |

```json
{
  "global": ["wetterheidi"],
  "tools": {
    "mwsviewer": ["olli"],
    "tlogp": []
  }
}
```

- `global`: dürfen dieses Tool nutzen und haben implizit Zugriff auf alle Admin-Tools.
  Über die UI weder löschbar noch änderbar — nur per Datei auf dem Server.
- `tools.<name>`: pro Admin-Tool die freigeschalteten Nutzer. **Standard: niemand.**

Die einzelnen Apps (mws-viewer, sounding_data/tlogp) prüfen die Rollen-Datei
selbst; Änderungen wirken sofort, ohne Neustart irgendeines Dienstes.

## Funktionen

- Konto anlegen (mit Zufallspasswort-Generator), Passwort ändern, Konto löschen
- Vor jeder Änderung an der htpasswd-Datei wird automatisch eine Sicherungskopie
  in `backups/` abgelegt (die letzten 50 bleiben erhalten)
- Admin-Tools pro Nutzer per Checkbox freischalten/entziehen (sofort wirksam)
- Globale Administratoren sind vor Löschung geschützt

## Deployment

```bash
# Einmalig als root auf dem Server:
bash <(curl -fsSL https://raw.githubusercontent.com/wetterheidi/user-admin/main/deploy/setup-server.sh)
```

Updates: `git -C /apps/user-admin pull && systemctl restart user-admin`

## Sicherheit

- nginx verlangt Basic Auth (zentrale htpasswd-Datei) und reicht den Login-Namen
  als `X-Remote-User` an die App durch; die App lauscht nur auf 127.0.0.1.
- Die App prüft zusätzlich, ob der Login in `roles.json → global` steht.
- Passwörter laufen beim Anlegen/Ändern über stdin an `htpasswd` — sie erscheinen
  nie auf der Kommandozeile oder in Logs.
