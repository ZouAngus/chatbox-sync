param(
  [string]$Server = "http://100.84.81.44:8765",
  [string]$BackupFile = "$env:USERPROFILE\Desktop\chatbox-exported-data-2026-3-24.json",
  [string]$PythonExe = "python"
)

Write-Host "== Chatbox Sync Windows Quickstart ==" -ForegroundColor Cyan
Write-Host "Server: $Server"
Write-Host "Backup: $BackupFile"
Write-Host ""
Write-Host "[1/2] Remote latest metadata" -ForegroundColor Yellow
& $PythonExe agent.py --server $Server latest-meta
Write-Host ""
Write-Host "[2/2] Sync decision" -ForegroundColor Yellow
& $PythonExe agent.py --server $Server sync-backup $BackupFile
Write-Host ""
Write-Host "If a file was downloaded, import it from Chatbox Settings -> Backup / Restore." -ForegroundColor Green
