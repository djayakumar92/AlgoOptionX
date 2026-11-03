[CmdletBinding()]
param([switch]$Diagnose, [int]$Port = 8000)
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$paperProcess = $null
$created = $false
function Test-LocalPort([int]$Number) {
    $socket = New-Object System.Net.Sockets.TcpClient
    try { $socket.Connect('127.0.0.1', $Number); return $true } catch { return $false } finally { $socket.Dispose() }
}
try {
    Set-Location $projectRoot
    if ($Port -lt 1024 -or $Port -gt 65535) { throw 'Choose a port from 1024 to 65535.' }
    Write-Host 'AlgoOptionX | PAPER execution | SYNTHETIC data | Local access only' -ForegroundColor Cyan
    $pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
    if (!(Test-Path $pythonExe)) { throw 'Python environment missing. Install Python 3.12+ and uv, then run: uv sync --frozen --extra dev' }
    & $pythonExe -c "import sys; assert sys.version_info >= (3,12); import uvicorn, algooptionx.api.app"
    if ($LASTEXITCODE -ne 0) { throw 'Python prerequisites are incomplete. Run: uv sync --frozen --extra dev' }
    $frontend = Join-Path $projectRoot 'apps\web\dist\index.html'
    if (!(Test-Path $frontend)) { throw 'Frontend missing. Install Node 22.12+ and npm, then run: npm --prefix apps/web ci and npm --prefix apps/web run build' }
    $inputs = @(Get-ChildItem (Join-Path $projectRoot 'apps\web\src') -File -Recurse)
    $inputs += Get-Item (Join-Path $projectRoot 'apps\web\package-lock.json'), (Join-Path $projectRoot 'apps\web\index.html')
    $latest = $inputs | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
    if ($latest.LastWriteTimeUtc -gt (Get-Item $frontend).LastWriteTimeUtc) { throw 'Frontend build is stale. Run: npm --prefix apps/web run build' }
    if (Test-LocalPort $Port) { throw "Port $Port is already occupied. Close that server or choose a different -Port. No existing process was stopped." }
    Write-Host "Python environment and frontend ready. Port $Port is available."
    if ($Diagnose) {
        foreach ($tool in @('node', 'npm', 'uv')) { if (Get-Command $tool -ErrorAction SilentlyContinue) { Write-Host "$tool is available" } else { Write-Warning "$tool is unavailable (needed for setup/development, not the built application)." } }
        Write-Host 'Diagnostics complete. No server started; no packages installed; no tests run.'
        exit 0
    }
    $logDirectory = Join-Path $projectRoot 'logs'
    New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
    $runId = [Guid]::NewGuid().ToString('N')
    $stdoutPath = Join-Path $logDirectory "startup-$runId.out.log"
    $stderrPath = Join-Path $logDirectory "startup-$runId.err.log"
    $arguments = "-m uvicorn algooptionx.api.app:app --host 127.0.0.1 --port $Port"
    $paperProcess = Start-Process -FilePath $pythonExe -ArgumentList $arguments -WorkingDirectory $projectRoot -PassThru -NoNewWindow -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
    $created = $true
    $ready = $false
    $deadline = (Get-Date).AddSeconds(40)
    while ((Get-Date) -lt $deadline) {
        if ($paperProcess.HasExited) { throw "Server exited. See $stderrPath" }
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 1
            if ($health.name -eq 'AlgoOptionX' -and $health.status -eq 'ok' -and $health.mode -eq 'PAPER' -and $health.source -eq 'SYNTHETIC') { $ready = $true; break }
        } catch { }
        Start-Sleep -Milliseconds 250
    }
    if (!$ready) { throw "Server did not become ready in 40 seconds. See $stderrPath" }
    Start-Process "http://127.0.0.1:$Port/"
    Write-Host 'Ready. Press Enter here to stop the owned server. Logs are in logs/.' -ForegroundColor Green
    while (!$paperProcess.HasExited) {
        if ([Console]::KeyAvailable -and [Console]::ReadKey($true).Key -eq 'Enter') { break }
        Start-Sleep -Milliseconds 200
    }
    if ($paperProcess.HasExited -and $paperProcess.ExitCode -ne 0) { throw "Server exited unexpectedly. See $stderrPath" }
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
} finally {
    if ($created -and $paperProcess -and !$paperProcess.HasExited) {
        Stop-Process -Id $paperProcess.Id -ErrorAction SilentlyContinue
        Write-Host 'Owned local server stopped. Stored history was preserved.'
    }
}
