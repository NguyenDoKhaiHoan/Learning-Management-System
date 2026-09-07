param([switch]$UseWindowsCertificates)

$ErrorActionPreference = 'Stop'
$projectDirectory = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$buildArguments = @('build', '-t', 'lms-backend:local', '-f',
    (Join-Path $projectDirectory 'backend/Dockerfile'))

if ($UseWindowsCertificates) {
    # Public CA certificates are mounted at build time only, never saved in the image.
    $certificateFile = Join-Path ([System.IO.Path]::GetTempPath()) (
        'lms-build-ca-' + [guid]::NewGuid().ToString('N') + '.pem')
    $certificates = Get-ChildItem Cert:\CurrentUser\Root, Cert:\LocalMachine\Root |
        Sort-Object -Property Thumbprint -Unique
    $pemBlocks = foreach ($certificate in $certificates) {
        "-----BEGIN CERTIFICATE-----`n" +
        [Convert]::ToBase64String($certificate.RawData,
            [System.Base64FormattingOptions]::InsertLineBreaks) +
        "`n-----END CERTIFICATE-----`n"
    }
    [System.IO.File]::WriteAllText($certificateFile, ($pemBlocks -join ''),
        [System.Text.Encoding]::ASCII)
    $buildArguments += @('--secret', "id=pip_ca,src=$certificateFile")
}

try {
    $buildArguments += $projectDirectory
    & docker @buildArguments
    if ($LASTEXITCODE -ne 0) { throw "Docker build failed with exit code $LASTEXITCODE" }
}
finally {
    if ($UseWindowsCertificates -and (Test-Path -LiteralPath $certificateFile)) {
        Remove-Item -LiteralPath $certificateFile
    }
}
