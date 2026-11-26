[CmdletBinding()]
param(
    [string]$ConfigPath = (Join-Path $PSScriptRoot '..\postgres-test.local.psd1'),
    [switch]$UseExistingBuild,
    [switch]$QuickStart,
    [switch]$OpenBrowser,
    [ValidateRange(1024,65535)][int]$ApiPort = 8014,
    [ValidateRange(1024,65535)][int]$WebPort = 5176
)

$ErrorActionPreference = 'Stop'
$backend = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$frontend = (Resolve-Path (Join-Path $backend '..\frontend')).Path
$python = Join-Path $backend '.venv\Scripts\python.exe'
$pytest = Join-Path $backend '.venv\Scripts\pytest.exe'
$apiUrl = "http://localhost:$ApiPort"
$webUrl = "http://localhost:$WebPort"
function Open-DemoBrowser {
    try { Start-Process $webUrl }
    catch { Write-Warning "Não foi possível abrir o navegador automaticamente. Acesse $webUrl." }
}
if (!(Test-Path -LiteralPath $ConfigPath)) { throw 'Configuração de teste ausente: backend/postgres-test.local.psd1.' }
$config = Import-PowerShellDataFile -LiteralPath $ConfigPath
if ($config.Database -cne 'triton_integration_test' -or $config.Username -cne 'triton_integration_test' -or $config.Host -notin @('127.0.0.1', 'localhost', '::1')) {
    throw 'A demonstração exige a conta e o banco triton_integration_test em endereço local.'
}
if ($QuickStart) {
    try {
        $existingPage = Invoke-WebRequest "$webUrl/" -UseBasicParsing -TimeoutSec 10
        $existingHealth = Invoke-RestMethod "$apiUrl/health" -TimeoutSec 10
        if ($existingPage.StatusCode -eq 200 -and $existingHealth.status -eq 'ok') {
            $asset = [regex]::Match($existingPage.Content, 'src="([^"]+\.js)"').Groups[1].Value
            if (!$asset) { throw 'Não foi possível identificar a interface existente.' }
            $existingBundle = Invoke-WebRequest ($webUrl + $asset) -UseBasicParsing -TimeoutSec 5
            $probeSession = New-Object Microsoft.PowerShell.Commands.WebRequestSession
            $probeBody = @{email='demo@example.com';password='Triton-Demo-2026!'} | ConvertTo-Json
            $probe = Invoke-RestMethod "$apiUrl/auth/login" -Method Post -ContentType 'application/json' -Body $probeBody -WebSession $probeSession -TimeoutSec 5
            $probeProperties = Invoke-RestMethod "$apiUrl/properties" -WebSession $probeSession -TimeoutSec 5
            if (!$existingBundle.Content.Contains($apiUrl) -or $probe.email -ne 'demo@example.com' -or @($probeProperties).Count -lt 1) { throw 'A interface ou a API existentes não correspondem à demonstração.' }
            Write-Output 'Demonstração já está aberta e respondeu ao login e à consulta de propriedades.'
            if ($OpenBrowser) { Open-DemoBrowser }
            return
        }
    } catch { }
}
foreach ($port in @($ApiPort, $WebPort)) {
    $socket = [System.Net.Sockets.TcpClient]::new()
    try { $socket.Connect('127.0.0.1', $port); throw "Porta $port ocupada; nenhum processo foi encerrado." }
    catch [System.Net.Sockets.SocketException] { }
    finally { $socket.Dispose() }
}
$secretPath = Join-Path $backend 'postgres-test.secret'
if ($QuickStart -and (Test-Path -LiteralPath $secretPath)) {
    try { $password = Get-Content -LiteralPath $secretPath -Raw | ConvertTo-SecureString }
    catch { throw 'Não foi possível acessar a credencial local protegida do PostgreSQL.' }
} else {
    $password = Read-Host 'Senha local da role PostgreSQL de teste' -AsSecureString
}
$plainPassword = [System.Net.NetworkCredential]::new('', $password).Password
$encodedPassword = [System.Uri]::EscapeDataString($plainPassword)
$encodedUser = [System.Uri]::EscapeDataString([string]$config.Username)
$url = "postgresql+psycopg://${encodedUser}:${encodedPassword}@$($config.Host):$([int]$config.Port)/$($config.Database)"
$names = @('DATABASE_URL','TRITON_TEST_DATABASE_URL','TRITON_TEST_TMP_ROOT','APP_ENV','CORS_ORIGINS','COOKIE_NAME','MEDIA_STORAGE_DIRECTORY','VITE_API_BASE_URL')
$saved = @{}
foreach ($name in $names) { $saved[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
$oldLocation = Get-Location
$runId = [guid]::NewGuid().ToString('N')
$runDir = Join-Path $backend ".tmp\demo-$runId"
$testDir = Join-Path $backend ".tmp\postgres-test-$runId"
$api = $null
$web = $null
New-Item -ItemType Directory -Path $runDir, $testDir -Force | Out-Null
try {
    $env:DATABASE_URL = $url
    $env:TRITON_TEST_DATABASE_URL = $url
    $env:TRITON_TEST_TMP_ROOT = $testDir
    $env:APP_ENV = 'test'
    $env:CORS_ORIGINS = $webUrl
    $env:COOKIE_NAME = 'triton_demo_session'
    $privateRoot = Join-Path $backend 'private_demo_uploads'
    New-Item -ItemType Directory -Path $privateRoot -Force | Out-Null
    # Copy previous private files into the stable store, retaining originals.
    foreach ($oldRun in Get-ChildItem (Join-Path $backend '.tmp') -Directory -Filter 'demo-*') {
        $oldRoot = Join-Path $oldRun.FullName 'private_uploads'
        if (!(Test-Path -LiteralPath $oldRoot)) { continue }
        foreach ($file in Get-ChildItem -LiteralPath $oldRoot -File -Recurse) {
            $relative = $file.FullName.Substring($oldRoot.Length).TrimStart('\','/')
            $destination = Join-Path $privateRoot $relative
            if (Test-Path -LiteralPath $destination) {
                if ((Get-FileHash -LiteralPath $file.FullName).Hash -ne (Get-FileHash -LiteralPath $destination).Hash) { throw 'Arquivos privados com o mesmo nome e conteúdos diferentes; cópia interrompida para revisão.' }
            } else {
                New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
                Copy-Item -LiteralPath $file.FullName -Destination $destination
            }
        }
    }
    $env:MEDIA_STORAGE_DIRECTORY = $privateRoot
    $env:VITE_API_BASE_URL = $apiUrl
    Set-Location -LiteralPath $backend
    & $python scripts/postgres_test_support.py verify
    if ($LASTEXITCODE -ne 0) { throw 'Esquema de teste não verificado. Execute a validação PostgreSQL antes da demonstração.' }
    if (!$QuickStart) {
        & $pytest tests/test_api.py -q -p no:tmpdir -p no:cacheprovider
        if ($LASTEXITCODE -ne 0) { throw 'Testes PostgreSQL falharam; demonstração não iniciada.' }
    }
    & $python scripts/load_demo.py
    if ($LASTEXITCODE -ne 0) { throw 'Carga de demonstração falhou; API não iniciada.' }
    Set-Location -LiteralPath $frontend
    $buildDir = Join-Path $runDir 'frontend'
    $existing = Join-Path $frontend 'dist'
    $index = Join-Path $existing 'index.html'
    $canReuseBuild = $false
    if ($UseExistingBuild -and (Test-Path -LiteralPath $index)) {
        $buildTime = (Get-Item -LiteralPath $index).LastWriteTimeUtc
        $sources = @(Get-ChildItem (Join-Path $frontend 'src') -File -Recurse) + @(Get-Item (Join-Path $frontend 'package.json'), (Join-Path $frontend 'package-lock.json'), (Join-Path $frontend 'vite.config.js'))
        $canReuseBuild = @($sources | Where-Object { $_.LastWriteTimeUtc -gt $buildTime }).Count -eq 0
    }
    if ($canReuseBuild) {
        New-Item -ItemType Directory -Path $buildDir -Force | Out-Null
        Copy-Item -Path (Join-Path $existing '*') -Destination $buildDir -Recurse
        $changed = 0
        foreach ($file in Get-ChildItem (Join-Path $buildDir 'assets') -Filter '*.js' -File) {
            $content = [IO.File]::ReadAllText($file.FullName)
            if ($content.Contains('http://localhost:8013')) {
                [IO.File]::WriteAllText($file.FullName, $content.Replace('http://localhost:8013', $apiUrl), [Text.UTF8Encoding]::new($false))
                $changed++
            }
        }
        if ($changed -ne 1) { throw 'Não foi possível identificar a URL da API no build existente.' }
        Write-Output 'Build existente copiado para a demonstração; URL da API ajustada somente na cópia.'
    } else {
        & npm.cmd run build -- --outDir $buildDir
        if ($LASTEXITCODE -ne 0) { throw 'Build do front-end falhou; API não iniciada.' }
    }
    $api = Start-Process -FilePath $python -ArgumentList "-m uvicorn app.main:app --host 127.0.0.1 --port $ApiPort" -WorkingDirectory $backend -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runDir 'api.out.log') -RedirectStandardError (Join-Path $runDir 'api.err.log')
    Start-Sleep -Seconds 3
    if ($api.HasExited) { throw "API de demonstração não iniciou. Consulte $runDir\api.err.log." }
    $session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
    $body = @{email='demo@example.com'; password='Triton-Demo-2026!'} | ConvertTo-Json
    try {
        $preflight = Invoke-WebRequest "$apiUrl/auth/login" -Method Options -Headers @{Origin=$webUrl; 'Access-Control-Request-Method'='POST'; 'Access-Control-Request-Headers'='content-type'} -UseBasicParsing
        if ($preflight.Headers['Access-Control-Allow-Origin'] -ne $webUrl -or $preflight.Headers['Access-Control-Allow-Credentials'] -ne 'true') { throw 'CORS da demonstração não está configurado corretamente.' }
        $login = Invoke-RestMethod "$apiUrl/auth/login" -Method Post -ContentType 'application/json' -Body $body -WebSession $session
        $properties = Invoke-RestMethod "$apiUrl/properties" -WebSession $session
        if (@($properties).Count -lt 1) { throw 'Nenhuma propriedade demonstrativa retornada.' }
        $arguments = '-m http.server {0} --bind 127.0.0.1 --directory "{1}"' -f $WebPort, $buildDir
        $web = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $frontend -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runDir 'web.out.log') -RedirectStandardError (Join-Path $runDir 'web.err.log')
        Start-Sleep -Seconds 2
        if ($web.HasExited) { throw "Servidor da interface não iniciou. Consulte $runDir\web.err.log." }
        $page = Invoke-WebRequest "$webUrl/" -UseBasicParsing
        if ($page.StatusCode -ne 200) { throw 'Interface demonstrativa indisponível.' }
    } catch {
        if ($web -and !$web.HasExited) { Stop-Process -Id $web.Id }
        if ($api -and !$api.HasExited) { Stop-Process -Id $api.Id }
        throw
    }
    Write-Output "Demonstração sintética disponível em $webUrl"
    Write-Output 'Login: demo@example.com / Triton-Demo-2026!'
    Write-Output "Processos desta demonstração: API=$($api.Id), interface=$($web.Id). Banco: triton_integration_test."
    Write-Output 'Fontes externas e medições reais não foram validadas por esta carga.'
    if ($OpenBrowser) { Open-DemoBrowser }
} finally {
    Set-Location -LiteralPath $oldLocation
    foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name, $saved[$name], 'Process') }
    $plainPassword = $null; $encodedPassword = $null; $url = $null
    $password.Dispose()
}
