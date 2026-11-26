[CmdletBinding()]
param(
    [string]$ConfigPath = (Join-Path $PSScriptRoot '..\postgres-test.local.psd1'),
    [switch]$VerifyOnly
)

$ErrorActionPreference = 'Stop'
$backendRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $backendRoot '.venv\Scripts\python.exe'
$alembic = Join-Path $backendRoot '.venv\Scripts\alembic.exe'
$support = Join-Path $PSScriptRoot 'postgres_test_support.py'
$pytest = Join-Path $backendRoot '.venv\Scripts\pytest.exe'

if (!(Test-Path -LiteralPath $ConfigPath)) {
    throw "Configuração não encontrada: $ConfigPath. Copie backend/postgres-test.example.psd1 para backend/postgres-test.local.psd1 e preencha apenas host, porta, banco e role."
}
if (!(Test-Path -LiteralPath $python) -or !(Test-Path -LiteralPath $alembic) -or !(Test-Path -LiteralPath $pytest)) {
    throw 'O ambiente virtual backend/.venv precisa conter Python, Alembic e pytest.'
}

$config = Import-PowerShellDataFile -LiteralPath $ConfigPath
if ($config.Database -cne 'triton_integration_test') {
    throw 'Execução recusada: o banco deve ser exatamente triton_integration_test; o banco triton nunca é permitido.'
}
if ($config.Host -notin @('127.0.0.1', 'localhost', '::1')) {
    throw 'Execução recusada: use somente host local (127.0.0.1, localhost ou ::1).'
}
if ([int]$config.Port -lt 1 -or [int]$config.Port -gt 65535 -or [string]::IsNullOrWhiteSpace([string]$config.Username)) {
    throw 'Host, porta ou role de teste inválidos na configuração.'
}

$securePassword = Read-Host 'Senha local da role PostgreSQL de teste' -AsSecureString
$plainPassword = [System.Net.NetworkCredential]::new('', $securePassword).Password
$encodedUser = [System.Uri]::EscapeDataString([string]$config.Username)
$encodedPassword = [System.Uri]::EscapeDataString($plainPassword)
$databaseUrl = "postgresql+psycopg://${encodedUser}:${encodedPassword}@$($config.Host):$([int]$config.Port)/$($config.Database)"

$environmentNames = @('DATABASE_URL', 'TRITON_TEST_DATABASE_URL', 'TRITON_TEST_TMP_ROOT', 'APP_ENV')
$oldEnvironment = @{}
foreach ($name in $environmentNames) {
    $item = Get-Item -Path "Env:$name" -ErrorAction SilentlyContinue
    if ($null -ne $item) { $oldEnvironment[$name] = @{ Exists = $true; Value = $item.Value } }
    else { $oldEnvironment[$name] = @{ Exists = $false; Value = $null } }
}
$oldLocation = Get-Location
$testTmpRoot = Join-Path (Join-Path $backendRoot '.tmp') ('postgres-test-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $testTmpRoot -Force | Out-Null

try {
    $env:DATABASE_URL = $databaseUrl
    $env:TRITON_TEST_DATABASE_URL = $databaseUrl
    $env:TRITON_TEST_TMP_ROOT = $testTmpRoot
    $env:APP_ENV = 'test'
    Set-Location -LiteralPath $backendRoot

    $state = (& $python $support state | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Não foi possível ler a revisão Alembic do banco de teste.' }
    Write-Output "Banco de teste confirmado; estado inicial: $state"
    $allowed = @('empty', '0006_nullable_interval_volume', '0007_integration_history', '0008_proven_intervals', '0009_property_archive_tariff_source', '0010_period_constraints', '0011_meter_coordinates')
    if ($state -notin $allowed) { throw "Revisão não permitida para o teste: $state" }

    if ($VerifyOnly) {
        & $python $support verify
        if ($LASTEXITCODE -ne 0) { throw 'Verificação do esquema falhou; veja os detalhes acima.' }
        return
    }

    if ($state -eq 'empty') {
        & $alembic upgrade 0006_nullable_interval_volume
        if ($LASTEXITCODE -ne 0) { throw 'Migração até 0006 falhou; o banco foi mantido para inspeção.' }
    }

    & $python $support seed
    if ($LASTEXITCODE -ne 0) { throw 'Não foi possível preparar a fixture legada; nenhum registro foi removido.' }

    if ($state -ne '0011_meter_coordinates') {
        & $alembic upgrade 0011_meter_coordinates
        if ($LASTEXITCODE -ne 0) { throw 'Migração até 0011 falhou; o banco foi mantido para inspeção.' }
    }

    & $python $support verify
    if ($LASTEXITCODE -ne 0) { throw 'Verificação de revisão, esquema ou preservação falhou.' }

    & $pytest tests/test_api.py -q -p no:tmpdir
    if ($LASTEXITCODE -ne 0) { throw 'Testes autenticados da API com PostgreSQL falharam.' }
} finally {
    Set-Location -LiteralPath $oldLocation
    foreach ($name in $environmentNames) {
        if ($oldEnvironment[$name].Exists) { Set-Item -Path "Env:$name" -Value $oldEnvironment[$name].Value }
        else { Remove-Item -Path "Env:$name" -ErrorAction SilentlyContinue }
    }
    $plainPassword = $null
    $encodedPassword = $null
    $databaseUrl = $null
    $securePassword.Dispose()
}
