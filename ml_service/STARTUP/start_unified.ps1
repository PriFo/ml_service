# Unified startup script for ML Service 0.9.1
# Shows logs from both backend and frontend in the same window

$scriptPath = $PSScriptRoot
$ErrorActionPreference = 'Continue'

Write-Host '========================================' -ForegroundColor Cyan
Write-Host 'ML Service 0.9.1 - Unified Logs' -ForegroundColor Cyan
Write-Host '========================================' -ForegroundColor Cyan
Write-Host 'Backend:  http://localhost:8085' -ForegroundColor Green
Write-Host 'Frontend: http://localhost:6565' -ForegroundColor Green
Write-Host '========================================' -ForegroundColor Cyan
Write-Host ''

# Start backend
$backendJob = Start-Job -ScriptBlock {
    param([string]$path)
    Set-Location "$path\backend"
    if (-not (Test-Path 'venv')) {
        python -m venv venv
    }
    & ".\venv\Scripts\Activate.ps1"
    pip install --prefer-binary --upgrade -r requirements.txt *>&1 | Out-Null
    python -m ml_service *>&1
} -ArgumentList $scriptPath

# Wait a bit before starting frontend
Start-Sleep -Seconds 3

# Start frontend
$frontendJob = Start-Job -ScriptBlock {
    param([string]$path)
    Set-Location "$path\frontend"
    if (-not (Test-Path 'node_modules')) {
        npm install --legacy-peer-deps *>&1 | Out-Null
    }
    npm run dev *>&1
} -ArgumentList $scriptPath

# Monitor and display logs
while ($backendJob.State -eq 'Running' -or $frontendJob.State -eq 'Running') {
    $backendOutput = Receive-Job -Job $backendJob -ErrorAction SilentlyContinue
    $frontendOutput = Receive-Job -Job $frontendJob -ErrorAction SilentlyContinue

    if ($backendOutput) {
        foreach ($line in $backendOutput) {
            if ($line) {
                $lineStr = if ($line -is [string]) { $line.Trim() } else { $line.ToString().Trim() }
                if ($lineStr) {
                    Write-Host '[BACKEND]' -NoNewline -ForegroundColor Yellow
                    Write-Host " $lineStr"
                }
            }
        }
    }

    if ($frontendOutput) {
        foreach ($line in $frontendOutput) {
            if ($line) {
                $lineStr = if ($line -is [string]) { $line.Trim() } else { $line.ToString().Trim() }
                if ($lineStr) {
                    Write-Host '[FRONTEND]' -NoNewline -ForegroundColor Magenta
                    Write-Host " $lineStr"
                }
            }
        }
    }

    Start-Sleep -Milliseconds 300
}

# Get remaining output
$remainingBackend = Receive-Job -Job $backendJob -ErrorAction SilentlyContinue
$remainingFrontend = Receive-Job -Job $frontendJob -ErrorAction SilentlyContinue

if ($remainingBackend) {
    foreach ($line in $remainingBackend) {
        if ($line) {
            $lineStr = if ($line -is [string]) { $line.Trim() } else { $line.ToString().Trim() }
            if ($lineStr) {
                Write-Host '[BACKEND]' -NoNewline -ForegroundColor Yellow
                Write-Host " $lineStr"
            }
        }
    }
}

if ($remainingFrontend) {
    foreach ($line in $remainingFrontend) {
        if ($line) {
            $lineStr = if ($line -is [string]) { $line.Trim() } else { $line.ToString().Trim() }
            if ($lineStr) {
                Write-Host '[FRONTEND]' -NoNewline -ForegroundColor Magenta
                Write-Host " $lineStr"
            }
        }
    }
}

Write-Host ''
Write-Host 'Services stopped.' -ForegroundColor Red
Remove-Job -Job $backendJob,$frontendJob -ErrorAction SilentlyContinue

