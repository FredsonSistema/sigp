param(
    # Usado pelo atalho da inicialização do Windows: sobe tudo sem abrir o navegador.
    [switch]$SemNavegador,
    # Abre também o editor n8n, para demonstrar os workflows.
    [switch]$AbrirN8n,
    # Força reconstruir as imagens (use depois de alterar o código da API, do OCR ou do painel legado).
    [switch]$Reconstruir
)

$ErrorActionPreference = 'Continue'

$projectRoot = $PSScriptRoot
$composeFile = Join-Path $projectRoot 'docker-compose.yml'
$logDirectory = Join-Path $projectRoot 'logs'
$appUrl = 'http://127.0.0.1:8000/agencias.html'
$n8nUrl = 'http://127.0.0.1:5678'
$dockerCommand = Get-Command docker.exe -ErrorAction SilentlyContinue
$curlCommand = Get-Command curl.exe -ErrorAction SilentlyContinue
$dockerDesktopCandidates = @(
    (Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\Docker Desktop.exe'),
    (Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe')
)

# Serviço -> URL de saúde. Todos rodam no Docker Compose.
$services = [ordered]@{
    'API SIGp'       = 'http://127.0.0.1:5001/api/health'
    'Interface SIGp' = 'http://127.0.0.1:8000/health'
    'n8n'            = 'http://127.0.0.1:5678/healthz'
    'Painel legado'  = 'http://127.0.0.1:5000/api/health'
}

# Workflow -> webhook que precisa estar registrado no n8n. 404 = não importado/publicado.
$workflows = [ordered]@{
    'sigpWF01NotaLanc' = 'sigp-nota-lancada'
    'sigpWF02NotaPaga' = 'sigp-nota-paga'
    'sigpWF05Eventos0' = 'sigp-eventos'
    'LNCrxFxvHfdDkqL2' = 'sigp-faturas-pdf'
}
$workflowFiles = @(
    'n8n_workflow_wf01_nota_lancada.json', 'n8n_workflow_wf02_nota_paga.json', 'n8n_workflow_wf05_eventos.json',
    'n8n_workflow_wf06_vencimentos.json', 'n8n_workflow_wf99_erros.json', 'n8n_workflow_extrair_fatura_pdf.json'
)
$publishIds = @(
    'sigpWF01NotaLanc', 'sigpWF02NotaPaga', 'sigpWF05Eventos0',
    'sigpWF06Vencimen', 'sigpWF99Erros000', 'LNCrxFxvHfdDkqL2'
)

function Test-HttpEndpoint {
    param([string]$Url)
    try {
        $response = Invoke-WebRequest -Uri $Url -TimeoutSec 3 -UseBasicParsing
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 400
    }
    catch {
        return $false
    }
}

function Wait-ForEndpoint {
    param([string]$Url, [int]$TimeoutSeconds, [string]$ServiceName)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-HttpEndpoint -Url $Url) {
            Write-Host ("{0}: pronto" -f $ServiceName) -ForegroundColor Green
            return
        }
        Start-Sleep -Seconds 3
    }
    throw "$ServiceName não respondeu em $Url. Veja 'docker compose logs' e '$logDirectory'."
}

function Test-WebhookRegistered {
    # GET não executa o workflow: o n8n responde "not registered for GET... Did you mean POST" quando o
    # webhook POST está publicado, e "is not registered" quando não existe.
    param([string]$Path)
    try {
        $body = & $curlCommand.Source --silent --show-error --max-time 10 "http://127.0.0.1:5678/webhook/$Path" 2>$null
        return ($LASTEXITCODE -eq 0) -and (($body -join "`n") -match 'Did you mean')
    }
    catch {
        return $false
    }
}

function Wait-N8nWebhookRouter {
    # /healthz pode responder antes de os workflows serem montados no roteador; espere todos os webhooks exigidos.
    $deadline = (Get-Date).AddSeconds(90)
    while ((Get-Date) -lt $deadline) {
        $missing = @($workflows.Values | Where-Object { -not (Test-WebhookRegistered -Path $_) })
        if ($missing.Count -eq 0) {
            return
        }
        Start-Sleep -Seconds 3
    }
}

function Get-MissingWebhooks {
    Wait-N8nWebhookRouter
    @($workflows.GetEnumerator() | Where-Object { -not (Test-WebhookRegistered -Path $_.Value) } | ForEach-Object { $_.Value })
}

