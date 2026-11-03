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
    if (Test-LocalPort $Port) { throw "Port $Port is already occupied. Close that server or choose a different -Port. No existing process was stopped." }
    $webDirectory = Join-Path $projectRoot 'apps\web'
    $frontend = Join-Path $webDirectory 'dist\index.html'
    $inputs = @(Get-ChildItem (Join-Path $webDirectory 'src') -File -Recurse)
    foreach ($name in @('package.json', 'package-lock.json', 'index.html', 'vite.config.ts', 'tsconfig.json', 'tsconfig.app.json', 'tsconfig.node.json')) {
        $inputPath = Join-Path $webDirectory $name
        if (Test-Path $inputPath) { $inputs += Get-Item $inputPath }
    }
    $latest = $inputs | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
    $needsBuild = !(Test-Path $frontend)
    if (!$needsBuild) { $needsBuild = $latest.LastWriteTimeUtc -gt (Get-Item $frontend).LastWriteTimeUtc }
    if ($needsBuild) {
        if ($Diagnose) { throw 'Frontend missing or stale. Normal Start-AlgoOptionX.bat will rebuild it automatically. Manual repair: npm --prefix apps/web ci, then npm --prefix apps/web run build. Diagnostics made no changes.' }
        # Use the executable shim, not npm.ps1, so Windows execution policy does
        # not prevent npm from running. Argument paths may contain spaces.
        $npmCommand = Get-Command npm.cmd -CommandType Application -ErrorAction SilentlyContinue
        $nodeCommand = Get-Command node.exe -CommandType Application -ErrorAction SilentlyContinue
        if (!$npmCommand -or !$nodeCommand) { throw 'Frontend rebuild requires Node 22.12+ and npm. Install Node, reopen Start-AlgoOptionX.bat and try again.' }
        $nodeVersionText = & $nodeCommand.Source --version
        if ($LASTEXITCODE -ne 0) { throw 'Unable to run Node. Repair the Node installation and try again.' }
        $nodeVersion = [Version]($nodeVersionText.Trim().TrimStart('v'))
        if ($nodeVersion -lt [Version]'22.12.0') { throw 'Frontend rebuild requires Node 22.12+ (Node 24 recommended). Update Node and try again.' }
        $installedLock = Join-Path $webDirectory 'node_modules\.package-lock.json'
        $packageLock = Join-Path $webDirectory 'package-lock.json'
        $needsInstall = !(Test-Path $installedLock)
        if (!$needsInstall) { $needsInstall = (Get-Item $packageLock).LastWriteTimeUtc -gt (Get-Item $installedLock).LastWriteTimeUtc }
        if ($needsInstall) {
            Write-Host 'Preparing frontend dependencies from package-lock.json...'
            & $npmCommand.Source --prefix $webDirectory ci
            if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed. Check the npm output above and retry. No server was started.' }
        }
        Write-Host 'Building the updated frontend. This may take a moment...' -ForegroundColor Cyan
        & $npmCommand.Source --prefix $webDirectory run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed. Check the build output above. No server was started.' }
        if (!(Test-Path $frontend)) { throw 'Frontend build returned success but dist/index.html is missing. No server was started.' }
    }
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
