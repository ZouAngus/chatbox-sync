# chatbox-sync

A lightweight external multi-device sync helper for Chatbox, using Chatbox's official backup JSON import/export flow.

## Status

Early MVP, but the basic loop is working:

- export backup JSON from Chatbox
- upload it to a small sync server
- inspect remote latest backup
- download latest backup on another device
- import it back into Chatbox

This project intentionally prefers the official backup path over reverse-engineering Chatbox's live IndexedDB storage.

## Why this approach?

Chatbox desktop stores live conversation data in Chromium-style IndexedDB/localforage internals, which are possible to investigate but awkward and fragile to automate.

Chatbox also provides an official **Settings → Backup** export/import flow. That backup JSON is:

- restorable
- structured
- stable enough for an external sync MVP
- much safer than poking at live storage

## Current features

### Server

- `GET /health`
- `POST /devices/register`
- `POST /backups/upload`
- `GET /backups/latest`
- `GET /backups/history`
- `GET /backups/download/latest`

### Agent

- `upload-backup <file>`
- `download-latest [--out path] [--force]`
- `history [--limit N]`
- `latest-meta`
- `sync-backup <file> [--out path] [--force-upload|--force-download]`

## Project layout

- `server/` — FastAPI sync server
- `agent.py` — CLI helper for upload/download/sync decisions
- `windows_quickstart.ps1` — minimal Windows helper script
- `notes/` — research notes
- `long_Plan.md` — temporary long-running execution plan

## Requirements

### Server side

- Python 3.11+
- `fastapi`
- `uvicorn`
- `pydantic`
- `python-multipart`

### Client side

- Python 3.11+ for `agent.py`
- Chatbox with backup export/import support

## Start the server

```bash
cd chatbox-sync
python3 -m venv .venv
. .venv/bin/activate
pip install -r server/requirements.txt
cd server
python -m uvicorn app:app --host 0.0.0.0 --port 8765
```

Health check:

```bash
curl http://127.0.0.1:8765/health
```

## Typical workflow

### Device A

1. In Chatbox, use **Settings → Backup**
2. Export a backup JSON file
3. Upload it:

```bash
python agent.py --server http://YOUR_SERVER:8765 upload-backup /path/to/chatbox-exported-data.json
```

### Device B

1. Inspect remote latest:

```bash
python agent.py --server http://YOUR_SERVER:8765 latest-meta
```

2. Download the latest backup:

```bash
python agent.py --server http://YOUR_SERVER:8765 download-latest --out ./downloaded-chatbox-backup.json
```

3. In Chatbox, use **Settings → Backup / Restore** to import the downloaded JSON

## Sync helper

You can also let the agent compare your local backup with the current remote latest:

```bash
python agent.py --server http://YOUR_SERVER:8765 sync-backup /path/to/local-backup.json --out ./remote-latest.json
```

Possible actions:

- `noop` — local backup already matches remote latest
- `upload` — local backup is treated as newer and gets uploaded
- `download` — remote latest is treated as newer and gets downloaded

Force options:

- `--force-upload` — upload the local file even if the heuristic would not choose upload
- `--force-download` — download the remote latest even if the heuristic would not choose download

## Windows quickstart

A minimal PowerShell helper is included:

```powershell
./windows_quickstart.ps1 -Server "http://YOUR_SERVER:8765" -BackupFile "$env:USERPROFILE\Desktop\chatbox-exported-data.json"
```

## Important limitations

- This is not live real-time sync yet.
- Import on the target device is still a manual Chatbox action.
- Conflict handling is still primitive.
- Backup-based sync is safer, but less seamless than deep app integration.
- Blob / attachment sync is not separately handled yet.

## Safety notes

- Prefer exporting a fresh backup before import/restore.
- Keep your own backup history.
- Test on non-critical conversations first.
- Do not assume perfect merge behavior across multiple rapidly changing devices.

## Near-term roadmap

- Improve Windows workflow
- Add better force/manual control flags
- Add clearer timestamp comparison
- Add backup file naming conventions
- Improve docs and publishing readiness
- Publish to GitHub when stable enough
