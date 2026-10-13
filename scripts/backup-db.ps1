[CmdletBinding()]
param([switch]$Rehearse, [string]$BackupPath)
$ErrorActionPreference = 'Stop'
if ($BackupPath -and -not $Rehearse) { throw '-BackupPath requires -Rehearse.' }
$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw 'uv is required.' }
if (-not $BackupPath) {
    $migrationPassword = [Environment]::GetEnvironmentVariable('SELFLORE_MIGRATOR_PASSWORD', 'User')
    if (-not $migrationPassword) { $migrationPassword = $env:SELFLORE_MIGRATOR_PASSWORD }
    if (-not $migrationPassword) { throw 'Configure SELFLORE_MIGRATOR_PASSWORD locally; do not put it in command arguments.' }
    $env:SELFLORE_MIGRATOR_PASSWORD = $migrationPassword
}
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:UV_CACHE_DIR = Join-Path $repoRoot '.cache/uv'
$arguments = @('run', '--frozen', '--no-env-file', 'python', '-m', 'app.db_backup')
if ($Rehearse) { $arguments += '--rehearse' }
if ($BackupPath) {
    $resolvedBackupPath = (Resolve-Path -LiteralPath $BackupPath).Path
    $arguments += @('--bundle', $resolvedBackupPath.Replace('\', '/'))
}
Push-Location (Join-Path $repoRoot 'apps/api')
try { & uv @arguments; exit $LASTEXITCODE } finally { Pop-Location }
