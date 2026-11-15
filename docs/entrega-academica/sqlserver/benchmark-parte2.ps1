# Parte 2 — benchmark das duas consultas lentas (A linha de base, B candidatos, C ajustados).
# Gera em evidence/parte2/: benchmark-tempos.txt (mediana/p95), leituras-logicas.txt e planos <cfg>-consulta<n>.sqlplan.
# Termina na configuração C (índices ajustados mantidos). Uso, na raiz: pwsh -File docs/entrega-academica/sqlserver/benchmark-parte2.ps1
$ErrorActionPreference = 'Stop'
$dir = $PSScriptRoot
$out = Join-Path $dir 'evidence/parte2'
New-Item -ItemType Directory -Force $out | Out-Null
$envs = @{}
Get-Content (Join-Path $dir '.env.academic') | ForEach-Object { if ($_ -match '^([A-Z0-9_]+)=(.*)$') { $envs[$matches[1]] = $matches[2] } }
$env:SQLCMDPASSWORD = $envs['MSSQL_SA_PASSWORD']
try {
  $base = @('-S', '127.0.0.1,14333', '-U', 'sa', '-C', '-f', '65001', '-b', '-I')
  # 1. Tempos (mediana, p95) nas três configurações.
  & sqlcmd @base -W -s '|' -i (Join-Path $dir '05_benchmark_parte2.sql') | Set-Content -Encoding utf8 (Join-Path $out 'benchmark-tempos.txt')
  # 2. Leituras lógicas e planos reais por configuração.
  $leituras = @()
  foreach ($cfg in 'A', 'B', 'C') {
    $texto = (& sqlcmd @base -y 0 -v "CFG=$cfg" -i (Join-Path $dir '06_planos_parte2.sql')) -join "`n"
    $planos = [regex]::Matches($texto, '<ShowPlanXML[\s\S]*?</ShowPlanXML>')
    for ($n = 0; $n -lt $planos.Count; $n++) {
      $planos[$n].Value | Set-Content -Encoding utf8 (Join-Path $out "$cfg-consulta$($n + 1).sqlplan")
    }
    $leituras += "### Configuração $cfg"
    $leituras += ($texto -split "`n" | Where-Object { $_ -match '^### CONSULTA|^Table ' })
  }
  $leituras | Set-Content -Encoding utf8 (Join-Path $out 'leituras-logicas.txt')
} finally {
  Remove-Item Env:SQLCMDPASSWORD -ErrorAction SilentlyContinue
}
'concluído'
