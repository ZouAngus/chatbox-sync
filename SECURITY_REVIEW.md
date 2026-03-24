# Security Review

## Scope reviewed

Reviewed repository contents intended for GitHub publication.

## Checked for obvious sensitive material

Manual checks covered:

- API keys / bearer tokens / OpenAI-style keys
- passwords / secrets / private keys
- local backup payloads
- local SQLite DBs
- server runtime logs
- uploaded backup artifacts
- virtual environment contents

## Findings

The repository content intended for commit is currently clean of obvious sensitive material.

Ignored and excluded from version control:

- `.venv/`
- `server/chatbox_sync.db`
- `server/backups/`
- `server/uvicorn.log`
- runtime download artifacts

## Important caveat

This is a practical repository review, not a formal secret scanner guarantee.
Before publishing, still re-check:

- `git status`
- staged diff
- remote URL target

## Recommendation

Safe to publish once staged contents are reviewed and confirmed.
