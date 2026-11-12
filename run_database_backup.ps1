
$ErrorActionPreference = "Stop"

# --------------------------------------------------
# PROJECT CONFIGURATION
# --------------------------------------------------

$ProjectPath = Split-Path -Parent $MyInvocation.MyCommand.Path

$PythonPath = Join-Path $ProjectPath ".venv\Scripts\python.exe"

$LogPath = Join-Path $ProjectPath "logs\scheduled_backup_runner.log"

$RunId = [guid]::NewGuid().ToString("N")

$StdoutFile = Join-Path $env:TEMP "backup_stdout_$RunId.log"

$StderrFile = Join-Path $env:TEMP "backup_stderr_$RunId.log"

$ExitCode = 1

# --------------------------------------------------
# SCHEDULED OAUTH CONFIGURATION
# --------------------------------------------------

$BrowserAuthVariable = "AI_BACKUP_ALLOW_BROWSER_AUTH"

# Preserve the previous environment setting.
$PreviousBrowserAuthSetting = [Environment]::GetEnvironmentVariable(
    $BrowserAuthVariable,
    "Process"
)

# --------------------------------------------------
# CREATE LOG DIRECTORY
# --------------------------------------------------

New-Item -ItemType Directory `
    -Path (Join-Path $ProjectPath "logs") `
    -Force | Out-Null

Add-Content $LogPath "`n========================================"
Add-Content $LogPath "Scheduled backup started: $(Get-Date)"

try {

    # --------------------------------------------------
    # 1. VERIFY PYTHON EXECUTABLE
    # --------------------------------------------------

    if (-not (Test-Path $PythonPath)) {

        throw "Python executable not found: $PythonPath"

    }

    Add-Content $LogPath "Python executable verified."

    # --------------------------------------------------
    # 2. DISABLE BROWSER OAUTH AUTHENTICATION
    # --------------------------------------------------

    $env:AI_BACKUP_ALLOW_BROWSER_AUTH = "0"

    Add-Content $LogPath `
        "Scheduled OAuth mode: Browser authentication disabled."

    # --------------------------------------------------
    # 3. EXECUTE DATABASE BACKUP
    # --------------------------------------------------

    Add-Content $LogPath "Starting Python backup manager..."

    $Process = Start-Process `
        -FilePath $PythonPath `
        -ArgumentList @(
            "-u",
            "-m",
            "app.database.backup_manager"
        ) `
        -WorkingDirectory $ProjectPath `
        -Wait `
        -PassThru `
        -RedirectStandardOutput $StdoutFile `
        -RedirectStandardError $StderrFile

    # --------------------------------------------------
    # 4. CAPTURE STANDARD OUTPUT
    # --------------------------------------------------

    if (Test-Path $StdoutFile) {

        $Output = Get-Content $StdoutFile -Raw

        if ($Output) {

            Add-Content $LogPath $Output

        }

    }

    # --------------------------------------------------
    # 5. CAPTURE ERROR OUTPUT
    # --------------------------------------------------

    if (Test-Path $StderrFile) {

        $ErrorOutput = Get-Content $StderrFile -Raw

        if ($ErrorOutput) {

            Add-Content $LogPath $ErrorOutput

        }

    }

    # --------------------------------------------------
    # 6. CAPTURE PYTHON EXIT CODE
    # --------------------------------------------------

    $ExitCode = $Process.ExitCode

    Add-Content $LogPath `
        "Scheduled backup finished: $(Get-Date)"

    Add-Content $LogPath `
        "Python exit code: $ExitCode"

    # --------------------------------------------------
    # 7. LOG BACKUP RESULT
    # --------------------------------------------------

    if ($ExitCode -eq 0) {

        Add-Content $LogPath `
            "BACKUP STATUS: LOCAL AND CLOUD SUCCESS"

    }
    elseif ($ExitCode -eq 2) {

        Add-Content $LogPath `
            "BACKUP STATUS: LOCAL SUCCESS, CLOUD FAILED"

    }
    else {

        Add-Content $LogPath `
            "BACKUP STATUS: FAILED"

    }

}
catch {

    # --------------------------------------------------
    # HANDLE LAUNCHER ERRORS
    # --------------------------------------------------

    Add-Content $LogPath "LAUNCHER ERROR: $_"

    Add-Content $LogPath `
        "Scheduled backup failed: $(Get-Date)"

    $ExitCode = 1

}
finally {

    # --------------------------------------------------
    # 1. CLEAN TEMPORARY LOG FILES
    # --------------------------------------------------

    Remove-Item $StdoutFile, $StderrFile `
        -Force `
        -ErrorAction SilentlyContinue

    # --------------------------------------------------
    # 2. RESTORE PREVIOUS ENVIRONMENT SETTING
    # --------------------------------------------------

    if ($null -eq $PreviousBrowserAuthSetting) {

        Remove-Item "Env:\$BrowserAuthVariable" `
            -ErrorAction SilentlyContinue

    }
    else {

        [Environment]::SetEnvironmentVariable(
            $BrowserAuthVariable,
            $PreviousBrowserAuthSetting,
            "Process"
        )

    }

}

# --------------------------------------------------
# RETURN FINAL EXIT CODE
# --------------------------------------------------

exit $ExitCode
