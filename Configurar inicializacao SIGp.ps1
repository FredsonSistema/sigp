# Cria os atalhos do SIGp para o usuário atual (execute uma vez por computador):
#  - Inicialização do Windows: sobe Docker e todos os serviços em segundo plano, sem abrir o navegador.
#  - Área de trabalho "SIGp": confere se tudo está pronto e abre o SIGp e o editor n8n.
# Para desfazer: execute com -Remover.
param([switch]$Remover)

$projectRoot = $PSScriptRoot
$script = Join-Path $projectRoot 'Iniciar SIGp.ps1'
$powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$startupLink = Join-Path ([Environment]::GetFolderPath('Startup')) 'SIGp - iniciar servicos.lnk'
$desktopLink = Join-Path ([Environment]::GetFolderPath('Desktop')) 'SIGp.lnk'

if ($Remover) {
    Remove-Item -LiteralPath $startupLink, $desktopLink -Force -ErrorAction SilentlyContinue
    Write-Host 'Atalhos do SIGp removidos.'
    return
}

$shell = New-Object -ComObject WScript.Shell

$startup = $shell.CreateShortcut($startupLink)
$startup.TargetPath = $powershell
$startup.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`" -SemNavegador"
$startup.WorkingDirectory = $projectRoot
$startup.WindowStyle = 7
$startup.Description = 'Sobe Docker, API, interface, n8n e OCR do SIGp ao entrar no Windows'
$startup.Save()

$desktop = $shell.CreateShortcut($desktopLink)
$desktop.TargetPath = Join-Path $projectRoot 'instalarsigp.bat'
$desktop.WorkingDirectory = $projectRoot
$desktop.WindowStyle = 7
$desktop.IconLocation = "$env:SystemRoot\System32\imageres.dll,1"
$desktop.Description = 'Abre o SIGp e o editor n8n (confere e inicia os serviços se preciso)'
$desktop.Save()

Write-Host "Atalho de inicialização: $startupLink"
Write-Host "Atalho na área de trabalho: $desktopLink"
