# Nutzerverwaltung wetterheidi.de — Betriebshandbuch

Zentrales Web-Tool zur Verwaltung aller htpasswd-Konten und Admin-Rechte
für die Anwendungen unter *.wetterheidi.de.

**URL: https://verwaltung.wetterheidi.de** — Zugriff nur für globale Administratoren.

---

## 1. Das System in 60 Sekunden

Es gibt zwei Ebenen, sauber getrennt:

| Ebene | Frage | Datei auf dem Server | Verwaltet über |
|---|---|---|---|
| **Authentifizierung** | Wer darf sich überhaupt einloggen? | `/etc/nginx/.htpasswd-wetterheidi` | Web-UI (verwaltung.wetterheidi.de) |
| **Autorisierung** | Wer darf welches Admin-Tool nutzen? | `/etc/wetterheidi/roles.json` | Web-UI; nur `global`-Liste per SSH |

- **Ein Konto pro Person**, gilt für alle Apps gleichzeitig (astro, epswx, flightclimate,
  idsse, mittelwind, mwsviewer, tlogpviewer, wxcalculator).
- **Admin-Tools sind standardmäßig für niemanden freigeschaltet.** Es gibt aktuell zwei:
  - *MWS Viewer – Geräte-Verwaltung* (mwsviewer.wetterheidi.de/admin)
  - *TLogP Viewer – Stations-Verwaltung* (tlogpviewer.wetterheidi.de/admin.html)
- **Globale Administratoren** (Liste `global` in roles.json) dürfen das Verwaltungstool
  nutzen und haben implizit Zugriff auf alle Admin-Tools. Sie sind über die UI weder
  löschbar noch veränderbar.
- Alle Änderungen wirken **sofort** — nirgends muss ein Dienst neu gestartet werden.

So sieht die `roles.json` aus:

```json
{
  "global": ["wetterheidi"],
  "tools": {
    "mwsviewer": ["olli"],
    "tlogp": []
  }
}
```

---

## 2. Alltagsaufgaben (alles über die Web-UI)

https://verwaltung.wetterheidi.de öffnen, mit dem eigenen Konto anmelden (muss in
`global` stehen).

### Neuen Nutzer anlegen
1. Oben Login-Name eintragen (Kleinbuchstaben, Ziffern, `. _ -`, 2–32 Zeichen)
2. Passwort eingeben oder per **🎲 Zufall** erzeugen lassen (dann notieren!)
3. **+ Anlegen** — die Person kann sich sofort bei allen Apps einloggen

### Passwort ändern
**🔑 Passwort** beim jeweiligen Nutzer → neues Passwort eingeben. Gilt sofort für alle Apps.

### Nutzer löschen
**✕ Löschen** → Rückfrage bestätigen. Der Zugang zu **allen** Apps erlischt sofort;
eventuelle Admin-Freischaltungen werden mit entfernt.
(Achtung: Bereits offene Browser-Sitzungen laufen weiter, bis der Browser geschlossen
wird — aber jede neue Anfrage wird abgewiesen.)

### Admin-Tool freischalten oder entziehen
Checkbox beim Nutzer setzen bzw. entfernen — wirkt sofort. Die Person nutzt dafür
ihr ganz normales Passwort, es gibt keine separaten Admin-Passwörter mehr.

### MWS-Geräte zuweisen (wer sieht welche Wetterstation?)
Das passiert nicht hier, sondern im MWS-Admin-Tool: **mwsviewer.wetterheidi.de/admin**
→ Nutzer hinzufügen → Geräte per Checkbox anhaken. Standard für Nutzer ohne Eintrag
ist dort umschaltbar („alle Geräte" / „keine").

---

## 3. Superuser (globale Admins) — nur per SSH

Bewusst nicht über die Web-UI möglich: Die höchste Rechtestufe wird nur dort vergeben,
wo ohnehin Vollzugriff besteht.

```bash
ssh root@178.104.206.136
nano /etc/wetterheidi/roles.json
# Name in die "global"-Liste eintragen oder daraus entfernen:
#   "global": ["wetterheidi", "neuername"],
```

Speichern — fertig, wirkt sofort. Das Konto selbst muss vorher ganz normal über die
Web-UI angelegt worden sein.

---

## 4. Wissenswertes zu Login und Browser

- Es ist HTTP Basic Auth: Der Browser merkt sich das Login bis er **komplett beendet**
  wird (Mac: Cmd+Q). Fenster schließen reicht nicht, einen Logout-Knopf gibt es nicht.
