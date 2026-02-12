# Unified startup script for ML Service 0.11.2
# Shows logs from both backend and frontend in the same window
# Press Ctrl+R to restart all services without closing terminal

# Get project root (one level up from STARTUP directory)
$scriptPath = Split-Path -Parent $PSScriptRoot
$ErrorActionPreference = 'Continue'

# Global variables for job management
$script:backendJob = $null
$script:frontendJob = $null

function Start-Services {
    param([string]$path)
    
    Write-Host '========================================' -ForegroundColor Cyan
    Write-Host 'ML Service 0.11.2 - Starting Services' -ForegroundColor Cyan
    Write-Host '========================================' -ForegroundColor Cyan
    Write-Host 'Backend:  http://localhost:8085' -ForegroundColor Green
    Write-Host 'Frontend: http://localhost:6565' -ForegroundColor Green
    Write-Host 'Press Ctrl+R to restart services' -ForegroundColor Yellow
    Write-Host 'Press Ctrl+C to stop services' -ForegroundColor Yellow
    Write-Host '========================================' -ForegroundColor Cyan
    Write-Host ''
    
    # Stop existing services if any
    Stop-Services
    
    # Start backend
    $script:backendJob = Start-Job -ScriptBlock {
        param([string]$path)
        Set-Location "$path\backend"
        if (-not (Test-Path 'venv')) {
            python -m venv venv
        }
        & ".\venv\Scripts\Activate.ps1"
        pip install --prefer-binary --upgrade -r requirements.txt *>&1 | Out-Null
        python -m ml_service *>&1
    } -ArgumentList $path
    
    # Wait a bit before starting frontend
    Start-Sleep -Seconds 3
    
    # Start frontend
    $script:frontendJob = Start-Job -ScriptBlock {
        param([string]$path)
        Set-Location "$path\frontend"
        if (-not (Test-Path 'node_modules')) {
            npm install --legacy-peer-deps *>&1 | Out-Null
        }
        npm run dev *>&1
    } -ArgumentList $path
}

function Stop-Services {
    Write-Host 'Stopping services...' -ForegroundColor Yellow
    
    # Stop backend job
    if ($script:backendJob -and $script:backendJob.State -eq 'Running') {
        Stop-Job -Job $script:backendJob -ErrorAction SilentlyContinue
        Remove-Job -Job $script:backendJob -ErrorAction SilentlyContinue
    }
    
    # Stop frontend job
    if ($script:frontendJob -and $script:frontendJob.State -eq 'Running') {
        Stop-Job -Job $script:frontendJob -ErrorAction SilentlyContinue
        Remove-Job -Job $script:frontendJob -ErrorAction SilentlyContinue
    }
    
    # Kill any remaining Python processes running ml_service
    Get-Process | Where-Object { $_.ProcessName -eq 'python' -or $_.ProcessName -eq 'pythonw' } | ForEach-Object {
        try {
            $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine
            if ($cmdLine -and $cmdLine -like "*ml_service*") {
                Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
            }
        } catch {}
    }
    
    # Kill any remaining Node processes running next on port 6565
    $nodeProcesses = Get-Process | Where-Object { $_.ProcessName -eq 'node' }
    foreach ($proc in $nodeProcesses) {
        try {
            $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($proc.Id)").CommandLine
            if ($cmdLine -and ($cmdLine -like "*next*" -or $cmdLine -like "*6565*")) {
                Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            }
        } catch {}
    }
    
    Start-Sleep -Seconds 1
}

# Start services
Start-Services -path $scriptPath

try {
    # Main monitoring loop - prioritize log output, check keys less frequently
    $lastKeyCheck = Get-Date
    $keyCheckInterval = 200  # Check keys every 200ms to avoid blocking
    
    while ($true) {
        # First, display all available logs (this is non-blocking)
        $hasOutput = $false
        
        if ($script:backendJob -and $script:backendJob.State -eq 'Running') {
            $backendOutput = Receive-Job -Job $script:backendJob -ErrorAction SilentlyContinue
            if ($backendOutput) {
                $hasOutput = $true
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
        }
        
        if ($script:frontendJob -and $script:frontendJob.State -eq 'Running') {
            $frontendOutput = Receive-Job -Job $script:frontendJob -ErrorAction SilentlyContinue
            if ($frontendOutput) {
                $hasOutput = $true
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
        }
        
        # Check for keyboard input only if no output was processed and enough time passed
        # This prevents blocking when there are logs to display
        $now = Get-Date
        if (-not $hasOutput -and (($now - $lastKeyCheck).TotalMilliseconds -ge $keyCheckInterval)) {
            $lastKeyCheck = $now
            try {
                # Only check if key is available (non-blocking check)
                if ($Host.UI.RawUI.KeyAvailable) {
                    $key = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
                    # Check for Ctrl+R
                    $isCtrl = ($key.ControlKeyState -band 8) -or ($key.ControlKeyState -band 4)
                    if (($key.Character -eq 'r' -or $key.Character -eq 'R') -and $isCtrl) {
                        Write-Host '' -ForegroundColor Cyan
                        Write-Host 'Ctrl+R detected - Restarting services...' -ForegroundColor Cyan
                        Write-Host '' -ForegroundColor Cyan
                        Stop-Services
                        Start-Sleep -Seconds 2
                        Start-Services -path $scriptPath
                        $lastKeyCheck = Get-Date
                        continue
                    }
                }
            } catch {
                # Try alternative method if RawUI fails
                try {
                    if ([Console]::KeyAvailable) {
                        $key = [Console]::ReadKey($true)
                        if ($key.Modifiers -eq [ConsoleModifiers]::Control -and $key.Key -eq 'R') {
                            Write-Host '' -ForegroundColor Cyan
                            Write-Host 'Ctrl+R detected - Restarting services...' -ForegroundColor Cyan
                            Write-Host '' -ForegroundColor Cyan
                            Stop-Services
                            Start-Sleep -Seconds 2
                            Start-Services -path $scriptPath
                            $lastKeyCheck = Get-Date
                            continue
                        }
                    }
                } catch {
                    # Ignore errors - continue monitoring logs
                }
            }
        }
        
        # Check if services stopped
        if (($script:backendJob -and $script:backendJob.State -ne 'Running') -and 
            ($script:frontendJob -and $script:frontendJob.State -ne 'Running')) {
            break
        }
        
        # Short sleep - shorter when there's output, longer when waiting
        if ($hasOutput) {
            Start-Sleep -Milliseconds 10
        } else {
            Start-Sleep -Milliseconds 50
        }
    }
} finally {
    # Cleanup
    Stop-Services
    
    # Get remaining output
    if ($script:backendJob) {
        $remainingBackend = Receive-Job -Job $script:backendJob -ErrorAction SilentlyContinue
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
        Remove-Job -Job $script:backendJob -ErrorAction SilentlyContinue
    }
    
    if ($script:frontendJob) {
        $remainingFrontend = Receive-Job -Job $script:frontendJob -ErrorAction SilentlyContinue
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
        Remove-Job -Job $script:frontendJob -ErrorAction SilentlyContinue
    }
    
    Write-Host ''
    Write-Host 'Services stopped.' -ForegroundColor Red
}
