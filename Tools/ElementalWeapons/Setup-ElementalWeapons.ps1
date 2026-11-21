param(
    [string]$EngineRoot = '',
    [switch]$NoOpen
)
$ErrorActionPreference = 'Stop'
try {
    $projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
    $projectFile = Join-Path $projectRoot 'Anabiosis.uproject'
    $projectInfo = Get-Content -LiteralPath $projectFile -Raw | ConvertFrom-Json
    $pythonFile = Join-Path $projectRoot 'Content\Python\setup_elemental_weapons.py'
    $reportPath = Join-Path $projectRoot 'Saved\ElementalWeapons\latest_setup.json'
    $logPath = Join-Path $projectRoot 'Saved\ElementalWeapons\UnrealSetup.log'
    $compileLog = Join-Path $projectRoot 'Saved\ElementalWeapons\Compile.log'
    New-Item -ItemType Directory -Force (Split-Path $reportPath) | Out-Null
    $env:ELEMENTAL_WEAPONS_RUN_ID = [Guid]::NewGuid().ToString()
    @{success=$false; run_id=$env:ELEMENTAL_WEAPONS_RUN_ID; phase='preflight'} |
        ConvertTo-Json | Set-Content -LiteralPath $reportPath -Encoding UTF8
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
        if ($version.MajorVersion -ne 5 -or $version.MinorVersion -ne 7 -or $version.PatchVersion -ne 4) {
            throw 'This setup requires the project-associated Unreal Engine 5.7.4.'
        }
    }

    $running = Get-Process -Name 'UnrealEditor','UnrealEditor-Cmd' -ErrorAction SilentlyContinue
    if ($running) {
        throw 'Save your work and close Unreal Editor before starting this separate build process.'
    }
    # New native classes require a build even when an older project DLL exists.
    $buildBat = Join-Path $engineDirectory 'Engine\Build\BatchFiles\Build.bat'
    if (-not (Test-Path -LiteralPath $buildBat)) { throw 'Build.bat is absent under the selected engine.' }
    Write-Host 'Building AnabiosisEditor. Uses the installed Visual Studio C++ and Windows SDK.'
    Write-Host "Compile log: $compileLog"
    & $buildBat 'AnabiosisEditor' 'Win64' 'Development' "-Project=$projectFile" '-WaitMutex' '-NoHotReloadFromIDE' 2>&1 |
        Tee-Object -FilePath $compileLog
    if ($LASTEXITCODE -ne 0) {
        throw "C++ build failed. No setup was run. See $compileLog (Visual Studio C++ toolchain and Windows SDK must already be installed)."
    }
    Write-Host 'Importing weapons and saving a NEW numbered copy of the player and map.'
    Write-Host "Unreal log: $logPath"
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = $editorCmd
    $info.Arguments = '"' + $projectFile + '" -ExecutePythonScript="' + $pythonFile + `
        '" -unattended -nop4 -nosplash -stdout -FullStdOutLogOutput -abslog="' + $logPath + '"'
    $info.WorkingDirectory = $projectRoot
    $info.UseShellExecute = $false
    $process = [System.Diagnostics.Process]::Start($info)
    $process.WaitForExit()
    if (-not (Test-Path -LiteralPath $reportPath)) { throw "No setup report. See $logPath" }
    $report = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
    if ($report.run_id -ne $env:ELEMENTAL_WEAPONS_RUN_ID) { throw "Stale setup report. See $logPath" }
    if ($process.ExitCode -ne 0 -or -not $report.success) {
        if ($report.error) { Write-Host $report.error -ForegroundColor Red }
        throw "Setup failed (exit $($process.ExitCode)). See $reportPath and $logPath"
    }
    if (-not $report.map -or -not $report.map.StartsWith('/Game/Weapons/Elemental/')) {
        throw 'The setup report does not contain a generated weapon map.'
    }
    $mapFile = Join-Path $projectRoot ('Content\' + $report.map.Substring(6).Replace('/','\') + '.umap')
    if (-not (Test-Path -LiteralPath $mapFile)) { throw "Reported map is missing: $mapFile" }
    Write-Host "Saved: $($report.map)" -ForegroundColor Green
    Write-Host 'Play: LMB attack, hold RMB aim, 1 flamethrower, 2 water pistol. WASD/look stay active.'
    if (-not $NoOpen) {
        $open = New-Object System.Diagnostics.ProcessStartInfo
        $open.FileName = $editor
        $open.Arguments = '"' + $projectFile + '" "' + $report.map + '"'
        $open.WorkingDirectory = $projectRoot
        [System.Diagnostics.Process]::Start($open) | Out-Null
    }
    exit 0
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
