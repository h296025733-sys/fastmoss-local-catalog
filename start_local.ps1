param(
    [string]$DataRoot = $env:FASTMOSS_DATA_ROOT,
    [int]$Port = 8767
)
$ErrorActionPreference = 'Stop'
$projectDir = $PSScriptRoot
if (-not $DataRoot) { $DataRoot = Join-Path $projectDir 'data' }
$pythonExe = Join-Path $projectDir '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Create .venv and install requirements.txt first.' }
if (-not (Test-Path -LiteralPath (Join-Path $DataRoot 'catalog.sqlite3'))) {
    throw 'Import your own data before starting the viewer.'
}
& $pythonExe (Join-Path $projectDir 'web\server.py') --root $DataRoot --port $Port
