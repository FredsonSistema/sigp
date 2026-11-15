$ErrorActionPreference = 'Stop'

$projectRoot = $PSScriptRoot
$composeFile = Join-Path $projectRoot 'docker-compose.yml'
$dockerCommand = Get-Command docker.exe -ErrorAction SilentlyContinue

# Versões antigas rodavam API e interface com Python no Windows.
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -and $_.CommandLine -match 'backend[\\/]app\.py|http\.server\s+8000' } |
    ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host "Processo antigo no Windows encerrado (PID $($_.ProcessId))."
    }

if (-not $dockerCommand) {
    Write-Warning 'Docker CLI não instalado; os containers não puderam ser parados.'
    exit 1
}

# "stop" mantém os containers: com restart=always eles voltam sozinhos no próximo início do Docker
# (ou do Windows). Volumes e bancos são preservados.
& $dockerCommand.Source compose -f $composeFile stop
if ($LASTEXITCODE -ne 0) {
    Write-Warning 'Não foi possível parar os containers. Os dados persistentes foram preservados.'
    exit 1
}
Write-Host 'SIGp parado. Volumes e bancos mantidos; os serviços voltam no próximo início do Docker ou com Iniciar SIGp.'
