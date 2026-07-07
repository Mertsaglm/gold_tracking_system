# Altin Takip - Windows gunluk yedek + private GitHub push (rehber D)
# Calistir: powershell -ExecutionPolicy Bypass -File scripts\backup.ps1
$ErrorActionPreference = "Stop"
$Proj = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $Proj
$Py = Join-Path $Proj ".venv\Scripts\python.exe"

# 1) Tutarli SQLite dump (.backup API'si — WAL guvenli)
& $Py -m src.backup_db

# 2) Hafta sonu -> pazartesi mutabakatini da tetikle (zararsiz)
try { & $Py -m src.reconcile } catch { Write-Host "reconcile atlandi: $_" }

# 3) Guvenlik: .env izlenmemeli
$tracked = git ls-files .env
if ($tracked) { throw "GUVENLIK: .env git'te izleniyor! Push iptal." }

# 4) Commit + push
git add -A
$staged = git diff --cached --name-only
if ($staged) {
    $stamp = (Get-Date -Format "yyyy-MM-dd")
    git commit -m "backup: veri $stamp" | Out-Null
    git push origin main
    Write-Host "[backup] push tamam: $stamp"
} else {
    Write-Host "[backup] degisiklik yok"
}
