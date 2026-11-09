$ErrorActionPreference = "Stop"

$ProjectPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonPath = Join-Path $ProjectPath ".venv\Scripts\python.exe"
$LogPath = Join-Path $ProjectPath "logs\scheduled_backup_runner.log"

$RunId = [guid]::NewGuid().ToString("N")

$StdoutFile = Join-Path $env:TEMP "backup_stdout_$RunId.log"
$StderrFile = Join-Path $env:TEMP "backup_stderr_$RunId.log"

$ExitCode = 1

New-Item -ItemType Directory `
    -Path (Join-Path $ProjectPath "logs") `
    -Force | Out-Null

Add-Content $LogPath "`n========================================"
Add-Content $LogPath "Scheduled backup started: $(Get-Date)"

try {

    if (-not (Test-Path $PythonPath)) {
        throw "Python executable not found: $PythonPath"
    }

    $Process = Start-Process `
        -FilePath $PythonPath `
        -ArgumentList @("-u", "-m", "app.database.backup_manager") `
        -WorkingDirectory $ProjectPath `
        -Wait `
        -PassThru `
        -RedirectStandardOutput $StdoutFile `
        -RedirectStandardError $StderrFile

    if (Test-Path $StdoutFile) {
        $Output = Get-Content $StdoutFile -Raw
        if ($Output) {
            Add-Content $LogPath $Output
        }
    }

    if (Test-Path $StderrFile) {
        $ErrorOutput = Get-Content $StderrFile -Raw
        if ($ErrorOutput) {
            Add-Content $LogPath $ErrorOutput
        }
    }

    $ExitCode = $Process.ExitCode

    Add-Content $LogPath "Scheduled backup finished: $(Get-Date)"
    Add-Content $LogPath "Python exit code: $ExitCode"

}
catch {

    Add-Content $LogPath "LAUNCHER ERROR: $_"
    Add-Content $LogPath "Scheduled backup failed: $(Get-Date)"

    $ExitCode = 1

}
finally {

    Remove-Item $StdoutFile, $StderrFile `
        -Force `
        -ErrorAction SilentlyContinue

}

exit $ExitCode
