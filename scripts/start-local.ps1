[CmdletBinding()]
param([switch]$Configure, [switch]$CheckOnly, [switch]$ConfigureMedia, [string]$MediaRoot, [string]$OpsRoot)
$ErrorActionPreference = 'Stop'
if ($Configure -and $CheckOnly) { throw 'Choose either -Configure or -CheckOnly.' }
if ((@($Configure.IsPresent,$CheckOnly.IsPresent,$ConfigureMedia.IsPresent) | Where-Object { $_ }).Count -gt 1) { throw 'Choose one mode.' }
$repoRoot = Split-Path -Parent $PSScriptRoot
$apiRoot = Join-Path $repoRoot 'apps/api'
$webRoot = Join-Path $repoRoot 'apps/web'
$envFile = Join-Path $apiRoot '.env'
if (-not (Test-Path -LiteralPath $envFile)) {
    Copy-Item -LiteralPath (Join-Path $apiRoot '.env.example') -Destination $envFile
    Write-Host 'Created apps/api/.env from the local template.'
}
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw 'uv is required. Install it before starting.' }
# uv's repeated --env-file parser treats backslashes as escape characters.
$envFileArgument = $envFile.Replace('\', '/')
$env:UV_CACHE_DIR = Join-Path $repoRoot '.cache/uv'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
# These changes only affect this launcher process and its children.
foreach ($name in @('SELFLORE_MIGRATOR_PASSWORD', 'PGPASSWORD', 'PGHOSTADDR', 'PGSERVICE', 'PGSERVICEFILE')) {
    Remove-Item -LiteralPath "Env:$name" -ErrorAction SilentlyContinue
}
Push-Location $apiRoot
try {
    if ($ConfigureMedia) {
        $mediaArguments = @('run','--frozen','--env-file',$envFileArgument,'python','-m','app.local_start','--configure-media')
        if ($MediaRoot) { $mediaArguments += @('--media-root',$MediaRoot) }
        if ($OpsRoot) { $mediaArguments += @('--ops-root',$OpsRoot) }
        & uv @mediaArguments
        exit $LASTEXITCODE
    }
    if ($Configure) {
        & uv run --frozen --env-file $envFileArgument python -m app.local_start --configure
        exit $LASTEXITCODE
    }
    & uv run --frozen --env-file $envFileArgument python -m app.local_start --check
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    if ($CheckOnly) { exit 0 }
    if (-not (Get-Command pnpm -ErrorAction SilentlyContinue)) { throw 'pnpm is required to build the frontend.' }
    Push-Location $webRoot
    try {
        & pnpm install --frozen-lockfile
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        & pnpm build
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    } finally { Pop-Location }
    & uv run --frozen --env-file $envFileArgument python -m app.local_start
    exit $LASTEXITCODE
} finally { Pop-Location }