- **Nutzer wechseln ohne Neustart:** privates Fenster öffnen (eigener Login-Speicher).
  Praktisch zum Testen: normales Fenster = eigenes Admin-Konto, privates Fenster =
  Test-Nutzer, parallel.
- Rechte-Entzug wirkt trotzdem sofort, denn jede einzelne Anfrage wird serverseitig
  frisch geprüft — das gemerkte Login nützt ohne Eintrag in den Dateien nichts.

---

## 5. Wenn etwas schiefgeht

### Sicherungskopien der htpasswd-Datei
Vor jeder Änderung legt das Tool automatisch ein Backup an (die letzten 50 bleiben):

```bash
ssh root@178.104.206.136
ls /apps/user-admin/backups/                 # htpasswd-JJJJMMTT-HHMMSS
cp /apps/user-admin/backups/htpasswd-<stand> /etc/nginx/.htpasswd-wetterheidi
chown root:www-data /etc/nginx/.htpasswd-wetterheidi && chmod 664 /etc/nginx/.htpasswd-wetterheidi
```

### roles.json kaputt (z.B. Tippfehler beim Editieren)
Symptom: alle Admin-Tools melden „Zugriff verweigert" — bei defekter Datei wird
bewusst gesperrt statt freigegeben. Prüfen und reparieren:

```bash
python3 -m json.tool /etc/wetterheidi/roles.json   # zeigt die Fehlerstelle
```

### Notzugang
Als root per SSH geht immer alles direkt, ganz ohne Web-UI:

```bash
htpasswd /etc/nginx/.htpasswd-wetterheidi <name>      # Konto anlegen/Passwort setzen
htpasswd -D /etc/nginx/.htpasswd-wetterheidi <name>   # Konto löschen
nano /etc/wetterheidi/roles.json                      # Rechte direkt editieren
```

### Dienste prüfen und neu starten

```bash
systemctl status user-admin     # Nutzerverwaltung (Port 8090)
systemctl status mws-viewer     # MWS Viewer        (Port 8080, braucht ~20 s zum Starten)
systemctl status tlogp-api      # TLogP Admin-API   (Port 8765)
journalctl -u user-admin -f     # Live-Log
```

---

## 6. Wo liegt was

| Was | Wo |
|---|---|
| Dieses Tool (Code) | github.com/wetterheidi/user-admin → `/apps/user-admin` |
| Konten (htpasswd) | `/etc/nginx/.htpasswd-wetterheidi` |
| Rollen | `/etc/wetterheidi/roles.json` |
| htpasswd-Backups | `/apps/user-admin/backups/` |
| MWS-Geräterechte | `/apps/mws-viewer/mws_permissions.json` (UI: mwsviewer…/admin) |
| MWS Viewer (Code) | github.com/wetterheidi/mws-viewer → `/apps/mws-viewer` |
| TLogP Viewer (Code) | github.com/wetterheidi/sounding_data → `/apps/TLogPViewer/sounding_data` |

**Updates einspielen** (jeweils): `git -C <app-verzeichnis> pull && systemctl restart <dienst>`

⚠️ **nginx-Configs unter `/etc/nginx/sites-available/` nie mit den Vorlagen aus den
Repos überschreiben** — die Live-Dateien enthalten von certbot ergänzte SSL-Blöcke.
Änderungen dort immer per Editor in der Live-Datei nachziehen, danach
`nginx -t && systemctl reload nginx`.

---

## 7. Technik (für später / für Claude)

- nginx verlangt Basic Auth gegen die zentrale htpasswd-Datei und reicht den
  Login-Namen als Header `X-Remote-User` an die Apps durch (alle lauschen nur
  auf 127.0.0.1 und sind nie direkt erreichbar).
- Jede App prüft diesen Header selbst gegen `roles.json`:
  - user_admin.py → Liste `global`
  - mws_server.py → `global` + `tools.mwsviewer`
  - admin_api.py (tlogp) → `global` + `tools.tlogp`
- Passwörter laufen beim Anlegen/Ändern über stdin an das Programm `htpasswd` —
  sie erscheinen nie auf der Kommandozeile oder in Logs.
- Neues Zertifikat für eine passwortgeschützte Subdomain: der certbot-nginx-Modus
  scheitert an der Basic Auth. Stattdessen hat der vhost eine Ausnahme
  (`location /.well-known/acme-challenge/` mit `auth_basic off`), Ausstellung per
  `certbot certonly --webroot -w /var/www/html -d <domain>`, dann
  `certbot install --nginx --cert-name <domain> --redirect`.
- Historie: aufgebaut am 10./11.06.2026; das frühere geteilte Konto „admin" und
  die separate Datei `.htpasswd-tlogp` sind seitdem obsolet.
