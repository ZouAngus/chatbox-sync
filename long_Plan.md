# long_Plan.md — Chatbox Sync

## Goal
Build a practical external multi-device sync workflow for Chatbox using the app's official backup JSON format, with a lightweight sync server on WSL and client-side upload/download helpers.

## Working mode
- This file is a temporary long-running execution plan for multi-step work.
- Update it as the project evolves.
- Prefer incremental delivery over big-bang rewrites.
- Prefer official import/export channels over reverse-engineering internal storage when possible.

## Confirmed facts
- WSL sync server is deployable and externally reachable.
- Windows Chatbox data is not primarily recoverable from config.json.
- Actual live session data is backed by Chromium IndexedDB/localforage.
- Chatbox has an official restore-capable backup export/import flow.
- Verified backup JSON contains:
  - `chat-sessions-list`
  - `session:<id>` entries
  - `settings`
  - `configVersion`
  - `myCopilots`

## Strategy
1. Stop targeting raw IndexedDB/config internals for MVP.
2. Use backup JSON as the sync artifact.
3. Build upload/download/versioning around backup files.
4. Start with manual import/export assisted by tooling.
5. Consider deeper automation only after MVP works reliably.

## Phase 1 — Reframe current prototype
- [ ] Replace config/session DB assumptions in agent design
- [ ] Add backup-focused API endpoints on server
- [ ] Store uploaded backup files with metadata and hash
- [ ] Add latest-backup fetch endpoint
- [ ] Add backup history listing endpoint

## Phase 2 — Client tooling
- [ ] Add `upload-backup <file>` command
- [ ] Add `download-latest <out>` command
- [ ] Add hash-based dedupe
- [ ] Add device registration metadata
- [ ] Add JSON validation before upload

## Phase 3 — Safety / UX
- [ ] Avoid duplicate uploads for same content hash
- [ ] Show remote-vs-local timestamps
- [ ] Add clear human guidance for import/restore step
- [ ] Preserve backup history on server
- [ ] Add naming convention for downloaded backups

## Phase 4 — Optional automation
- [ ] Watch export directory for new backups
- [ ] Auto-upload newest backup
- [ ] Auto-download remote latest when changed
- [ ] Investigate safe assisted import workflow on Windows

## Phase 5 — Publish when mature enough
- [ ] Clean up project structure
- [ ] Add usage docs and examples
- [ ] Add Windows quickstart steps
- [ ] Add basic safety warnings around import/restore
- [ ] Publish to GitHub when the workflow is stable enough

## Notes
- For this project, prefer something robust and boring over something magical and fragile.
- Backup JSON is the current MVP path.
- When it feels sufficiently usable, prepare it for publishing to GitHub.
