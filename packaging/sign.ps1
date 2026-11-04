# Sign dist\ZhaoZhaoRecord.exe with Authenticode and verify the result.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File packaging\sign.ps1 -Path dist\ZhaoZhaoRecord.exe -PfxPath C:\keys\zhao.pfx
#   powershell -ExecutionPolicy Bypass -File packaging\sign.ps1 -Path dist\ZhaoZhaoRecord.exe -CertThumbprint 1A2B3C...
#
# The PFX password can be supplied with -PfxPassword or the ZSIGN_PFX_PASSWORD
# environment variable (preferred: command lines are visible to other processes).
# Pass -TimestampUrl none to skip RFC 3161 timestamping (offline builds only).
param(
    [Parameter(Mandatory = $true)][string]$Path,
    [string]$PfxPath,
    [string]$PfxPassword,
    [string]$CertThumbprint,
    [string]$TimestampUrl = "http://timestamp.digicert.com"
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path $Path)) { throw "File not found: $Path" }
$Path = (Resolve-Path $Path).Path
if (-not $PfxPassword) { $PfxPassword = $env:ZSIGN_PFX_PASSWORD }
if ($TimestampUrl -eq "none") { $TimestampUrl = "" }
if (-not $PfxPath -and -not $CertThumbprint) {
    throw "Provide -PfxPath (optionally -PfxPassword) or -CertThumbprint to select the signing certificate."
}

function Find-SignTool {
    $cmd = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $roots = @("$env:ProgramFiles(x86)\Windows Kits\10\bin", "$env:ProgramFiles\Windows Kits\10\bin")
    foreach ($root in $roots) {
        if (-not (Test-Path $root)) { continue }
        $hit = Get-ChildItem -Path $root -Filter signtool.exe -Recurse -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -match '\\x64\\signtool\.exe$' } |
            Sort-Object FullName -Descending | Select-Object -First 1
        if ($hit) { return $hit.FullName }
    }
    return $null
}

$signtool = Find-SignTool
if ($signtool) {
        Write-Output "Using signtool: $signtool"
        $signArgs = @("sign", "/fd", "sha256", "/a")
        if ($PfxPath) {
            $signArgs += @("/f", (Resolve-Path $PfxPath).Path)
            if ($PfxPassword) { $signArgs += @("/p", $PfxPassword) }
        }
        else {
            $signArgs += @("/sha1", $CertThumbprint, "/s", "My")
        }
        if ($TimestampUrl) { $signArgs += @("/tr", $TimestampUrl, "/td", "sha256") }
        $signArgs += $Path
        & $signtool @signArgs
        if ($LASTEXITCODE -ne 0) { throw "signtool failed with exit code $LASTEXITCODE" }
    }
    else {
        Write-Warning "signtool.exe not found (PATH / Windows Kits). Falling back to Set-AuthenticodeSignature."
        if ($PfxPath) {
            # Load the key pair straight from the PFX instead of importing it: an
            # import persists the private key in the store, and cleaning it up
            # afterwards would also delete a pre-existing copy of the same cert.
            $flags = [System.Security.Cryptography.X509Certificates.X509KeyStorageFlags]::EphemeralKeySet
            $cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2((Resolve-Path $PfxPath).Path, $PfxPassword, $flags)
        }
        else {
            $cert = Get-Item ("Cert:\CurrentUser\My\" + $CertThumbprint)
        }
        if (-not $cert) { throw "Certificate not found: $CertThumbprint" }
        $signParams = @{ FilePath = $Path; Certificate = $cert; HashAlgorithm = "SHA256" }
        if ($TimestampUrl) { $signParams["TimestampServer"] = $TimestampUrl }
        $result = Set-AuthenticodeSignature @signParams
        if ($result.SignatureType -eq "None") { throw "Signing failed: $($result.StatusMessage)" }
    }

    $check = Get-AuthenticodeSignature -FilePath $Path
    if ($check.SignatureType -eq "None") { throw "No signature found after signing." }
    Write-Output ("signature: " + $check.SignatureType + " / " + $check.Status)
    if ($check.SignerCertificate) { Write-Output ("signer:    " + $check.SignerCertificate.Subject) }
    if ($check.TimeStamperCertificate) { Write-Output "timestamp: yes" } else { Write-Output "timestamp: no" }
    if ($check.Status -ne "Valid") {
        Write-Warning ("Signature status is " + $check.Status + ": " + $check.StatusMessage)
        Write-Warning "A self-signed or test certificate reports UnknownError because its root is not trusted; a CA-issued certificate should report Valid."
    }
