$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Wymagany Python 3.12 x64.' }
}
& .venv/Scripts/python.exe -m pip install -r requirements-lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Instalacja zależności nie powiodła się.' }
& .venv/Scripts/python.exe -m unittest discover -s tests
if ($LASTEXITCODE -ne 0) { throw 'Testy nie powiodły się.' }
& .venv/Scripts/python.exe -m PyInstaller --noconfirm ListenActive.spec
if ($LASTEXITCODE -ne 0) { throw 'Budowanie aplikacji nie powiodło się.' }
& .venv/Scripts/python.exe collect_licenses.py
if ($LASTEXITCODE -ne 0) { throw 'Nie udało się zebrać licencji.' }
Compress-Archive -Path dist/ListenActive -DestinationPath dist/ListenActive-Windows-x64.zip -Force
$releaseHash = (Get-FileHash -LiteralPath dist/ListenActive-Windows-x64.zip -Algorithm SHA256).Hash.ToLowerInvariant()
"$releaseHash  ListenActive-Windows-x64.zip" | Set-Content -LiteralPath dist/SHA256SUMS.txt
