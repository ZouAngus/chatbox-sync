from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "chatbox_sync.db"
BACKUP_DIR = BASE_DIR / "backups"

app = FastAPI(title="chatbox-sync", version="0.2.0")


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS devices (
                device_id TEXT PRIMARY KEY,
                name TEXT,
                created_at INTEGER NOT NULL,
                last_seen_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS backups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT,
                filename TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                exported_at TEXT,
                uploaded_at INTEGER NOT NULL,
                session_count INTEGER,
                top_keys_json TEXT
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_backups_hash ON backups(content_hash);
            CREATE INDEX IF NOT EXISTS idx_backups_uploaded_at ON backups(uploaded_at DESC);
            """
        )


class DeviceRegister(BaseModel):
    device_id: str
    name: str | None = None


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_backup_json(raw: bytes) -> dict[str, Any]:
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"invalid backup json: {exc}") from exc


def backup_meta(data: dict[str, Any]) -> dict[str, Any]:
    keys = list(data.keys())
    session_count = sum(1 for k in keys if k.startswith("session:"))
    return {
        "exported_at": data.get("__exported_at"),
        "session_count": session_count,
        "top_keys": keys[:100],
    }


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "db": str(DB_PATH), "backup_dir": str(BACKUP_DIR)}


@app.post("/devices/register")
def register_device(payload: DeviceRegister) -> dict[str, Any]:
    now = int(time.time() * 1000)
    with db() as conn:
        conn.execute(
            """
            INSERT INTO devices (device_id, name, created_at, last_seen_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(device_id) DO UPDATE SET
                name=excluded.name,
                last_seen_at=excluded.last_seen_at
            """,
            (payload.device_id, payload.name, now, now),
        )
    return {"ok": True, "device_id": payload.device_id}


@app.post("/backups/upload")
async def upload_backup(
    file: UploadFile = File(...),
    device_id: str = Form(...),
    device_name: str | None = Form(default=None),
) -> dict[str, Any]:
    now = int(time.time() * 1000)
    raw = await file.read()
    content_hash = sha256_bytes(raw)
    parsed = parse_backup_json(raw)
    meta = backup_meta(parsed)

    with db() as conn:
        conn.execute(
            """
            INSERT INTO devices (device_id, name, created_at, last_seen_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(device_id) DO UPDATE SET
                name=COALESCE(excluded.name, name),
                last_seen_at=excluded.last_seen_at
            """,
            (device_id, device_name, now, now),
        )

        existing = conn.execute(
            "SELECT id, stored_path, uploaded_at FROM backups WHERE content_hash=?",
            (content_hash,),
        ).fetchone()
        if existing is not None:
            return {
                "ok": True,
                "deduped": True,
                "backup_id": existing["id"],
                "uploaded_at": existing["uploaded_at"],
                "content_hash": content_hash,
                "session_count": meta["session_count"],
            }

        safe_name = Path(file.filename or f"backup-{now}.json").name
        stored_name = f"{now}-{content_hash[:12]}-{safe_name}"
        stored_path = BACKUP_DIR / stored_name
        stored_path.write_bytes(raw)

        cur = conn.execute(
            """
            INSERT INTO backups (
                device_id, filename, stored_path, content_hash, size_bytes,
                exported_at, uploaded_at, session_count, top_keys_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                device_id,
                safe_name,
                str(stored_path),
                content_hash,
                len(raw),
                meta["exported_at"],
                now,
                meta["session_count"],
                json.dumps(meta["top_keys"], ensure_ascii=False),
            ),
        )
        backup_id = cur.lastrowid

    return {
        "ok": True,
        "deduped": False,
        "backup_id": backup_id,
        "uploaded_at": now,
        "content_hash": content_hash,
        "session_count": meta["session_count"],
        "exported_at": meta["exported_at"],
    }


@app.get("/backups/latest")
def latest_backup() -> dict[str, Any]:
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM backups ORDER BY uploaded_at DESC LIMIT 1"
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="no backups uploaded yet")
    return dict(row)


@app.get("/backups/history")
def backup_history(limit: int = 20) -> dict[str, Any]:
    limit = max(1, min(limit, 200))
    with db() as conn:
        rows = conn.execute(
            "SELECT id, device_id, filename, stored_path, content_hash, size_bytes, exported_at, uploaded_at, session_count FROM backups ORDER BY uploaded_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return {"items": [dict(r) for r in rows]}


@app.get("/backups/download/latest")
def download_latest_backup() -> dict[str, Any]:
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM backups ORDER BY uploaded_at DESC LIMIT 1"
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="no backups uploaded yet")
    path = Path(row["stored_path"])
    if not path.exists():
        raise HTTPException(status_code=500, detail="stored backup file missing")
    return {
        "filename": row["filename"],
        "content_hash": row["content_hash"],
        "uploaded_at": row["uploaded_at"],
        "exported_at": row["exported_at"],
        "session_count": row["session_count"],
        "content": path.read_text(encoding="utf-8"),
    }
