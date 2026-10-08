$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
function Fail([string]$Message) { Write-Host $Message -ForegroundColor Red; exit 1 }
function Compose {
    & docker compose --project-directory $PSScriptRoot -f (Join-Path $PSScriptRoot 'compose.yaml') --env-file (Join-Path $PSScriptRoot '.env') @args
}
try {
    Write-Host '[1/6] Verificando Docker...'
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Fail 'Docker Desktop não foi encontrado. Consulte o README.' }
    & docker --version *> $null
    if ($LASTEXITCODE -ne 0) { Fail 'Docker Desktop não foi encontrado ou não está em execução.' }
    & docker compose version *> $null
    if ($LASTEXITCODE -ne 0) { Fail 'Docker Compose não foi encontrado. Consulte o README.' }
    & docker info *> $null
    if ($LASTEXITCODE -ne 0) { Fail 'Não foi possível acessar o Docker. Verifique se Docker Desktop está em execução, usando containers Linux.' }
    Write-Host '[2/6] Preparando configuração...'
    Write-Host 'As configurações serão solicitadas dentro do Docker após o build.'
    Write-Host '[3/6] Construindo aplicação e preparando modelos OCR. A primeira instalação pode demorar alguns minutos...'
    & docker build --tag corrigiai-local:latest .
    if ($LASTEXITCODE -ne 0) { Fail 'Não foi possível construir a aplicação.' }
    & docker run --rm -it --user root --mount "type=bind,source=$PSScriptRoot,target=/config" --entrypoint python corrigiai-local:latest scripts/install_common.py configure
    if ($LASTEXITCODE -ne 0) { Fail 'Não foi possível configurar o ambiente. Use um terminal interativo e confira os dados.' }
    Write-Host '[4/6] Iniciando serviços...'
    Compose up -d --no-build web *> $null
    if ($LASTEXITCODE -ne 0) { Fail 'Não foi possível iniciar os serviços. Confira .env, a porta 8000 e o Docker.' }
    Write-Host '[5/6] Preparando banco...'
    Compose exec -T web flask --app run.py init-db *> $null
    if ($LASTEXITCODE -ne 0) { Fail 'Não foi possível preparar o banco. Verifique DATABASE_URL e a conexão com o Supabase.' }
    Write-Host '[6/6] Verificando aplicação...'
    Compose exec -T web python scripts/install_common.py health *> $null
    if ($LASTEXITCODE -ne 0) { Fail 'A aplicação não respondeu dentro do tempo esperado. Diagnóstico: docker compose logs web (não compartilhe credenciais dos logs).' }
    Write-Host "`n========================================`n        corrigiAi instalado`n========================================"
    Write-Host 'Aplicação iniciada com sucesso.'
    Write-Host 'Acesso neste computador: http://localhost:8000'
    try {
        $addresses = @(Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq 'Up' } | ForEach-Object { $_.IPv4Address.IPAddress } | Select-Object -Unique)
        if ($addresses.Count -eq 1) { Write-Host "Possível acesso pelo celular na mesma rede: http://$($addresses[0]):8000" }
    } catch { }
    Write-Host 'Se necessário, consulte o IPv4 da interface Wi-Fi/Ethernet deste computador e use http://IP:8000.'
    Write-Host 'Se o celular não conseguir acessar, verifique se a porta 8000 está liberada no firewall do computador.'
} catch {
    Fail 'Instalação interrompida. Verifique Docker Desktop, permissões e os arquivos do projeto.'
}
