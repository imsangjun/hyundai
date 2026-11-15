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
    $laneModel = Join-Path $PSScriptRoot '.tools/vision-data/yolop-640-640.onnx'
    if (-not (Test-Path -LiteralPath $laneModel)) {
        New-Item -ItemType Directory -Force (Split-Path $laneModel) | Out-Null
        $download = "$laneModel.download"
        Invoke-WebRequest 'https://raw.githubusercontent.com/hustvl/YOLOP/main/weights/yolop-640-640.onnx' -OutFile $download
        if ((Get-FileHash -LiteralPath $download -Algorithm SHA256).Hash -ne 'CD66A3E0087A7258AE07768CC02CB742EED93865727AE4C9BAF969B8FA190696') {
            throw 'YOLOP model checksum differs from the verified model.'
        }
        Move-Item -LiteralPath $download -Destination $laneModel
    }
    $structuralModel = Join-Path $PSScriptRoot '.tools/vision-data/culane_res18.pth'
    if (-not (Test-Path -LiteralPath $structuralModel)) {
        $download = "$structuralModel.download"
        & $python -m gdown 1oEjJraFr-3lxhX_OXduAGFWalWa6Xh3W -O $download
        if ($LASTEXITCODE -ne 0) { throw 'UFLDv2 download failed.' }
        if ((Get-FileHash -LiteralPath $download -Algorithm SHA256).Hash -ne '956616371EE758551C455D28C1C8A9732B39D7FBD85BC70B9869424A5121F967') {
            throw 'UFLDv2 model checksum differs from the verified official model.'
        }
        Move-Item -LiteralPath $download -Destination $structuralModel
    }
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
