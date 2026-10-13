[CmdletBinding()]
param([switch]$Json,[switch]$Deep,[switch]$Details,[switch]$Record,[string]$Output,[double]$BandwidthMbps=0)
$ErrorActionPreference='Stop'
$repoRoot=Split-Path -Parent $PSScriptRoot
$apiRoot=Join-Path $repoRoot 'apps/api'
$envFile=Join-Path $apiRoot '.env'
if (-not (Test-Path -LiteralPath $envFile)) { throw 'Local configuration missing; diagnosis does not create it.' }
$env:UV_CACHE_DIR=Join-Path $repoRoot '.cache/uv'
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
foreach ($name in @('SELFLORE_MIGRATOR_PASSWORD','PGPASSWORD','PGHOSTADDR','PGSERVICE','PGSERVICEFILE')) { Remove-Item -LiteralPath "Env:$name" -ErrorAction SilentlyContinue }
$arguments=@('run','--frozen','--no-sync','--env-file',$envFile.Replace('\','/'),'python','-c','from app.local_start import configuration; configuration(); from app.media_diagnostics import main; raise SystemExit(main())','--expected-port','6171','--backup-root',(Join-Path $repoRoot 'backups/database'),'--rehearsal-root',(Join-Path $repoRoot '.cache/restore-rehearsals'))
if ($Json) { $arguments += '--json' }
if ($Deep) { $arguments += '--deep' }
if ($Details) { $arguments += '--details' }
if ($Record) { $arguments += '--record' }
if ($Output) { $arguments += @('--output',$Output) }
if ($BandwidthMbps -gt 0) { $arguments += @('--bandwidth-mbps',[string]$BandwidthMbps) }
Push-Location -LiteralPath $apiRoot
try { & uv @arguments; exit $LASTEXITCODE } finally { Pop-Location }