# Serviços só da rede interna (sem porta no Windows): conferidos pelo healthcheck do Docker.
$internalContainers = [ordered]@{
    'OCR'            = 'sigp_fatura_ocr'
    'LLM (Ollama)'   = 'sigp_ollama'
}

function Test-ContainerHealthy {
    param([string]$Name)
    $status = & $dockerCommand.Source inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' $Name 2>$null
    return ($LASTEXITCODE -eq 0 -and ($status -eq 'healthy' -or $status -eq 'running'))
}

function Test-AllReady {
    foreach ($url in $services.Values) {
        if (-not (Test-HttpEndpoint -Url $url)) { return $false }
    }
    foreach ($container in $internalContainers.Values) {
        if (-not (Test-ContainerHealthy -Name $container)) { return $false }
    }
    return (Get-MissingWebhooks).Count -eq 0
}

function Show-InternalServices {
    foreach ($entry in $internalContainers.GetEnumerator()) {
        $deadline = (Get-Date).AddSeconds(90)
        while (-not (Test-ContainerHealthy -Name $entry.Value) -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds 3 }
        if (Test-ContainerHealthy -Name $entry.Value) { Write-Host "$($entry.Key): pronto." -ForegroundColor Green }
        else { Write-Host "$($entry.Key): não ficou pronto ($($entry.Value)). Veja 'docker logs $($entry.Value)'." -ForegroundColor Yellow }
    }
    # A LLM é local: sem o modelo, as importações do Gmail vão para Revisão (nada é perdido).
    $model = if ($env:SIGP_OLLAMA_MODEL) { $env:SIGP_OLLAMA_MODEL } else { 'qwen2.5:3b' }
    $models = & $dockerCommand.Source exec sigp_ollama ollama list 2>$null
    if ($LASTEXITCODE -ne 0 -or -not ($models -match [regex]::Escape($model))) {
        Write-Host "Modelo $model ausente no Ollama local. Instale com: docker exec sigp_ollama ollama pull $model" -ForegroundColor Yellow
    }
}

function Repair-Workflows {
    # Volume n8n novo (outro computador, reinstalação): importa e publica os workflows versionados na raiz.
    Write-Host 'Importando e publicando os workflows do SIGp no n8n...' -ForegroundColor Yellow
    & $dockerCommand.Source exec sigp_n8n sh -c 'rm -rf /tmp/sigp-wf && mkdir -p /tmp/sigp-wf' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Não foi possível preparar o diretório temporário para os workflows no n8n.' }
    foreach ($file in $workflowFiles) {
        & $dockerCommand.Source cp (Join-Path $projectRoot $file) "sigp_n8n:/tmp/sigp-wf/$file" | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Não foi possível copiar '$file' para o container n8n." }
    }
    & $dockerCommand.Source exec sigp_n8n n8n import:workflow --separate --input=/tmp/sigp-wf
    if ($LASTEXITCODE -ne 0) { throw 'O n8n não conseguiu importar os arquivos de workflow. Consulte a saída do comando acima.' }
    foreach ($id in $publishIds) {
        & $dockerCommand.Source exec sigp_n8n n8n publish:workflow --id=$id
        if ($LASTEXITCODE -ne 0) { throw "O n8n não conseguiu publicar o workflow '$id'. Consulte a saída do comando acima." }
    }
    & $dockerCommand.Source restart sigp_n8n | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Não foi possível reiniciar o n8n após publicar os workflows.' }
    Wait-ForEndpoint -Url $services['n8n'] -TimeoutSeconds 180 -ServiceName 'n8n'
}

New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
Start-Transcript -Path (Join-Path $logDirectory 'iniciar-sigp.log') -Force | Out-Null

