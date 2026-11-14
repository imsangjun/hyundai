param(
    [string]$Video,
    [string]$Config,
    [string]$Output = 'verification/vision',
    [ValidateSet('V1','V2','V3','V4')][string]$Node = 'V4',
    [int]$Seconds = 60,
    [string]$Replay,
    [switch]$InstallReplay
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $PSScriptRoot '.tools/vision-env/Scripts/python.exe'
if (-not $Replay) {
    if (-not $Video) { throw 'Provide -Video or -Replay.' }
    if (-not (Test-Path -LiteralPath $python)) {
        $env:UV_CACHE_DIR = Join-Path $PSScriptRoot '.tools/uv-cache'
        $env:UV_PYTHON_INSTALL_DIR = Join-Path $PSScriptRoot '.tools/python'
        & uv venv .tools/vision-env --python 3.11
        if ($LASTEXITCODE -ne 0) { throw 'Python setup failed.' }
    }
    $env:UV_CACHE_DIR = Join-Path $PSScriptRoot '.tools/uv-cache'
    & uv pip install --python $python -r vision/requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency setup failed.' }
    $analysisArgs = @('vision/analyze.py','--video',$Video,'--output',$Output,'--node',$Node,'--seconds',"$Seconds")
    if ($Config) { $analysisArgs += @('--config',$Config) }
    & $python @analysisArgs
    if ($LASTEXITCODE -ne 0) { throw 'Video analysis failed.' }
    $Replay = Join-Path $Output 'replay.json'
}
if ($InstallReplay) {
    $resolvedReplay = (Resolve-Path -LiteralPath $Replay).Path
    if ((Get-Item -LiteralPath $resolvedReplay).Length -gt 2000000) { throw 'Replay exceeds app size limit.' }
    & "$PSScriptRoot/Start-Pleos.ps1"
    $adb = Join-Path $env:LOCALAPPDATA 'Android/Sdk/platform-tools/adb.exe'
    $driverUser = (& $adb -s emulator-5554 shell am get-current-user).Trim()
    if ($LASTEXITCODE -ne 0 -or $driverUser -notmatch '^\d+$') { throw 'Unable to resolve Pleos driver profile.' }
    & $adb -s emulator-5554 push $resolvedReplay /data/local/tmp/mergewindow-vision.json
    if ($LASTEXITCODE -ne 0) { throw 'Replay transfer failed.' }
    & $adb -s emulator-5554 shell run-as com.mergewindow.app --user $driverUser mkdir -p files
    & $adb -s emulator-5554 shell run-as com.mergewindow.app --user $driverUser cp /data/local/tmp/mergewindow-vision.json files/vision-replay.json
    if ($LASTEXITCODE -ne 0) { throw 'Replay installation failed. Install the debug app with Run-App.ps1 first.' }
    & $adb -s emulator-5554 shell am start -n com.mergewindow.app/.MainActivity
    Write-Output 'Open demo settings and select YOLO analysis playback.'
}
