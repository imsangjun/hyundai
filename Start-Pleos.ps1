param(
    [string]$AvdName = 'MergeWindow_Pleos_2_1',
    [switch]$Headless
)

$ErrorActionPreference = 'Stop'
$sdkRoot = Join-Path $env:LOCALAPPDATA 'Android\Sdk'
$adb = Join-Path $sdkRoot 'platform-tools\adb.exe'
$emulator = Join-Path $sdkRoot 'emulator\emulator.exe'
$serial = 'emulator-5554'
if (-not (Test-Path -LiteralPath $emulator)) { throw "Android Emulator not found: $emulator" }
if ($AvdName -notin @(& $emulator -list-avds)) { throw "AVD not found: $AvdName" }

$state = & $adb -s $serial get-state 2>$null
if ($LASTEXITCODE -ne 0) {
    if (Get-NetTCPConnection -LocalPort 5554 -State Listen -ErrorAction SilentlyContinue) {
        throw 'Port 5554 is already occupied. Close the other emulator before continuing.'
    }
    $emulatorArgs = @('-avd', $AvdName, '-port', '5554', '-no-snapshot', '-gpu', 'host')
    if ($Headless) { $emulatorArgs += '-no-window' }
    Start-Process -FilePath $emulator -ArgumentList $emulatorArgs -WindowStyle Hidden | Out-Null
} elseif ($state -eq 'device') {
    $runningName = @(& $adb -s $serial emu avd name)[0]
    if ($runningName -ne $AvdName) { throw "Port 5554 belongs to another AVD: $runningName" }
} else {
    throw "Emulator is not ready: $state"
}

$deadline = (Get-Date).AddMinutes(5)
do {
    $boot = & $adb -s $serial shell getprop sys.boot_completed 2>$null
    if ($boot -eq '1') { break }
    Start-Sleep -Seconds 2
} while ((Get-Date) -lt $deadline)
if ($boot -ne '1') { throw 'Pleos did not finish booting within five minutes.' }

$expected = "$serial tcp:8088 tcp:8088"
if ($expected -notin @(& $adb forward --list)) {
    & $adb -s $serial forward --no-rebind tcp:8088 tcp:8088
    if ($LASTEXITCODE -ne 0) { throw 'Port 8088 is in use by another service.' }
}
Write-Output 'Pleos is ready. Virtual Console: http://127.0.0.1:8088/'
