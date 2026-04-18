# snipeit-bridge

Python/Flask-Anwendung zur Synchronisation von Assets und Benutzern aus verschiedenen Quellen nach [Snipe-IT](https://snipeitapp.com/) 8.4.

## Funktionen

| Quelle | Was wird synchronisiert |
|---|---|
| **Microsoft Intune** | Geräte (Assets) + aktive Benutzer (ohne Login-Rechte) |
| **Unifi Site Manager** | Netzwerkgeräte (Switches, APs, Gateways) |
| **Proxmox 9.1** | Cluster-Knoten, VMs (QEMU), Container (LXC) |
| **Zammad 7.0** | Ticket-Links → Snipe-IT Assets; Asset-Suche für Zammad External Data Source |

Syncs werden manuell über das Dashboard oder per Cronjob ausgelöst. Keine Hintergrund-Threads, kein Celery.

---

## Voraussetzungen

- Python 3.11+
- Snipe-IT 8.4 mit API-Token
- Für Intune: App-Registrierung in Microsoft Entra ID
- Für Proxmox: API-Token in PVE angelegt
- Für Unifi: API-Key im Unifi Site Manager

---

## Installation

```bash
git clone https://github.com/christian-roeser/snipeit-bridge.git
cd snipeit-bridge

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# .env mit eigenen Werten befüllen

# Entwicklung
flask run --host=0.0.0.0 --port=5000

# Produktion
gunicorn -b 0.0.0.0:5000 app:app
```

Das Dashboard ist erreichbar unter `http://<server-ip>:5000`.

---

## Konfiguration (.env)

```env
# Snipe-IT
SNIPEIT_URL=https://snipeit.example.com
SNIPEIT_TOKEN=your-api-token

# Microsoft Intune (Graph API)
INTUNE_TENANT_ID=your-tenant-id
INTUNE_CLIENT_ID=your-client-id
INTUNE_CLIENT_SECRET=your-client-secret

# Unifi Site Manager
UNIFI_URL=https://api.ui.com
UNIFI_API_KEY=your-api-key
UNIFI_SITES=ALL          # oder kommagetrennte Site-IDs: site1,site2

# Proxmox
PROXMOX_URL=https://proxmox.example.com:8006
PROXMOX_TOKEN_ID=user@pam!tokenname
PROXMOX_TOKEN_SECRET=your-token-secret
PROXMOX_VERIFY_SSL=true

# Zammad
ZAMMAD_URL=https://zammad.example.com
ZAMMAD_TOKEN=your-api-token

# Dashboard
DASHBOARD_USER=admin
DASHBOARD_PASSWORD=your-strong-password
SECRET_KEY=change-this-to-a-long-random-string
SESSION_COOKIE_SECURE=true
TRUST_PROXY=false
RATELIMIT_STORAGE_URI=memory://
LOGIN_RATE_LIMIT=10 per minute
SYNC_RATE_LIMIT=5 per minute
ASSET_API_RATE_LIMIT=30 per minute
ASSET_API_MAX_SEARCH_LENGTH=100
ZAMMAD_NOTES_MAX_LENGTH=4000
```

Für Produktion hinter HTTPS-Reverse-Proxy (z. B. Nginx/Traefik):
- `SESSION_COOKIE_SECURE=true`
- `TRUST_PROXY=true`
- Bei mehreren App-Workern `RATELIMIT_STORAGE_URI` auf ein gemeinsames Backend setzen (z. B. Redis).

Beispiel Redis für Rate Limits (mehrere Worker):

```env
RATELIMIT_STORAGE_URI=redis://127.0.0.1:6379/0
```

Beispiel Redis mit Passwort:

```env
RATELIMIT_STORAGE_URI=redis://:strong-redis-password@127.0.0.1:6379/0
```

Beispiel docker-compose (nur Redis):

```yaml
services:
  redis:
    image: redis:7-alpine
    restart: unless-stopped
    ports:
      - "6379:6379"
```

Beispiel docker-compose (Redis mit Passwort):

```yaml
services:
  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: ["redis-server", "--requirepass", "strong-redis-password"]
    ports:
      - "6379:6379"
```

Beispiel Nginx (HTTPS-Termination):

```nginx
location / {
    proxy_pass http://127.0.0.1:5000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
}
```

Beispiel Traefik (Docker labels):

```yaml
labels:
  - traefik.enable=true
  - traefik.http.routers.snipeit-bridge.rule=Host(`bridge.example.com`)
  - traefik.http.routers.snipeit-bridge.entrypoints=websecure
  - traefik.http.routers.snipeit-bridge.tls=true
  - traefik.http.services.snipeit-bridge.loadbalancer.server.port=5000
```

---

## Berechtigungen

### Microsoft Entra ID (App-Registrierung)
Application Permissions (kein delegierter Zugriff):
- `DeviceManagementManagedDevices.Read.All` — Geräte aus Intune
- `User.Read.All` — Benutzer aus Entra ID

### Proxmox API-Token
Unter *Datacenter → Permissions → API Tokens*. Benötigte Rolle: `PVEAuditor` (read-only reicht).

### Zammad
API-Token eines Benutzers mit Lesezugriff auf Tickets.

---

## Zammad: External Data Source einrichten

Der Endpoint `/api/assets?search=<query>` ist ohne Login erreichbar und gibt Assets aus Snipe-IT zurück — im Format das Zammad für External Data Sources erwartet.

Einrichtung in Zammad unter *Admin → Ticket → Core Workflows* oder *Objects*:
- Typ: External Data Source
- URL: `http://<host>/api/assets?search=#{search.term}`
- Value-Key: `value`
- Label-Key: `label`

Das zugehörige Custom-Ticket-Feld `snipeit_asset_id` muss in Zammad als Textfeld angelegt werden. Wenn es einen Wert enthält, schreibt der Zammad-Sync einen Verweis auf das Ticket in die Notes des entsprechenden Snipe-IT Assets.

---

## Sync per Cronjob

```cron
# Täglich um 02:00 Uhr alle Quellen synchronisieren
0 2 * * * cd /opt/snipeit-bridge && .venv/bin/flask sync intune
5 2 * * * cd /opt/snipeit-bridge && .venv/bin/flask sync unifi
10 2 * * * cd /opt/snipeit-bridge && .venv/bin/flask sync proxmox
15 2 * * * cd /opt/snipeit-bridge && .venv/bin/flask sync zammad
```

> Aktuell gibt es keine CLI-Route für Cronjobs — Syncs werden über HTTP POST ausgelöst. Alternativ kann ein kleines Wrapper-Skript verwendet werden:

```bash
#!/bin/bash
curl -s -X POST -b "session=..." http://localhost:5000/sync/intune
```

---

## Projektstruktur

```
snipeit-bridge/
├── app.py                 Flask-App, alle Routen
├── config.py              .env-Loader
├── db.py                  SQLite-Schema, Sync-Historie, Logs
├── connectors/
│   ├── snipeit.py         Snipe-IT REST API Client
│   ├── intune.py          Microsoft Graph API Client (MSAL)
│   ├── unifi.py           Unifi Site Manager API Client
│   ├── proxmox.py         Proxmox PVE API Client
│   └── zammad.py          Zammad REST API Client
├── sync/
│   ├── intune_sync.py     Intune → Snipe-IT (Geräte + Benutzer)
│   ├── unifi_sync.py      Unifi → Snipe-IT
│   ├── proxmox_sync.py    Proxmox → Snipe-IT
│   └── zammad_sync.py     Zammad ↔ Snipe-IT
├── templates/             Jinja2-Templates (Bootstrap 5)
├── .env.example
└── requirements.txt
```

---

## Datenbank

SQLite-Datei `snipeit_bridge.db` wird automatisch beim Start angelegt.

| Tabelle | Inhalt |
|---|---|
| `sync_runs` | Ein Eintrag pro Sync-Lauf (Quelle, Start, Ende, Status, Anzahl) |
| `sync_log` | Log-Zeilen pro Lauf |
| `asset_mapping` | Mapping von Quell-ID → Snipe-IT Asset-ID (vermeidet API-Lookups bei Folge-Syncs) |

---

## Hinweise

- **Kein Löschen**: Assets und Benutzer werden nur angelegt oder aktualisiert, nie gelöscht.
- **Intune-Benutzer**: Werden mit `activated: false` angelegt — sie können sich nicht am Snipe-IT Dashboard anmelden, sind aber als zuweisbare Benutzer verfügbar.
- **Proxmox SSL**: Bei selbst-signierten Zertifikaten `PROXMOX_VERIFY_SSL=false` setzen.
- **Rate Limiting**: Zwischen API-Calls wird 100 ms gewartet. Für sehr große Umgebungen ggf. erhöhen.
