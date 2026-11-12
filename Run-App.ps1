param([switch]$SkipBuild)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:JAVA_HOME = 'C:\Program Files\Android\Android Studio\jbr'
if (-not $SkipBuild) {
    & "$PSScriptRoot\gradlew.bat" assembleDebug
    if ($LASTEXITCODE -ne 0) { throw 'Android build failed.' }
}
& "$PSScriptRoot\Start-Pleos.ps1"
$adb = Join-Path $env:LOCALAPPDATA 'Android\Sdk\platform-tools\adb.exe'
& $adb -s emulator-5554 install -r "$PSScriptRoot\app\build\outputs\apk\debug\app-debug.apk"
if ($LASTEXITCODE -ne 0) { throw 'APK installation failed.' }
& $adb -s emulator-5554 shell am start -n com.mergewindow.app/.MainActivity
if ($LASTEXITCODE -ne 0) { throw 'Activity launch failed.' }
