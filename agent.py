from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import sys
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_SERVER = os.environ.get("CHATBOX_SYNC_SERVER", "http://127.0.0.1:8765")
STATE_DIR = Path.home() / ".config" / "chatbox-sync"
STATE_FILE = STATE_DIR / "state.json"


def load_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        device_id = str(uuid.uuid4())
        return {"device_id": device_id, "last_download_hash": None}
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def save_state(state: dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    req = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_json(url: str) -> dict[str, Any]:
    with urlopen(url) as resp:
        return json.loads(resp.read().decode("utf-8"))


def register(server: str, state: dict[str, Any]) -> None:
    post_json(
        f"{server}/devices/register",
        {"device_id": state["device_id"], "name": socket.gethostname()},
    )


def encode_multipart(fields: dict[str, str], file_field: str, file_path: Path) -> tuple[bytes, str]:
    boundary = f"----chatboxsync{uuid.uuid4().hex}"
    parts: list[bytes] = []

    for name, value in fields.items():
        parts.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                str(value).encode("utf-8"),
                b"\r\n",
            ]
        )

    parts.extend(
        [
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{file_field}"; filename="{file_path.name}"\r\n'.encode(),
            b"Content-Type: application/json\r\n\r\n",
            file_path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )

    body = b"".join(parts)
    return body, boundary


def upload_backup(server: str, state: dict[str, Any], backup_path: Path) -> dict[str, Any]:
    if not backup_path.exists():
        raise FileNotFoundError(f"backup file not found: {backup_path}")

    json.loads(backup_path.read_text(encoding="utf-8"))
    body, boundary = encode_multipart(
        {
            "device_id": state["device_id"],
            "device_name": socket.gethostname(),
        },
        "file",
        backup_path,
    )
    req = Request(
        f"{server}/backups/upload",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def latest_meta(server: str) -> dict[str, Any]:
    return get_json(f"{server}/backups/latest")


def default_download_path(filename: str | None, content_hash: str | None) -> Path:
    safe = filename or (f"chatbox-backup-{(content_hash or 'latest')[:12]}.json")
    downloads_dir = Path.cwd() / ".downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)
    return downloads_dir / safe


def download_latest(server: str, state: dict[str, Any], out_path: Path | None, force: bool = False) -> dict[str, Any]:
    data = get_json(f"{server}/backups/download/latest")
    content_hash = data["content_hash"]
    if (not force) and state.get("last_download_hash") == content_hash:
        return {"ok": True, "skipped": True, "reason": "same hash already downloaded", **data}

    target = out_path if out_path else default_download_path(data.get("filename"), content_hash)
    target.write_text(data["content"], encoding="utf-8")
    state["last_download_hash"] = content_hash
    save_state(state)
    return {
        "ok": True,
        "skipped": False,
        "saved_to": str(target),
        "import_hint": "Import this JSON from Chatbox Settings -> Backup / Restore on the target device.",
        **{k: v for k, v in data.items() if k != 'content'},
    }


def sync_backup(
    server: str,
    state: dict[str, Any],
    backup_path: Path,
    download_out: Path | None = None,
    force_upload: bool = False,
    force_download: bool = False,
) -> dict[str, Any]:
    if force_upload and force_download:
        raise ValueError("cannot force upload and download at the same time")
    if not backup_path.exists():
        raise FileNotFoundError(f"backup file not found: {backup_path}")

    local_hash = sha256_file(backup_path)
    remote = latest_meta(server)
    remote_hash = remote["content_hash"]

    result: dict[str, Any] = {
        "local_file": str(backup_path),
        "local_hash": local_hash,
        "remote_hash": remote_hash,
        "action": None,
    }

    if local_hash == remote_hash and not (force_upload or force_download):
        result["action"] = "noop"
        result["reason"] = "local backup already matches remote latest"
        return result

    if force_upload:
        result["action"] = "upload"
        result["upload_result"] = upload_backup(server, state, backup_path)
        return result

    if force_download:
        result["action"] = "download"
        result["download_result"] = download_latest(server, state, download_out, force=True)
        return result

    local_mtime = int(backup_path.stat().st_mtime)
    remote_uploaded = int(remote.get("uploaded_at", 0)) // 1000
    result["local_mtime"] = local_mtime
    result["remote_uploaded_at_s"] = remote_uploaded

    if local_mtime >= remote_uploaded:
        upload_result = upload_backup(server, state, backup_path)
        result["action"] = "upload"
        result["upload_result"] = upload_result
        return result

    download_result = download_latest(server, state, download_out)
    result["action"] = "download"
    result["download_result"] = download_result
    return result


def cmd_upload_backup(args: argparse.Namespace) -> int:
    state = load_state()
    register(args.server, state)
    result = upload_backup(args.server, state, Path(args.file))
    save_state(state)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_download_latest(args: argparse.Namespace) -> int:
    state = load_state()
    register(args.server, state)
    result = download_latest(args.server, state, Path(args.out) if args.out else None, force=args.force)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    result = get_json(f"{args.server}/backups/history?{urlencode({'limit': args.limit})}")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_latest_meta(args: argparse.Namespace) -> int:
    result = latest_meta(args.server)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_sync_backup(args: argparse.Namespace) -> int:
    state = load_state()
    register(args.server, state)
    result = sync_backup(
        args.server,
        state,
        Path(args.file),
        Path(args.out) if args.out else None,
        force_upload=args.force_upload,
        force_download=args.force_download,
    )
    save_state(state)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Chatbox backup sync agent")
    parser.add_argument("--server", default=DEFAULT_SERVER)
    sub = parser.add_subparsers(dest="command", required=True)

    up = sub.add_parser("upload-backup")
    up.add_argument("file")

    dl = sub.add_parser("download-latest")
    dl.add_argument("--out", default=None)
    dl.add_argument("--force", action="store_true")

    hist = sub.add_parser("history")
    hist.add_argument("--limit", type=int, default=20)

    sub.add_parser("latest-meta")

    sync = sub.add_parser("sync-backup")
    sync.add_argument("file")
    sync.add_argument("--out", default=None)
    sync.add_argument("--force-upload", action="store_true")
    sync.add_argument("--force-download", action="store_true")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "upload-backup":
            return cmd_upload_backup(args)
        if args.command == "download-latest":
            return cmd_download_latest(args)
        if args.command == "history":
            return cmd_history(args)
        if args.command == "latest-meta":
            return cmd_latest_meta(args)
        if args.command == "sync-backup":
            return cmd_sync_backup(args)
        parser.error("unknown command")
        return 2
    except (HTTPError, URLError, FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
