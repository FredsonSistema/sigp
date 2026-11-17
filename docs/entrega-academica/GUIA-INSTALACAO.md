# Guia de instalação e execução (Windows)

Este guia sobe o ambiente da entrega 2 numa máquina Windows: SQL Server, API da IA, Ollama com o modelo Qwen 0.5B e n8n. Tudo roda em Docker, **local**, com dados fictícios.

## 1. Requisitos

| Item | Para quê | Onde obter |
|---|---|---|
| Windows 10/11 64 bits, **8 GB de RAM** (16 GB recomendado), cerca de 10 GB livres em disco | SQL Server (cerca de 2 GB), modelo local (cerca de 0,4 GB) e imagens | — |
| **Docker Desktop** com WSL 2 | Roda todos os serviços | <https://docs.docker.com/desktop/setup/install/windows-install/> |
| **Git** | Baixar o repositório (ou use o zip) | <https://git-scm.com/download/win> |
| **sqlcmd** (Command Line Utilities do SQL Server) | Cria o banco e roda os testes SQL | <https://learn.microsoft.com/sql/tools/sqlcmd/sqlcmd-utility> |
| **PowerShell 7** (`pwsh`) | Script de demonstração | `winget install Microsoft.PowerShell` |
| Python 3.11 ou superior (opcional) | Passo 8 da demo (perfis da API) e `run_cases.py` | <https://www.python.org/downloads/> |
| Postman (opcional) | Testar os endpoints | <https://www.postman.com/downloads/> |

Depois de instalar o Docker Desktop, abra-o e espere aparecer **"Engine running"**.

## 2. Baixar o projeto

```powershell
git clone https://github.com/FredsonSistema/sigp.git
cd sigp
```
Se receber o zip, extraia-o e abra o PowerShell dentro da pasta extraída.

## 3. Subir tudo com um comando

Na raiz do projeto:
```powershell
powershell -ExecutionPolicy Bypass -File docs/entrega-academica/sqlserver/setup-academic.ps1
```

O script faz, em ordem:
1. Gera senhas e a chave da API em `docs/entrega-academica/sqlserver/.env.academic`. Esse arquivo não vai para o Git, e nenhuma senha fica no código.
2. Sobe o **n8n** em `http://127.0.0.1:5678`.
3. Sobe o **SQL Server** em `127.0.0.1,14333`, cria a base fictícia, os papéis, o RLS e os usuários da IA, e roda os testes de segurança (`resultado = PASS`).
4. Sobe o **Ollama** e baixa o modelo `qwen2.5:0.5b`.
5. Sobe a **API da IA** em `http://127.0.0.1:5010`.
6. Importa e publica o **workflow** "SIGp Acadêmico - RAG e Análise" no n8n.

A primeira execução leva de 10 a 20 minutos, porque baixa as imagens e o modelo. As próximas são rápidas. O script pode ser rodado de novo sem perder nada.

## 4. Conferir se está funcionando

```powershell
Invoke-RestMethod http://127.0.0.1:5010/health
Invoke-RestMethod -Method Post http://127.0.0.1:5678/webhook/sigp-academic-ai -ContentType 'application/json' -Body '{"provider":"Conecta Alfa Fictícia","description":"IP adicional mensal","amount":"35.00"}'
```
A primeira chamada deve responder `status: ok`. A segunda deve responder `classification: DIVERGENTE`. Ela pode levar até cerca de 1 minuto, porque o modelo ainda está carregando.

## 4.1 Carga de volume e benchmark (opcional)

Sem este passo, a base tem só as 20 notas iniciais, e o passo 5 da demo mostra contagens pequenas. Para reproduzir as 100.020 notas e os planos de execução:
```powershell
$env:SQLCMDPASSWORD = '<MSSQL_SA_PASSWORD do .env.academic>'
sqlcmd -S 127.0.0.1,14333 -U sa -C -d SIGpAcademic -b -i docs/entrega-academica/sqlserver/03_load_benchmark.sql
pwsh -File docs/entrega-academica/sqlserver/benchmark-parte2.ps1
```
A carga leva alguns minutos e pode ser repetida sem duplicar dados. O benchmark grava em `sqlserver/evidence/parte2/` os tempos (`benchmark-tempos.txt`), as leituras lógicas e os planos `.sqlplan` das configurações A, B e C.

## 5. Testar

- **Postman:** importe [`postman/SIGp-academico.postman_collection.json`](postman/SIGp-academico.postman_collection.json) e preencha a variável `chave`. O valor está em `SIGP_AI_API_KEY`, no `.env.academic`. A descrição completa está em [`ENDPOINTS.md`](ENDPOINTS.md).
- **Demonstração pelo terminal** (8 passos, com Enter entre eles):
  ```powershell
  pip install -r requirements.txt        # só para o passo 8 (perfis da API)
  pwsh -File docs/entrega-academica/demo-parte2.ps1
  ```
- **Ver o fluxo no n8n:**
  1. Abra `http://127.0.0.1:5678`. No primeiro acesso, o n8n pede para criar um usuário local.
  2. Abra o workflow **SIGp Acadêmico - RAG e Análise** e clique em **Executions** para ver cada chamada.
  3. Para acompanhar ao vivo, rode a demo com `-VerNoN8n`.
- **Casos de avaliação da IA:**
  ```powershell
  $env:SIGP_ACADEMIC_AI_KEY = '<SIGP_AI_API_KEY do .env.academic>'
  python docs/entrega-academica/ia/run_cases.py
  ```

## 6. Parar e remover

```powershell
docker compose --env-file docs/entrega-academica/sqlserver/.env.academic -f docs/entrega-academica/sqlserver/compose.academic.yml down
docker compose -p sigp_n8n stop n8n
```
Os dados ficam nos volumes do Docker. Para apagar tudo, inclusive a base, acrescente `-v` ao primeiro comando.

## Problemas comuns

| Sintoma | Causa provável | Solução |
|---|---|---|
| `sqlcmd não encontrado` | Ferramentas do SQL Server não instaladas | Instale o sqlcmd (link na seção 1) e abra um novo PowerShell |
| `SQL Server não ficou pronto` | Pouca memória para o Docker | No Docker Desktop, dê pelo menos 4 GB ao WSL e rode o script de novo |
| Porta 5678, 5010 ou 14333 em uso | Outro programa usa a porta | Feche o programa ou pare o container que está nela |
| Webhook responde `Error in workflow` ou 503 | Modelo ainda carregando ou CPU ocupada | Espere 1 minuto e repita. A demo já aquece o modelo e tenta de novo |
| Webhook responde 404 | Workflow não publicado | No n8n, abra o workflow e ative-o (*Publish*/*Active*) |
