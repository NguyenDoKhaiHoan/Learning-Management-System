# Download Linux amd64 / CPython 3.11 wheels using Windows system certificates.
$ErrorActionPreference = 'Stop'
$projectDirectory = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$python = Join-Path (Split-Path $projectDirectory -Parent) '.venv/Scripts/python.exe'
& $python -m pip download --use-feature=truststore --timeout 120 --retries 3 `
    --only-binary=:all: --no-deps `
    --platform manylinux2014_x86_64 --platform manylinux_2_28_x86_64 `
    --platform manylinux_2_34_x86_64 --python-version 311 --implementation cp --abi cp311 `
    -r (Join-Path $projectDirectory 'backend/requirements.runtime.lock.txt') `
    -d (Join-Path $projectDirectory 'backend/.wheels')
if ($LASTEXITCODE -ne 0) { throw 'Wheel download failed; retry to reuse the pip download cache.' }
