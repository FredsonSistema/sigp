# Demonstração da entrega 2 pelo terminal (sem tela web): IA, Segurança/Otimização e Integração.
# Cada passo mostra o comando, executa e espera Enter (para gravar o vídeo). Com -SemPausa roda direto
# e grava a saída em sqlserver/evidence/parte2/demo-parte2-saida.txt (os "prints" do relatório).
# Nenhuma senha é mostrada: o script lê o .env.academic e passa a senha por variável de ambiente.
# Uso, na raiz do projeto:  pwsh -File docs/entrega-academica/demo-parte2.ps1  [-SemPausa]
param([switch]$SemPausa)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$OutputEncoding = [Text.Encoding]::UTF8
if ($PSStyle) { $PSStyle.OutputRendering = 'Host' }  # cores só na tela; arquivo sem códigos de cor
$raiz = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$sql = Join-Path $PSScriptRoot 'sqlserver'
$py = if (Test-Path (Join-Path $raiz '.venv-1\Scripts\python.exe')) { Join-Path $raiz '.venv-1\Scripts\python.exe' } else { 'python' }
$envs = @{}
Get-Content (Join-Path $sql '.env.academic') | ForEach-Object { if ($_ -match '^([A-Z0-9_]+)=(.*)$') { $envs[$matches[1]] = $matches[2] } }
$env:SQLCMDPASSWORD = $envs['MSSQL_SA_PASSWORD']
$base = @('-S', '127.0.0.1,14333', '-U', 'sa', '-C', '-f', '65001', '-I', '-W', '-s', ' | ', '-d', 'SIGpAcademic')

function Passo($n, $titulo, $fala) {
  Write-Host ''
  Write-Host ('=' * 100) -ForegroundColor DarkCyan
  Write-Host " PASSO $n · $titulo" -ForegroundColor Cyan
  Write-Host " $fala" -ForegroundColor Gray
  Write-Host ('=' * 100) -ForegroundColor DarkCyan
}
function Comando($texto) { Write-Host "> $texto" -ForegroundColor Yellow }
function Pausa { if (-not $SemPausa) { Read-Host "`n[Enter] próximo passo" | Out-Null } }
function Sql($consulta) { & sqlcmd @base -Q "SET NOCOUNT ON; $consulta" }
# O Ollama é compartilhado com o SIGp de produção (um pedido por vez, um modelo carregado).
# Antes do passo 1 carregamos o qwen2.5:0.5b e esperamos a fila esvaziar, para a demo não estourar o tempo.
function Aquecer-Modelo {
  $py_aq = "import json,urllib.request as u;r=u.Request('http://ollama:11434/api/generate',data=json.dumps({'model':'qwen2.5:0.5b','prompt':'ok','stream':False,'keep_alive':'30m','options':{'num_predict':1}}).encode(),headers={'Content-Type':'application/json'});u.urlopen(r,timeout=900).read();print('ok')"
  for ($i = 1; $i -le 3; $i++) {
    Write-Host "  aquecendo o modelo local (tentativa $i/3; pode levar alguns minutos se o Ollama estiver ocupado)..." -ForegroundColor DarkGray
    $saida = docker exec sigp_academic_ai python -c $py_aq 2>&1
    if ("$saida" -match 'ok') { Write-Host '  modelo pronto.' -ForegroundColor DarkGray; return }
  }
  Write-Host '  aviso: não foi possível aquecer o modelo; o passo 1 vai tentar mesmo assim.' -ForegroundColor Yellow
}