try {
    Write-Host 'Iniciando o SIGp...' -ForegroundColor Cyan

    if (-not (Test-Path -LiteralPath $composeFile)) {
        throw "docker-compose.yml não encontrado em '$projectRoot'."
    }
    if (-not $dockerCommand) {
        throw 'Docker CLI não instalado. Instale e configure o Docker Desktop antes de iniciar o SIGp.'
    }
    if (-not $curlCommand) {
        throw 'curl.exe não encontrado. Instale/atualize o Windows ou adicione curl.exe ao PATH para validar os webhooks do n8n.'
    }

    & $dockerCommand.Source info *> $null
    $dockerReady = $LASTEXITCODE -eq 0
    if (-not $dockerReady) {
        $dockerDesktop = $dockerDesktopCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
        if (-not $dockerDesktop) {
            throw 'Docker Desktop não encontrado. Abra-o manualmente e execute este arquivo de novo.'
        }
        Write-Host 'Abrindo o Docker Desktop; a primeira inicialização pode levar alguns minutos...'
        Start-Process -FilePath $dockerDesktop | Out-Null
        $dockerDeadline = (Get-Date).AddMinutes(5)
        while ((Get-Date) -lt $dockerDeadline) {
            Start-Sleep -Seconds 5
            & $dockerCommand.Source info *> $null
            if ($LASTEXITCODE -eq 0) { $dockerReady = $true; break }
        }
    }
    if (-not $dockerReady) {
        throw 'O Docker Desktop abriu, mas o motor de containers não ficou pronto em 5 minutos.'
    }

    # Trava contra clique acidental num computador novo (ex.: avaliação acadêmica): só pergunta quando o
    # SIGp ainda não está instalado aqui. Na máquina do autor os containers existem e nada é perguntado.
    & $dockerCommand.Source inspect sigp_api *> $null
    if ($LASTEXITCODE -ne 0 -and -not $SemNavegador) {
        Write-Host ''
        Write-Host 'ATENÇÃO: este é o SIGp de uso pessoal do autor (com interface web).' -ForegroundColor Yellow
        Write-Host 'Ele NÃO faz parte da avaliação acadêmica. Para a avaliação, veja:' -ForegroundColor Yellow
        Write-Host '  docs/entrega-academica/README-ENTREGA2.md' -ForegroundColor Yellow
        Write-Host 'Instalar o SIGp pessoal baixa e sobe 6 containers (vários GB).' -ForegroundColor Yellow
        $resposta = Read-Host 'Continuar mesmo assim? (S/N)'
        if ($resposta -notmatch '^[sS]') {
            Write-Host 'Nada foi instalado.'
            Stop-Transcript | Out-Null
            exit 0
        }
    }
    if (-not $Reconstruir -and (Test-AllReady)) {
        Write-Host 'Todos os serviços já estavam prontos.' -ForegroundColor Green
    }
    else {
        # Versões antigas rodavam API e interface com Python no Windows; liberam as portas 5001 e 8000.
        Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -and $_.CommandLine -match 'backend[\\/]app\.py|http\.server\s+8000' } |
            ForEach-Object {
                Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
                Write-Host "Processo antigo no Windows encerrado (PID $($_.ProcessId))."
            }

        Write-Host 'Subindo API, interface, n8n, OCR, LLM local e painel legado pelo Docker Compose...'
        $composeArgs = @('compose', '-f', $composeFile, 'up', '-d')
        if ($Reconstruir) { $composeArgs += '--build' }
        & $dockerCommand.Source @composeArgs
        if ($LASTEXITCODE -ne 0) {
            throw 'O Docker Compose não conseguiu subir os containers. Veja a saída acima e o Docker Desktop.'
        }

        Wait-ForEndpoint -Url $services['n8n'] -TimeoutSeconds 180 -ServiceName 'n8n'
        foreach ($name in @('API SIGp', 'Interface SIGp', 'Painel legado')) {
            Wait-ForEndpoint -Url $services[$name] -TimeoutSeconds 90 -ServiceName $name
        }

        $missing = Get-MissingWebhooks
        if ($missing.Count -gt 0) {
            Write-Host ("Webhooks ausentes no n8n: {0}" -f ($missing -join ', ')) -ForegroundColor Yellow
            Repair-Workflows
            $missing = Get-MissingWebhooks
            if ($missing.Count -gt 0) {
                throw ("Os workflows continuam ausentes no n8n ({0}). Abra http://127.0.0.1:5678 e publique-os." -f ($missing -join ', '))
            }
        }
        Write-Host 'Workflows do n8n: publicados.' -ForegroundColor Green
    }
    Show-InternalServices

    Write-Host ''
    Write-Host "SIGp pronto: $appUrl" -ForegroundColor Green
    if (-not $SemNavegador) {
        Start-Process $appUrl
        if ($AbrirN8n) {
            Start-Sleep -Seconds 1
            Start-Process $n8nUrl
        }
    }
}
catch {
    Write-Host ''
    Write-Host "Falha ao iniciar o SIGp: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Registro desta execução: $(Join-Path $logDirectory 'iniciar-sigp.log')"
    Stop-Transcript | Out-Null
    exit 1
}
Stop-Transcript | Out-Null
