# Roteiro do vídeo / prints — parte 2 (cerca de 4 minutos)

Antes de gravar (PowerShell, na raiz do projeto): confirme que estão no ar `sigp_sqlserver_academic`, `sigp_academic_ai`, `sigp_n8n` e `sigp_ollama`:

```powershell
docker ps --format "{{.Names}} {{.Status}}"
```

Se faltar algum container acadêmico:

```powershell
docker compose --env-file docs/entrega-academica/sqlserver/.env.academic `
  -f docs/entrega-academica/sqlserver/compose.academic.yml `
  -f docs/entrega-academica/sqlserver/compose.leve.yml up -d --no-deps sqlserver-academic academic-ai
```

Faça uma chamada de aquecimento (passo 2) antes de gravar: a primeira carrega o modelo e leva cerca de 30 s.
Não mostre na tela o arquivo `.env.academic`.

| # | Tempo | Mostrar | Comando / tela | Falar |
|---|---|---|---|---|
| 1 | 0:00–0:30 | Arquitetura | `docs/entrega-academica/parte-integracao.pdf`, diagrama | n8n chama a API; a API é a única que fala com o SQL Server; a IA não tem senha de banco nem escrita |
| 2 | 0:30–1:20 | **Fluxo n8n de ponta a ponta** | n8n (http://127.0.0.1:5678) aberto no workflow "SIGp Acadêmico - RAG e Análise"; em outro terminal: `Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5678/webhook/sigp-academic-ai -ContentType 'application/json' -Body '{"provider":"Conecta Alfa Fictícia","description":"IP adicional mensal","amount":"35.00","due_date":"2026-11-10"}'` | Resultado DIVERGENTE pela regra; o modelo sugere, não decide; fontes do RAG citadas; `automatic_payment: false`. Mostrar a execução verde no n8n |
| 3 | 1:20–2:00 | Casos de teste e prompts | `docs/entrega-academica/ia/casos-de-teste-parte2.md` e `ia/prompts/CHANGELOG.md` | 5 casos da API (regra 5/5, modelo 3/5), injeção barrada; v4 = prompts de produção, fatos calculados antes da LLM |
| 4 | 2:00–2:30 | Fine-tune, custo e latência | `ia/finetuning/README.md` (0,522 → 0,900) e `sqlserver/evidence/parte2/latencia-custo.json` | LoRA preliminar em dados sintéticos; 0,5B ≈ 0,3 s, 3B ≈ 1,2 s por chamada, sem custo por token |
| 5 | 2:30–3:10 | **IA sem permissão** | `pwsh -File docs/entrega-academica/sqlserver/testar-ia-permissao.ps1` e abrir `evidence/parte2/ia-permissao-e-injecao.json` e `auditoria-ia.txt` | Perfil sem permissão: 503, nenhum dado. Auditoria: quem pediu, o que consultou, quando, inclusive a negação |
| 6 | 3:10–3:40 | Mascaramento e permissões | `evidence/parte2/mascaramento.txt` e `evidence/security-tests.txt` | Aplicação vê a chave mascarada, fiscal vê o valor real só do seu local; GRANT/DENY com acesso negado |
| 7 | 3:40–4:10 | Volume e consultas lentas | `evidence/parte2/benchmark-tempos.txt`, `leituras-logicas.txt` e abrir `C-consulta2.sqlplan` no SSMS/Azure Data Studio | 100.020 notas; consulta 2: 33 ms → 16 ms e 4.954 → 7 leituras com índice filtrado |

Prints mínimos, se não houver vídeo: passo 2 (resposta + execução no n8n), passo 5 (JSON e auditoria), passo 6 e passo 7 (tabela de tempos e plano).
