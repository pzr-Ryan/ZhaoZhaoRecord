param(
    [switch]$SkipInstall,
    [switch]$Sign,
    [string]$PfxPath,
    [string]$PfxPassword,
    [string]$CertThumbprint,
    [string]$TimestampUrl = "http://timestamp.digicert.com"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if ($Sign -and -not $PfxPath -and -not $CertThumbprint) {
    throw "Signing requested but no certificate given: use -PfxPath (optionally -PfxPassword) or -CertThumbprint."
}

$tools = Join-Path $root ".tools\pyinstaller"
$pyiPackage = Join-Path $tools "PyInstaller"
if (-not $SkipInstall -and -not (Test-Path $pyiPackage)) {
    Write-Output "Installing PyInstaller 6.22.3 into .tools\pyinstaller ..."
    python -m pip install --disable-pip-version-check --no-cache-dir --target $tools pyinstaller==6.22.3
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller installation failed" }
}

$env:PYTHONPATH = $tools
Write-Output "Building ZhaoZhaoRecord.exe ..."
python -m PyInstaller --noconfirm --clean packaging\ZhaoZhaoRecord.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }

$exe = Join-Path $root "dist\ZhaoZhaoRecord.exe"
if (-not (Test-Path $exe)) { throw "Missing build output: $exe" }

if ($Sign) {
    Write-Output "Signing ZhaoZhaoRecord.exe ..."
    & (Join-Path $PSScriptRoot "sign.ps1") -Path $exe -PfxPath $PfxPath -PfxPassword $PfxPassword -CertThumbprint $CertThumbprint -TimestampUrl $TimestampUrl
    if ($LASTEXITCODE -ne 0) { throw "Code signing failed" }
}

$zip = Join-Path $root "dist\ZhaoZhaoRecord-1.0.0-win64.zip"
Compress-Archive -Path $exe -DestinationPath $zip -Force

$lines = @()
foreach ($file in @($exe, $zip)) {
    $hash = (Get-FileHash -Algorithm SHA256 -Path $file).Hash.ToLower()
    $lines += ("{0}  {1}" -f $hash, [System.IO.Path]::GetFileName($file))
}
$lines | Set-Content -Path (Join-Path $root "dist\SHA256SUMS.txt") -Encoding Ascii

Write-Output ("exe:    " + $exe + " (" + [math]::Round((Get-Item $exe).Length / 1MB, 2) + " MB)")
Write-Output ("zip:    " + $zip + " (" + [math]::Round((Get-Item $zip).Length / 1MB, 2) + " MB)")
Write-Output "hashes: dist\SHA256SUMS.txt"