try {
  Passo 0 'Ambiente' 'Tudo local em Docker: SQL Server acadêmico, API da IA, n8n e Ollama (sem SaaS, sem site).'
  Comando 'docker ps'
  docker ps --format '{{.Names}}  {{.Status}}' | Where-Object { $_ -match 'academic|n8n|ollama' }
  Pausa

  Passo 1 'IA · fluxo de ponta a ponta (n8n + RAG + LLM local)' 'Webhook do n8n -> API -> SQL Server com RLS -> RAG (fontes citadas) -> Qwen local. A regra decide; o modelo sugere; nada é pago sozinho.'
  Aquecer-Modelo
  $corpo = '{"provider":"Conecta Alfa Fictícia","description":"IP adicional mensal","amount":"35.00","due_date":"2026-11-10"}'
  Comando "Invoke-RestMethod -Method Post http://127.0.0.1:5678/webhook/sigp-academic-ai -Body '$corpo'"
  $t0 = Get-Date
  $r = $null
  for ($i = 1; $i -le 3 -and -not $r; $i++) {
    try { $r = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:5678/webhook/sigp-academic-ai' -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($corpo)) -TimeoutSec 300 }
    catch {
      if ($i -eq 3) { throw "O fluxo da IA falhou 3 vezes ($($_.Exception.Message)). O Ollama provavelmente está ocupado com o SIGp de produção: desative o WF-08 no n8n e rode de novo." }
      Write-Host "  o modelo local estava ocupado (tentativa $i/3); aquecendo e tentando de novo..." -ForegroundColor DarkGray
      Aquecer-Modelo
    }
  }
  $resp = if ($r.result) { $r.result } else { $r }
  [pscustomobject][ordered]@{
    classificacao_pela_regra = $resp.classification; sugestao_do_modelo = $resp.model_classification; modelo_decide = $resp.model_is_authoritative
    pagamento_automatico = $resp.automatic_payment; local = $resp.local_id; linhas_de_contexto = $resp.context_rows
    fontes_rag = (@($resp.source_ids) -join ', '); prompt = $resp.prompt_version; segundos = [math]::Round(((Get-Date) - $t0).TotalSeconds, 1)
  } | Format-List
  Pausa

  Passo 2 'IA · casos de teste, prompts, fine-tuning, custo e latência' 'Cinco casos com entrada, esperado e obtido; prompts versionados; LoRA contra o modelo base; latência medida.'
  Comando 'casos-de-teste-parte2.md (resumo)'
  Get-Content (Join-Path $PSScriptRoot 'ia\casos-de-teste-parte2.md') -Encoding utf8 | Where-Object { $_ -match '^\| (Caso|IA-0)' } | ForEach-Object { $_.Substring(0, [math]::Min(170, $_.Length)) }
  Comando 'ia/prompts/CHANGELOG.md (versões atuais)'
  Get-Content (Join-Path $PSScriptRoot 'ia\prompts\CHANGELOG.md') -Encoding utf8 | Where-Object { $_ -match '^\| v4' } | ForEach-Object { $_.Substring(0, [math]::Min(160, $_.Length)) + '…' }
  Comando 'ia/finetuning/training-results.json: modelo base x LoRA (mesmo conjunto de teste, 20 exemplos)'
  $ft = Get-Content (Join-Path $PSScriptRoot 'ia\finetuning\training-results.json') -Raw | ConvertFrom-Json
  "base  {0}: acurácia {1:N2}, macro-F1 {2:N3}" -f $ft.model_id, $ft.baseline.test.accuracy, $ft.baseline.test.macro_f1
  "LoRA  rank {0}, {1} exemplos de treino: acurácia {2:N2}, macro-F1 {3:N3}" -f $ft.lora_config.rank, $(if ($ft.trainable_examples) { $ft.trainable_examples } else { $ft.finetuned.trainable_examples }), $ft.finetuned.test.accuracy, $ft.finetuned.test.macro_f1
  Comando 'latencia-custo.json'
  $l = Get-Content (Join-Path $sql 'evidence\parte2\latencia-custo.json') -Raw | ConvertFrom-Json
  $l.ollama | ForEach-Object { "{0}: mediana {1} ms, p95 {2} ms, {3} tokens/s" -f $_.modelo, $_.total_ms.mediana, $_.total_ms.p95, $_.geracao_tokens_por_s.mediana }
  Pausa

  Passo 3 'Segurança · papéis, GRANT e DENY testados' 'Papéis sigp_api, sigp_auditor e sigp_ia. DENY de DELETE para a aplicação e de leitura direta para a IA. O teste mostra o permitido e o negado.'
  Comando 'sqlcmd -i 02_security_tests.sql'
  & sqlcmd @base -i (Join-Path $sql '02_security_tests.sql') | Select-Object -Last 3
  Comando 'permissões efetivas da IA (sys.database_permissions)'
  Sql "SELECT pr.name AS papel, pe.state_desc AS estado, pe.permission_name AS permissao, ISNULL(SCHEMA_NAME(o.schema_id)+'.'+o.name, 'schema '+s.name) AS objeto FROM sys.database_permissions pe JOIN sys.database_principals pr ON pr.principal_id = pe.grantee_principal_id LEFT JOIN sys.objects o ON pe.class = 1 AND o.object_id = pe.major_id LEFT JOIN sys.schemas s ON pe.class = 3 AND s.schema_id = pe.major_id WHERE pr.name = 'sigp_ia' ORDER BY estado, objeto;"
  Pausa

  Passo 4 'Segurança · proteção de dado sensível (RLS + mascaramento)' 'A aplicação vê a chave fiscal mascarada; o papel fiscal vê o valor real só do seu local; a IA não lê a coluna.'
  Comando 'sqlcmd -i 07_mascaramento_parte2.sql'
  & sqlcmd @base -i (Join-Path $sql '07_mascaramento_parte2.sql') | Select-Object -Last 12
  Pausa

  Passo 5 'Otimização · volume e consultas lentas' 'Base com volume e as duas consultas lentas com plano de execução (A = só chaves primárias, B = candidatos, C = ajustados).'
  Comando 'contagem de linhas'
  Sql "SELECT (SELECT COUNT(*) FROM app.Notas) AS notas, (SELECT COUNT(*) FROM app.ItensNota) AS itens, (SELECT COUNT(*) FROM app.Pagamentos) AS pagamentos, (SELECT COUNT(*) FROM app.Locais) AS locais;"
  Comando 'benchmark-tempos.txt (15 execuções por configuração)'
  Get-Content (Join-Path $sql 'evidence\parte2\benchmark-tempos.txt') -Encoding utf8 | Where-Object { $_ -match '^[ABC]\||configuracao' }
  Comando 'planos de execução gerados'
  Get-ChildItem (Join-Path $sql 'evidence\parte2') -Filter '*.sqlplan' | ForEach-Object { "{0}  ({1:N0} KB)" -f $_.Name, ($_.Length / 1KB) }
  Pausa

  Passo 6 'Integração · a IA respeita as permissões (nem pela IA o dado sai)' 'IA configurada para outro local com credencial sem permissão: o banco nega e a IA não devolve dado. Prompt injection: responde REVISAR.'
  Comando 'pwsh -File sqlserver/testar-ia-permissao.ps1'
  & pwsh -NoProfile -File (Join-Path $sql 'testar-ia-permissao.ps1') | Out-Null
  $p = Get-Content (Join-Path $sql 'evidence\parte2\ia-permissao-e-injecao.json') -Raw | ConvertFrom-Json
  $neg = ($p.teste_1_perfil_sem_permissao.resposta.corpo | ConvertTo-Json -Compress -Depth 4)
  "perfil sem permissão  -> HTTP {0}: {1}" -f $p.teste_1_perfil_sem_permissao.resposta.http, $neg.Substring(0, [math]::Min(170, $neg.Length))
  "prompt injection      -> HTTP {0}: classificação {1}, pagamento automático {2}" -f $p.teste_2_prompt_injection.resposta.http, $p.teste_2_prompt_injection.resposta.corpo.classification, $p.teste_2_prompt_injection.resposta.corpo.automatic_payment
  Pausa

  Passo 7 'Integração · auditoria: o que a IA consultou, quem pediu e quando' 'Cada chamada grava o ator, a ação, o objeto e o detalhe (sem dado sensível), inclusive as negações.'
  Sql "SELECT TOP 8 ator, acao, objeto, LEFT(detalhe_redigido, 70) AS detalhe, CONVERT(varchar(19), criado_em, 120) AS quando FROM audit.Eventos ORDER BY criado_em DESC;"
  Pausa

  Passo 8 'Segurança na API do sistema · perfis e permissões' 'Administrador, Gerente, Operador e Leitura com chaves próprias; 403 para o que o perfil não pode; auditoria das recusas (banco temporário).'
  Comando 'python docs/entrega-academica/seguranca/demonstrar_perfis.py'
  & $py -W ignore (Join-Path $PSScriptRoot 'seguranca\demonstrar_perfis.py') | Where-Object { $_ -match '^\||Auditoria' }
  Write-Host "`nFim da demonstração." -ForegroundColor Green
} finally {
  Remove-Item Env:SQLCMDPASSWORD -ErrorAction SilentlyContinue
}
