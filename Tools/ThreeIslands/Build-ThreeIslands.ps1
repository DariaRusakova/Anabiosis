param(
    [string]$EngineRoot = '',
    [switch]$NoOpen
)
$ErrorActionPreference = 'Stop'

try {
    $projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
    $projectFile = Join-Path $projectRoot 'Anabiosis.uproject'
    $projectInfo = Get-Content -LiteralPath $projectFile -Raw | ConvertFrom-Json
    $pythonFile = Join-Path $projectRoot 'Content\Python\build_three_islands.py'
    $reportPath = Join-Path $projectRoot 'Saved\ThreeIslands\latest_build.json'
    $logPath = Join-Path $projectRoot 'Saved\ThreeIslands\UnrealBuild.log'
    New-Item -ItemType Directory -Force (Split-Path $reportPath) | Out-Null

    # Honour the exact registered engine associated with this project first.
    $candidates = New-Object 'System.Collections.Generic.List[string]'
    if ($EngineRoot) { $candidates.Add($EngineRoot) }
    $association = [string]$projectInfo.EngineAssociation
    $customBuilds = 'HKCU:\Software\Epic Games\Unreal Engine\Builds'
    if (Test-Path $customBuilds) {
        $builds = Get-ItemProperty $customBuilds
        $property = $builds.PSObject.Properties[$association]
        if ($property -and $property.Value) { $candidates.Add([string]$property.Value) }
    }
    foreach ($key in @(
        "HKLM:\SOFTWARE\EpicGames\Unreal Engine\$association",
        'HKLM:\SOFTWARE\EpicGames\Unreal Engine\5.7'
    )) {
        if (Test-Path $key) {
            $installed = Get-ItemProperty $key
            if ($installed.InstalledDirectory) { $candidates.Add([string]$installed.InstalledDirectory) }
        }
    }
    if ($env:ProgramFiles) { $candidates.Add((Join-Path $env:ProgramFiles 'Epic Games\UE_5.7')) }

    $engineDirectory = $null
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath (Join-Path $candidate 'Engine\Binaries\Win64\UnrealEditor.exe')) {
            $engineDirectory = $candidate
            break
        }
    }
    if (-not $engineDirectory) {
        Write-Host 'The engine associated with this project was not found automatically.'
        $engineDirectory = Read-Host 'Enter the UE 5.7.4 engine root (the folder containing Engine)'
        $engineDirectory = $engineDirectory.Trim('"')
    }
    $editor = Join-Path $engineDirectory 'Engine\Binaries\Win64\UnrealEditor.exe'
    $editorCmd = Join-Path $engineDirectory 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe'
    $buildVersion = Join-Path $engineDirectory 'Engine\Build\Build.version'
    if (-not (Test-Path -LiteralPath $editor) -or -not (Test-Path -LiteralPath $editorCmd)) {
        throw 'Cannot find UnrealEditor.exe and UnrealEditor-Cmd.exe under that engine root.'
    }
    if (Test-Path -LiteralPath $buildVersion) {
        $version = Get-Content -LiteralPath $buildVersion -Raw | ConvertFrom-Json
        if ($version.MajorVersion -ne 5 -or $version.MinorVersion -ne 7) {
            throw 'This project and level builder require Unreal Engine 5.7.x.'
        }
    }

    $running = Get-Process -Name 'UnrealEditor','UnrealEditor-Cmd' -ErrorAction SilentlyContinue
    if ($running) {
        throw 'Save your work and close Unreal Editor before starting this separate build process.'
    }
    # This is an existing C++ template project. A copied checkout can have no
    # ignored Binaries folder yet; build its unchanged editor module if needed.
    $projectModule = Join-Path $projectRoot 'Binaries\Win64\UnrealEditor-Anabiosis.dll'
    if (-not (Test-Path -LiteralPath $projectModule)) {
        $buildBat = Join-Path $engineDirectory 'Engine\Build\BatchFiles\Build.bat'
        if (-not (Test-Path -LiteralPath $buildBat)) {
            throw 'The project editor module is absent. Open/build Anabiosis in Windows first, then retry.'
        }
        Write-Host 'Building the existing AnabiosisEditor module with the installed Windows toolchain...'
        & $buildBat 'AnabiosisEditor' 'Win64' 'Development' "-Project=$projectFile" '-WaitMutex' '-NoHotReloadFromIDE'
        if ($LASTEXITCODE -ne 0) {
            throw 'The existing C++ editor module could not compile. Build/open the original project in Windows, then retry. No map has been changed.'
        }
    }
    Write-Host 'Creating a NEW numbered three-island map. Existing maps will be preserved.'
    Write-Host "Engine: $engineDirectory"
    Write-Host "Build log: $logPath"
    Write-Host 'Shader compilation can take several minutes on the first run.'
    $env:THREE_ISLANDS_RUN_ID = [Guid]::NewGuid().ToString()

    # Full editor mode deliberately loads project content before executing Python.
    # Epic's -ExecutePythonScript mode exits after the script; then open its saved map.
    $buildProcessInfo = New-Object System.Diagnostics.ProcessStartInfo
    $buildProcessInfo.FileName = $editorCmd
    $buildProcessInfo.Arguments = '"' + $projectFile + '" -ExecutePythonScript="' + $pythonFile + `
        '" -unattended -nop4 -nosplash -stdout -FullStdOutLogOutput -abslog="' + $logPath + '"'
    $buildProcessInfo.WorkingDirectory = $projectRoot
    $buildProcessInfo.UseShellExecute = $false
    $buildProcess = [System.Diagnostics.Process]::Start($buildProcessInfo)
    $buildProcess.WaitForExit()
    $engineExitCode = $buildProcess.ExitCode
    if (-not (Test-Path -LiteralPath $reportPath)) {
        throw "Unreal did not run the script (exit $engineExitCode). Open the project normally and check its C++ modules, then retry. Log: $logPath"
    }
    $report = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
    if ($report.run_id -ne $env:THREE_ISLANDS_RUN_ID) {
        throw "The report belongs to an older build. Unreal did not execute this run. Log: $logPath"
    }
    if ($engineExitCode -ne 0 -or -not $report.success) {
        if ($report.error) { Write-Host $report.error -ForegroundColor Red }
        throw "Map build failed (exit $engineExitCode). See: $reportPath and $logPath"
    }
    $mapFile = Join-Path $projectRoot ('Content\' + $report.map.Substring(6).Replace('/','\') + '.umap')
    if (-not (Test-Path -LiteralPath $mapFile)) {
        throw "Unreal reported success, but the saved map file is absent: $mapFile"
    }
    Write-Host "Saved: $($report.map)" -ForegroundColor Green
    Write-Host "Mesh actors: $($report.piece_count); actual collision trace checks: $($report.collision_trace_checks)"
    if (-not $NoOpen) {
        # ProcessStartInfo's argument string keeps paths with spaces quoted on PS 5.1.
        $startInfo = New-Object System.Diagnostics.ProcessStartInfo
        $startInfo.FileName = $editor
        $startInfo.Arguments = '"' + $projectFile + '" "' + $report.map + '"'
        $startInfo.WorkingDirectory = $projectRoot
        [System.Diagnostics.Process]::Start($startInfo) | Out-Null
    }
    exit 0
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
