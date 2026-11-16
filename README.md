# SIGp — Sistema Gerencial Pessoal

> **Avaliação acadêmica (Entrega 2):** comece por [`docs/entrega-academica/README-ENTREGA2.md`](docs/entrega-academica/README-ENTREGA2.md). Ele diz onde estão os documentos, como instalar e quais endpoints testar. A interface web descrita abaixo é o sistema pessoal do autor e não faz parte da avaliação.

Protótipo local para cadastro e gestão de agências, rodoviárias e garagens, com notas fiscais de provedores, anexos de faturas, conciliação e integração com n8n.

## Equipe

- Fredson Pereira de Oliveira Santos
- Maciel Lopes Francisco
- Aeverton Santos
- Jonatas de Jesus Souza

Repositório: <https://github.com/FredsonSistema/sigp>

> **SIG, SIE e painel legado:**
> - **SIG — Sistema de Informação Gerencial:** aba do SIGp (já existe, primeira versão) com a visão gerencial de notas, pagamentos, pendências e divergências.
> - **SIE — Sistema de Informação Executiva:** aba **dedicada e separada** do SIG, com indicadores de ciclos fechados (nota lançada + nota paga + fatura com `MATCH`), análises gravadas pelo n8n e lista separada das notas Gmail em andamento.
> - **Painel legado `/sie`** (`buscador_nfse.py`, porta `5000`): foi criado com o nome trocado. É um painel de **conciliação**, não o SIE executivo. Continua no ar como legado; “sie” permanece em nomes técnicos (container `sigp_sie`, eventos) até a migração.
>
> O fluxo alvo, o que já está pronto e o plano de ação estão em [`docs/guia-fluxo-n8n.md`](docs/guia-fluxo-n8n.md).
> O roteiro para consolidar persistência local e preparar uma instalação completa para Windows está em [`docs/roteiro-instalacao-local.md`](docs/roteiro-instalacao-local.md).

## Como rodar a entrega acadêmica (terminal, sem site)

Pré-requisitos: Docker Desktop, PowerShell 7 (`pwsh`), `sqlcmd` e Python 3. Na raiz do projeto:

```powershell
# 1. Banco, papéis e carga. O setup gera as senhas aleatórias em .env.academic (fora do repositório;
#    as variáveis estão descritas em .env.academic.example).
pwsh -File docs/entrega-academica/sqlserver/setup-academic.ps1

# 2. Sistema principal (API, n8n, OCR, Ollama) e ambiente acadêmico leve (SQL Server 2 GB + API da IA)
docker compose up -d
docker compose --env-file docs/entrega-academica/sqlserver/.env.academic `
  -f docs/entrega-academica/sqlserver/compose.academic.yml `
  -f docs/entrega-academica/sqlserver/compose.leve.yml up -d

# 3. Demonstração de todos os itens da entrega 2 (com pausa entre os passos; sem pausa: -SemPausa)
pwsh -File docs/entrega-academica/demo-parte2.ps1
```

A demonstração mostra, nesta ordem: fluxo n8n → API → SQL Server/RLS → RAG → Qwen local; casos de teste, prompts, fine-tuning,
custo e latência; papéis com GRANT e DENY; mascaramento; volume e consultas lentas; IA sem permissão e prompt injection; auditoria;
perfis e permissões da API. O PDF da entrega é gerado por `python docs/entrega-academica/gerar_parte2.py` (ver
[`docs/entrega-academica/README.md`](docs/entrega-academica/README.md)).

## Visão do sistema

O sistema é dividido em três partes:

1. **SIGp (frontend):** aplicação HTML e JavaScript (porta `8000`, no Windows). O SQLite da API é a fonte persistente dos cadastros e dados operacionais; `localStorage` funciona como cache e migração inicial. Configurações de conexão, incluindo URLs e chave de API, continuam no navegador.
2. **API SIGp:** Flask + waitress no container `sigp_api` (porta `5001`, só em `127.0.0.1`), fonte única de locais, dados auxiliares do sistema, notas, pagamentos, faturas, conciliações (3 vias), correções, alertas e análises. Banco SQLite em `backend/data/sigp.db`.
3. **n8n (orquestrador) e serviços Docker:** recebem notas e faturas, chamam a API, recebem dela os eventos de conciliação, gravam análises (SIG/SIE), agendam alertas e notificam. O OCR de PDFs é local à rede Docker.

O sistema contém dois bancos SQLite, com finalidades diferentes. O backend SIGp (`backend/data/sigp.db`) é a fonte dos dados operacionais do SIGp e os PDFs ficam em diretório persistente separado. O serviço legado (`buscador_nfse.db`) mantém os registros do Buscador/SIE e recebe uma cópia/representação dos eventos encaminhados pelo n8n. Os arquivos **não** são o mesmo banco nem ficam automaticamente sincronizados em todos os fluxos.

### Conceitos e fluxo de notas

- **Local:** agência, rodoviária ou garagem. Notas e faturas devem estar vinculadas ao cadastro correto do local.
- **Nota lançada:** nota recebida/importada, normalmente por XML ou preenchimento manual; possui chave, número, série, emissor, valores e datas quando disponíveis.
- **Nota paga:** registro separado do pagamento, com valor efetivamente pago e data. Um estado de pagamento deve refletir confirmação real; os registros de teste estão identificados como simulação.
- **Conciliação (3 vias):** compara identidade fiscal, local, valores e serviços nas notas lançada e paga e, depois, a fatura. Pagamento parcial = `PAGO_PARCIAL`; lançada e paga conferindo sem fatura = `AGUARDANDO_FATURA`; fatura divergente = `DIVERGENCIA`; só lançada + paga + fatura conferidas = `MATCH`. Cada mudança de status vira evento para o n8n. A regra de 3 vias pode ser desligada com `SIGP_EXIGIR_FATURA=0`.
- **Fatura PDF:** anexo opcional de provedor, filho de um local e opcionalmente associado a uma nota lançada. Serve para extrair e comparar emissor, número, vencimento e valores; o documento não comprova pagamento.
- **Contrato de evento:** o SIGp envia um payload normalizado com evento, documento, itens e resumo. O n8n orquestra; não substitui a conferência humana nem a regra de conciliação do backend.
- **SIG:** aba gerencial com indicadores, filtros, gráficos, alertas (vencimentos, fatura não disponível, aguardando fatura, divergências) e a análise gerencial gravada pelo n8n. Falta drill-down.
- **SIE:** aba executiva dedicada, só com ciclos fechados (`MATCH` de 3 vias): custo fechado, custo médio, taxa de fechamento, variação mensal, por local/provedor e a análise executiva gravada pelo n8n. Gmail, WhatsApp e Telegram estão nos workflows, desativados até as credenciais serem configuradas.

### Fluxo alvo (produção: API + webhook)

Em produção, nota lançada e nota paga chegam por **duas APIs separadas e obrigatórias** (Praxio/Globus), o n8n extrai e normaliza os dados e grava pela API SIGp, que valida e concilia. Hoje as duas notas são importadas manualmente; a importação manual deve usar o mesmo contrato e os mesmos endpoints, mudando só a `origem`. Divergências podem ser corrigidas manualmente. Sem fatura, o SIG mostra o alerta "fatura não disponível"; com a fatura, o n8n extrai os campos para revisão. Quando lançada + paga + fatura dão `MATCH`, o n8n analisa com IA, alimenta o SIE e envia relatório/alertas. O n8n também verifica diariamente os vencimentos por agência, rodoviária e garagem. Detalhes, prontidão e plano em [`docs/guia-fluxo-n8n.md`](docs/guia-fluxo-n8n.md).

Mais detalhes do payload e da arquitetura estão em [`docs/contrato-documentos.md`](docs/contrato-documentos.md) e [`docs/arquitetura.md`](docs/arquitetura.md).

### Entrega acadêmica

O README curto, diagramas, plano técnico de IA/segurança e script de carga fictícia para SQL Server estão em [`docs/entrega-academica/`](docs/entrega-academica/README.md).

## O que já foi feito

### SIGp e documentos

- Cadastro de agências, rodoviárias e garagens, com provedores e dados locais.
- Importação e normalização de XML/JSON de NFS-e; lançamento de nota e registro separado de nota paga.
- Campos e comparação de chave, valor, cidade e serviços, com estados como `PENDENTE`, `DIVERGENCIA` e `MATCH`.
- Revisão das classificações nos serviços lançados e pagos; conciliação de pagamentos parciais acumulados, sem liberar parcial como `MATCH`.
- Proteção contra reutilizar um ID para outra identidade fiscal, duplicar uma chave de nota lançada e sobrescrever conciliações de pares diferentes. Conflitos de documentos são informados com HTTP 409.
- Aba **Faturas** para anexar PDFs a um local, opcionalmente selecionar nota de referência, enviar ao n8n, revisar a extração e salvar metadados e arquivo no backend.
- Aba **Notas recebidas** para PDFs importados por Gmail, associação manual a agência/rodoviária/garagem, criação de local, abertura/impressão e preparação manual de e-mail ao financeiro. CNPJ/nome exatos podem sugerir local, mas nunca associam automaticamente; etiquetas Gmail dependem do workflow OAuth ainda não publicado.
- Cada provedor de agência, rodoviária ou garagem pode receber seu próprio PDF. O PDF recém-anexado passa a ser a fatura atual daquele provedor, e os anteriores continuam no histórico; valor e vencimento extraídos podem ser revisados antes de salvar. A conciliação usa o PDF atual como referência de valor quando disponível.
- A tela `/sig` na porta `5000` registra aprovações/rejeições manuais com usuário, justificativa e histórico dos valores antes/depois. Essas decisões são auditoria separada e não alteram a conciliação automática nem liberam o ciclo para o SIE.
- Vínculo de PDF resolvido pelo ID canônico da nota na API, mesmo quando a nota foi primeiro importada para o cadastro local do navegador; reenvios idênticos de notas com HTTP 409 reutilizam o registro existente e não aceitam divergências cadastrais.
- Ações **Enviar para análise** nas notas e faturas encaminham a conciliação ao n8n. Divergências exigem confirmação explícita antes do envio; aceitar encaminhar para revisão não altera nem aprova automaticamente a conciliação.
- O WF-05 atualiza a API SIGp e faz upsert das conciliações na tabela que alimenta o painel legado `/sie` (porta 5000).
- Persistência do backend por SQLite e endpoints para notas, conciliação, eventos e faturas.
- Lookup de nome de município por código através da API de localidades do IBGE.

### n8n, OCR e painel legado

- Workflow de contas de provedores e workflow de notas fiscais exportados em JSON.
- Workflow de extração de PDF publicado na instância n8n. O fluxo tenta extrair texto do PDF e usa OCR local quando necessário.
- Serviço OCR com Poppler (`pdftotext`/`pdftoppm`) e Tesseract com idiomas português e inglês. O serviço só é exposto na rede interna do Compose.
- Serviço legado de conciliação em `buscador_nfse.py`, disponível em `/sie` na porta `5000` (nome trocado: não é o SIE executivo), com filtros por categoria/status/texto e detalhes por registro; inicia sem inserir registros de demonstração.
- Teste ponta a ponta de uma **simulação** de pagamento: nota XML 88468 da Algar, valor R$ 121,69, conciliação `MATCH`, envio pelo n8n e registro `nfse_conciliada` no painel legado.
- A simulação foi marcada como tal na observação; não representa pagamento real.
- Primeira aba **SIG** integrada ao menu: indicadores de valores lançados/pagos/pendentes, vencidas, conciliações e divergências; filtros de período, tipo de local, provedor e status; evolução mensal e agrupamentos por provedor e local.
- Endpoint `GET /api/sig/resumo` calcula os indicadores diretamente do SQLite do backend SIGp. Grupos com chaves de nota duplicadas são excluídos dos totais e exibidos como alerta de qualidade, sem correção automática dos registros.

### Verificação de 09/10/2026 (computador atual)

- 12/12 testes automatizados passaram com `.venv-1`.
- Fluxo da API testado de ponta a ponta (lançada, duplicidade 409, pagamento parcial, `MATCH`, divergência, serviço pendente, anexo de PDF, resumo SIG); banco restaurado do backup após o teste.
- Webhook `sigp-faturas-pdf` com `algar.pdf`: HTTP 200 em 27 s com OCR; valor e vencimento corretos, emissor/número/CNPJ com erro (revisão manual continua obrigatória).
- A instância n8n deste computador só tinha o workflow de PDF (`sigp-notas` respondia 404). Resolvido no mesmo dia com os workflows WF-01/02/05/06/99.
- Bug B1 (SIG mostrava `PAGO_PARCIAL` em vez de `MATCH` com conciliações no mesmo segundo): corrigido e coberto por teste.

### Verificação após as fases 0–2 (09/10/2026)

- 29/29 testes automatizados.
- Ponta a ponta pelo n8n, 13/13: nota lançada via WF-01 (origem `manual` preservada, 409 repassado), pagamento via WF-02 conciliando como `AGUARDANDO_FATURA`, evento entregue ao WF-05 com análise gravada no SIG, fatura fechando o ciclo em `MATCH` com análise executiva no SIE, divergência corrigida por `PATCH` auditado, alertas do local de teste. Banco restaurado do backup ao final.
- Histórico reprocessado pela regra de 3 vias: a simulação 88468 passou a `AGUARDANDO_FATURA` (o PDF está no outro registro duplicado da mesma nota).

O checklist detalhado, com estados e evidências, está em [`Checklist — SIGp + n8n Webhook de Contas de Provedores.md`](Checklist%20%E2%80%94%20SIGp%20%2B%20n8n%20Webhook%20de%20Contas%20de%20Provedores.md).

## Estrutura do repositório

```text
SIGp_n8n/
├── agencias.html                         # aplicação principal SIGp
├── frontend/modules/                     # eventos, notas, faturas e contrato de documentos
├── backend/
│   ├── app.py                            # API Flask na porta 5001
│   ├── database.py                       # persistência SQLite do SIGp
│   ├── normalizer.py                     # normalização JSON/XML
│   └── data/
│       ├── sigp.db                       # banco SIGp criado/atualizado pela API
│       └── faturas/                      # PDFs anexados pela API
├── ocr/
│   ├── app.py                            # serviço local de extração/OCR HTTP
│   └── Dockerfile                        # Poppler + Tesseract e idiomas
├── sie/
│   └── Dockerfile                        # imagem do painel legado / Buscador
├── docs/
│   ├── arquitetura.md
│   ├── contrato-documentos.md
│   └── guia-fluxo-n8n.md                 # fluxo alvo, prontidão, possibilidades n8n e plano
├── tests/                                # suíte unittest do backend
├── buscador_nfse.py                      # aplicação legada Buscador/SIE na porta 5000
├── buscador_nfse.db                      # banco do painel legado
├── docker-compose.yml                    # n8n, serviço legado e OCR na rede Compose
├── n8n_workflow_contas_provedores.json
├── n8n_workflow_nfse_conciliacao.json
├── n8n_workflow_extrair_fatura_pdf.json
├── requirements.txt                      # dependências Python do host (Flask)
└── README.md
```

O repositório também pode conter PDFs/XMLs de teste e o ambiente virtual local. O ambiente `.venv-1` é gerado na máquina, não é código-fonte nem deve ser versionado. O antigo `.venv` foi excluído em 09/10/2026 porque apontava para o Python do computador anterior (`C:\Users\fredson.santos\...`).

## Dependências

### Necessárias

- Windows com Docker Desktop (é o que o `Iniciar SIGp.ps1` usa, via `docker.exe`).
- Python 3.14 e pip para o backend Flask e o servidor estático local. Dependência Python declarada: `Flask==3.1.0`.
- Navegador moderno.
- Conta local da instância n8n para administração/importação de workflows.

### Instaladas nos contêineres

- `n8nio/n8n:latest`: automações; os dados/configuração persistem no volume Docker `n8n_data`.
- `python:3.12-slim-bookworm` + Flask: serviço legado do painel/Buscador.
- `python:3.12-slim-bookworm`, Poppler e Tesseract (`eng` e `por`): serviço OCR.

Não há dependências npm para o frontend. Ele é composto por HTML/CSS/JavaScript e servido localmente por `http.server`.

## Docker: serviços, rede e persistência

O [`docker-compose.yml`](docker-compose.yml) define os serviços na mesma rede Compose (inclui a interface `web` e a LLM local `ollama`):

| Serviço Compose | Container | Função | Endereço/acesso |
|---|---|---|---|
| `api` | `sigp_api` | API SIGp (Flask + waitress) | `http://127.0.0.1:5001` no Windows; `http://api:5001` para o n8n; monta `backend/data` |
| `n8n` | `sigp_n8n` | Editor e webhooks de produção | `http://127.0.0.1:5678`; volume persistente `n8n_data` |
| `sie` | `sigp_sie` | Painel legado de conciliação (nome trocado: não é o SIE executivo); será desativado depois que SIG e SIE absorverem o que for útil | `http://127.0.0.1:5000`; monta `buscador_nfse.db` |
| `ocr` | `sigp_fatura_ocr` | Extração de texto/OCR local para PDFs | Apenas na rede interna, `http://ocr:5002`; sem porta publicada no Windows |
| `ollama` | `sigp_ollama` | LLM local (Qwen 2.5 3B) chamada só pelo n8n; nenhum dado sai da rede | Apenas na rede interna, `http://ollama:11434`; modelo em `SIGP_OLLAMA_MODEL`; volume `ollama_data` |
| `web` | `sigp_web` | Interface SIGp (nginx servindo `agencias.html` e `frontend/`) | `http://127.0.0.1:8000` |

O n8n acessa a API por `http://api:5001` (variáveis `SIGP_API_URL` e `SIGP_API_KEY` no container), o OCR por `http://ocr:5002` e o painel legado por `http://sie:5000`. A API envia eventos ao n8n por `http://n8n:5678/webhook/sigp-eventos`. Só o frontend (porta `8000`) roda no Windows. As portas `5000`, `5001` e `5678` são publicadas apenas no loopback (`127.0.0.1`).

O OCR valida PDF, limita arquivo a 15 MiB e processamento às primeiras 10 páginas. Arquivos temporários são processados dentro do contêiner; os PDFs salvos pela aplicação ficam em `backend/data/faturas/`, fora do serviço OCR. A extração também sugere a descrição do serviço em formatos rotulados e tabelas de itens; revise esse campo na interface antes de vincular a fatura a uma nota.

### Iniciar os contêineres

Com o Docker Desktop aberto, em PowerShell na pasta do projeto:

```powershell
docker compose up -d --build
```

Para conferir os serviços e logs:

```powershell
docker compose ps
docker compose logs --tail 100
```

Para parar os contêineres sem apagar volumes ou bancos:

```powershell
docker compose down
```

Não use `down -v` em operação normal: isso removeria o volume persistente do n8n. O `buscador_nfse.db` é um arquivo do projeto montado no contêiner.

## Instalar e iniciar o sistema no Windows

O ambiente virtual do projeto é `.venv-1` (Python 3.14 desta máquina, Flask 3.1.0). Só é preciso recriá-lo se ele não existir ou se o projeto for copiado para outro computador — um venv guarda o caminho absoluto do Python e não funciona quando movido:

```powershell
py -3.14 -m venv .venv-1
.\.venv-1\Scripts\python.exe -m pip install -r requirements.txt
.\.venv-1\Scripts\python.exe -m unittest discover -s tests
```

Depois, pode iniciar tudo com duplo clique em [`Iniciar SIGp.bat`](Iniciar%20SIGp.bat). O iniciador abre o Docker Desktop se necessário, encerra uma API antiga que esteja rodando no Windows, executa `docker compose up -d --build` (API, n8n, OCR, painel legado), inicia a interface na porta `8000`, verifica as URLs de saúde e abre a aplicação. A primeira inicialização pode levar alguns minutos. O log da interface fica em `logs/`; o da API, em `docker logs sigp_api`.

### Configuração da API

Copie [`.env.example`](.env.example) para `.env` (não versionado). O Compose lê o arquivo automaticamente.

| Variável | Efeito |
|---|---|
| `SIGP_API_KEY` | Com valor, toda escrita na API exige o cabeçalho `X-API-Key` (o n8n já envia). Informe a mesma chave na interface em **Configurações > Integração**. |
| `SIGP_CORS_ORIGINS` | Origens do navegador autorizadas (padrão `http://127.0.0.1:8000,http://localhost:8000`). |
| `SIGP_EXIGIR_FATURA` | `1` (padrão): `MATCH` exige a fatura. `0`: `MATCH` só com lançada + paga. |
| `SIGP_N8N_EVENTOS_URL`, `SIGP_N8N_TOKEN` | Para onde a API envia os eventos de conciliação. Falhas ficam na fila e são reenviadas a cada 15 min pelo WF-06. |
| `SIGP_ACADEMIC_AI_KEY` | Chave do serviço acadêmico Qwen/RAG usada pelo WF-05; deve corresponder a `SIGP_AI_API_KEY` no `.env.academic`. |
| `SIGP_RELATORIO_EMAIL`, `SIGP_TELEGRAM_CHAT_ID`, `SIGP_WHATSAPP_*` | Destinatários de notificações do n8n (credenciais também necessárias; ver o guia). |

Em **Configurações > Integração** da interface ficam também o endereço da API, o do n8n e o modo de entrada das notas: **pelo n8n** (padrão, igual à produção) ou **direto na API** (contingência; a interface também cai nesse modo sozinha se o n8n não responder).

Na primeira execução de uma instância n8n sem configuração, abra <http://127.0.0.1:5678>, crie a conta proprietária e importe e publique os workflows da raiz (ver [Webhooks n8n](#webhooks-n8n)). **O estado do n8n não acompanha o repositório:** ao trocar de computador, só o que foi importado no novo volume existe. Após alterar um workflow no editor, exporte o JSON de volta para a raiz. A URL `http://127.0.0.1:5678/healthz` confirma apenas que o n8n está no ar: o webhook só atende depois que o workflow estiver importado e ativo. O estado do n8n é guardado no volume Docker `n8n_data`.

### Instalar e abrir o SIGp

Use duplo clique em [`instalarsigp.bat`](instalarsigp.bat). Ele inicia o Docker Desktop se necessário, cria ou atualiza os containers e workflows do SIGp, verifica os serviços e abre duas páginas no navegador:

- **Sistema SIGp:** <http://127.0.0.1:8000/agencias.html>
- **Editor n8n:** <http://127.0.0.1:5678>

Entre na conta do n8n e abra **Workflows** para mostrar WF-01 (nota lançada), WF-02 (nota paga), WF-03 (extração de fatura PDF), WF-05 (eventos/SIG/SIE) e WF-06 (vencimentos). O iniciador importa e publica os workflows principais quando eles ainda não estão registrados. O editor pode solicitar a criação da conta proprietária na primeira utilização.

`file:///C:/.../agencias.html` abre apenas o arquivo estático. O navegador bloqueia operações necessárias ao sistema — por exemplo, chamadas HTTP à API, ao n8n e carregamento de módulos locais — e uma página HTML não tem permissão para iniciar Docker ou processos do Windows. Portanto, use sempre o endereço HTTP acima, depois de iniciar pelo atalho. Se abrir apenas o SIGp, use [`Iniciar SIGp.bat`](Iniciar%20SIGp.bat); para abrir os serviços automaticamente ao entrar no Windows, execute uma vez [`Configurar inicializacao SIGp.ps1`](Configurar%20inicializacao%20SIGp.ps1).

### Levar para outro computador

1. Instale e inicie o **Docker Desktop para Windows** (com WSL 2 habilitado). Docker Compose vem com o Docker Desktop; não é necessário instalar Node.js, n8n, Tesseract ou Poppler no Windows: os serviços são executados em containers.
2. Copie a pasta completa do projeto para um caminho local no novo PC. Inclua os arquivos de workflows `n8n_workflow_*.json`; não use apenas `agencias.html`.
3. Se precisar manter os dados atuais, copie também `backend/data/` (banco SIGp e PDFs anexados) e `buscador_nfse.db` com os containers parados. Guarde o arquivo `.env` separadamente e configure-o no novo computador; não compartilhe nem versiona segredos.
4. Dê duplo clique em [`instalarsigp.bat`](instalarsigp.bat). Na primeira execução, o Docker baixa as imagens e compila os containers, o que pode demorar. Os workflows versionados são importados/publicados quando ausentes.
5. Abra as duas páginas indicadas acima. Na primeira abertura, dados SIGp que ainda estejam apenas no navegador são migrados para o SQLite. URLs de conexão/configurações locais do navegador devem ser configuradas no novo computador; o banco e os PDFs precisam ser copiados conforme o passo 3.

Para preservar também a conta, credenciais, execuções e demais configurações internas do n8n, faça backup/restaure do volume Docker `n8n_data`; os JSONs na pasta do projeto guardam definições de workflows, não credenciais OAuth ou histórico. Para uma apresentação limpa, normalmente basta importar os workflows e entrar/criar a conta n8n no novo computador.

### Conexão MCP do n8n com o VS Code

O arquivo [`.vscode/mcp.json`](.vscode/mcp.json) configura a URL MCP local. No n8n, habilite **Settings > Instance-level MCP** e use **Connect > OAuth > VS Code > One-click setup** para autorizar o cliente. Não coloque o token MCP em arquivos versionados. `N8N_HOST`, `N8N_EDITOR_BASE_URL` e `WEBHOOK_URL` anunciam `127.0.0.1`, que corresponde ao endereço de loopback publicado pelo Docker; usar `localhost` nesta configuração Windows/IPv4 pode tentar `::1` e deixar o MCP esperando a inicialização.

Para encerrar os serviços sem apagar dados ou volumes, use [`Parar SIGp.bat`](Parar%20SIGp.bat). Alternativamente, a inicialização manual abaixo continua disponível.

Se a interface mostrar `Failed to fetch`, confira `http://127.0.0.1:5001/api/health` e `http://127.0.0.1:5678/healthz`; inicie os serviços com `Iniciar SIGp.bat` se algum deles não responder. A tela de saúde do n8n confirma que o serviço iniciou, mas o workflow **SIGp - Extrair fatura PDF** também precisa estar ativo no próprio n8n para receber arquivos.

Inicialização manual: suba os containers (`docker compose up -d --build`, que inclui a API) e, num terminal PowerShell na pasta do projeto, sirva a interface:

**Frontend SIGp (porta 8000):**

```powershell
.\.venv-1\Scripts\python.exe -m http.server 8000 --bind 127.0.0.1
```

Não é necessário iniciar `buscador_nfse.py` no Windows quando o Compose já estiver servindo `sie` na porta `5000`. O contêiner usa a mesma base de código e o mesmo arquivo `buscador_nfse.db`. Iniciar outra cópia nesse endereço causa conflito de porta e pode confundir qual processo atende o painel.

Abra:

- SIGp: <http://127.0.0.1:8000/agencias.html>
- painel legado de conciliação: <http://127.0.0.1:5000/sie>
- n8n: <http://127.0.0.1:5678>
- saúde da API SIGp: <http://127.0.0.1:5001/api/health>
- saúde do painel legado: <http://127.0.0.1:5000/api/health>
- saúde do n8n: <http://127.0.0.1:5678/healthz>

O SQLite é a fonte dos dados operacionais e é carregado antes da abertura da interface. O navegador mantém uma cópia local para funcionamento da tela e preserva suas configurações de conexão; alterações operacionais são persistidas pela API. Se a API não responder, a interface não abre como se os dados estivessem salvos: os dados locais são mantidos e o erro é informado.

### Webhooks n8n

| Arquivo | Workflow | Gatilho | Estado de implantação |
|---|---|---|---|
| `n8n_workflow_wf01_nota_lancada.json` | WF-01 Receber nota lançada | `POST /webhook/sigp-nota-lancada` | publicado e testado |
| `n8n_workflow_wf02_nota_paga.json` | WF-02 Receber nota paga | `POST /webhook/sigp-nota-paga` | publicado e testado |
| `n8n_workflow_extrair_fatura_pdf.json` | WF-03 Extrair fatura PDF | `POST /webhook/sigp-faturas-pdf` | publicado e testado |
| `n8n_workflow_wf05_eventos.json` | WF-05 Eventos da API (IA, SIG, SIE, notificações) | `POST /webhook/sigp-eventos` (chamado pela API) | publicado/ativo com Qwen/RAG experimental; inferência sintética confirmada pela rede n8n; ponta a ponta até SIG/SIE pendente |
| `n8n_workflow_wf06_vencimentos.json` | WF-06 Vencimentos e alertas diários | agenda 07:00 + reenvio de eventos a cada 15 min | publicado; notificações desativadas |
| `n8n_workflow_wf07_decisoes.json` | WF-07 Tomada de decisão manual | `POST /webhook/sigp-tomada-decisao` | publicado e ativo; payload inválido confirmado com HTTP 400 sem gravar decisão |
| `n8n_workflow_wf99_erros.json` | WF-99 Erros | Error Trigger (workflow de erro dos demais) | publicado |
| `n8n_workflow_nfse_conciliacao.json`, `n8n_workflow_contas_provedores.json` | workflows legados | `sigp-notas`, `contas-provedores` | não importados; substituídos por WF-01/02/05/06 |

Para importar e publicar pela linha de comando (o n8n precisa ser reiniciado depois):

```powershell
docker exec sigp_n8n mkdir -p /tmp/wf
Get-ChildItem n8n_workflow_wf*.json, n8n_workflow_extrair_fatura_pdf.json | ForEach-Object { docker cp $_.FullName "sigp_n8n:/tmp/wf/$($_.Name)" }
docker exec sigp_n8n n8n import:workflow --separate --input=/tmp/wf
'sigpWF01NotaLanc','sigpWF02NotaPaga','sigpWF05Eventos0','sigpWF06Vencimen','sigpWF99Erros000','LNCrxFxvHfdDkqL2' | ForEach-Object { docker exec sigp_n8n n8n publish:workflow --id=$_ }
docker restart sigp_n8n
```

O campo **URL do Webhook** em Configurações > Integração recebe eventos JSON; use o endereço do workflow de eventos instalado para essa integração, não o endpoint de extração PDF. O botão **Testar conexão** envia JSON, enquanto o workflow PDF aceita somente bytes de um arquivo `application/pdf`. Na aba **Faturas**, configure separadamente `http://127.0.0.1:5678/webhook/sigp-faturas-pdf`. A interface envia notas para `sigp-nota-lancada`/`sigp-nota-paga` a partir do endereço base do n8n configurado em **Configurações > Integração**. Importar JSON não registra a URL de produção; o workflow precisa estar publicado.

Um HTTP 409 ao sincronizar nota lançada significa que a chave fiscal já existe no banco; confira o registro existente antes de tentar novamente. A API bloqueia duplicatas para preservar a identidade fiscal.

Os workflows de notificação de contas podem ter nós de demonstração/placeholder; Gmail, WhatsApp, Telegram ou serviços externos só funcionam após credenciais e destinatários terem sido configurados. O OCR descrito neste projeto é local; não use endpoint externo se a exigência for manter os documentos no ambiente local.

## PDF: problema encontrado e estado atual

O PDF de exemplo da Algar é um documento sem camada de texto suficiente para extração textual direta. O teste original no workflow retornou `textEncontrado=false`. Foi adicionado um serviço OCR local ao Compose: primeiro tenta Poppler e, se não encontra texto, converte páginas com `pdftoppm` e aplica Tesseract em português.

O OCR local foi executado pelo webhook publicado e retornou HTTP 200 com `textEncontrado=true` e `ocrUsado=true`. No PDF de teste:

- emissor, número, vencimento e valor foram detectados pelo parser, mas **emissor/número vieram parcialmente incorretos**;
- CNPJ e data de emissão não foram reconhecidos;
- numa revisão com a nota XML usada como referência, o valor conferiu, mas o vencimento extraído divergiu do vencimento cadastrado.

Por isso, a extração é assistiva, não prova fiscal: todos os campos precisam ser revisados/corrigidos por uma pessoa antes de salvar. Um aviso de campo não reconhecido não equivale a uma divergência confirmada.

O PDF persistido aponta para a nota 88468 e os IDs do vínculo da fatura e do local coincidem. O usuário confirmou que o cadastro correto para essa fatura é `a_muxd1bz4qek1t` (Agencia teste, Itabuna), que já era o vínculo existente. Há outra nota com a mesma identidade fiscal vinculada a `a_muxc15mpwo330`; esse registro histórico não foi alterado e ambos permanecem fora dos indicadores SIG até resolver a duplicidade. A simulação de pagamento 88468 foi feita separadamente e **não utilizou esse PDF**.

## SIG integrado ao SIGp — primeira versão e evolução

O produto desejado é uma aba **SIG** no menu principal do próprio SIGp, separada das rotinas operacionais como Agências, Notas e Faturas. Não se pretende manter o painel independente `/sie` como destino final nem criar um segundo sistema gerencial desconectado.

Uma primeira versão já consulta a API autoritativa do SIGp e apresenta indicadores financeiros, filtros e gráficos mensais/por provedor/local. Os registros com chave duplicada são excluídos dos indicadores até revisão manual.

Próximas melhorias: validar com o usuário as regras do saldo e dos pagamentos parciais, permitir abrir as notas que compõem cada indicador, ampliar os testes para datas ausentes e filtros, e avaliar migração gradual de recursos úteis do `/sie` sem apagar histórico.

O `/sie` continua sendo painel legado/técnico. A aba principal **Dashboard** continua separada da nova aba SIG.

## Pendências e próximos passos

O plano completo, em fases (saneamento → backend pronto para API → n8n orquestrador → IA/SIG/SIE → Praxio/Globus → produção), está em [`docs/guia-fluxo-n8n.md`](docs/guia-fluxo-n8n.md#7-plano-de-ação). Resumo:

### Concluído em 09/10/2026 (fases 0, 1 e 2 do guia)

- API no Compose com waitress, só em `127.0.0.1`, sem depurador; CORS restrito; chave de API opcional (`X-API-Key`).
- Repositório Git próprio em `SIGp_n8n` com `.gitignore` (sem commit ainda).
- Conciliação de 3 vias com `AGUARDANDO_FATURA`; reprocessamento (`POST /api/notas/reconciliar`); desempate correto no SIG; "vencidas" pela data de hoje.
- Locais e provedores sincronizados para a API; alertas de vencimento, fatura ausente e divergência (`/api/alertas`).
- Correção manual auditada (`PATCH` + histórico); origem externa (`sistemaOrigem`/`idExterno`) com reenvio idempotente.
- Eventos da API para o n8n com fila e reenvio; análises SIG/SIE gravadas pelo n8n; aba SIE.
- Workflows WF-01, 02, 05, 06 e 99 publicados; entrada de notas pela interface passa pelo n8n.
- 29 testes automatizados e teste ponta a ponta pelo n8n (13/13).

### WF-05: parecer experimental Qwen/RAG

O WF-05 envia ao serviço acadêmico somente provedor, descrição, valor e vencimento da fatura, usando `X-API-Key` via `SIGP_ACADEMIC_AI_KEY`. Configure essa variável no `.env` com o mesmo valor de `SIGP_AI_API_KEY` do serviço `academic-ai`. O parecer é salvo junto à análise do SIG/SIE, sem alterar o status ou autorizar pagamento. O modelo usa corpus acadêmico demonstrativo e não valida contratos reais; em caso de dados incompletos ou indisponibilidade, o fluxo grava a análise determinística com o motivo explícito. Para ativar a chamada, o serviço acadêmico precisa estar conectado à rede `sigp_n8n_default`.

As notificações Gmail, Telegram e WhatsApp continuam desativadas até que suas credenciais e destinatários sejam configurados.
- Após a limpeza da base, reimportar somente dados reais e verificar o vínculo entre nota lançada, nota paga e fatura.
- Tela de correção manual na interface (a API `PATCH` já existe; hoje a interface corrige editando e salvando o local).
- Levantar as APIs Praxio/Globus e mapear os campos para o contrato v2 (fase 4 do guia).
- Melhorar o parser/OCR para emissor completo, CNPJ, número e data de emissão, validando com diferentes faturas reais e mantendo revisão manual.
- Validar com o usuário as definições do saldo pendente e dos pagamentos parciais e adicionar drill-down dos gráficos até as notas de origem.
- Revisar manualmente as notas históricas duplicadas já armazenadas; novas duplicações são bloqueadas, mas os registros antigos não foram fundidos/excluídos.

### Robustez e operação

- A suíte automatizada (29 testes) cobre conciliação 3 vias, duplicidade, pagamentos parciais, correção auditada, origem externa, locais, alertas, SIE, autenticação e CORS; ampliar para normalização XML/JSON e cenários-limite.
- A conciliação já revê serviços nas notas lançadas e pagas; o pagamento parcial permanece separado de `MATCH`. Confirmar a semântica desses indicadores com o usuário antes de uso financeiro.
- Completar o ciclo de eventos NFSe (criação, atualização, cancelamento, pagamento, fila/reenvio e erros).
- Adicionar limites/paginação nas listagens e tratamento explícito de falhas/retries no n8n.
- Antes de expor fora da máquina: definir `SIGP_API_KEY`, Header Auth nos webhooks do n8n, HTTPS e usuários na interface.
- Definir backups testados para os bancos SQLite, arquivos PDF e volume `n8n_data`; não há estratégia de produção/monitoramento implementada.
- Configurar credenciais/destinatários somente se notificações externas forem necessárias.
- Adicionar navegação de detalhe (drill-down) aos gráficos/indicadores do SIG e validar filtros com dados reais.

### O que não está implementado

- Integração automática de notas via NS Docs/Praxio, SEFAZ/municípios ou instituição financeira.
- Confirmação bancária de pagamento.
- Migração para PostgreSQL.
- Drill-down dos gráficos SIG para as notas/faturas que compõem os indicadores.
- Garantia de que o OCR reconheça corretamente todos os layouts de fatura.

## APIs locais principais

| Serviço | Rotas |
|---|---|
| API SIGp (`5001`) | Ver lista completa em [`backend/README.md`](backend/README.md): notas (`GET/POST`, `PATCH` com auditoria), conciliação 3 vias, faturas, locais, alertas, análises, SIG, SIE e eventos |
| Painel legado (`5000`) | `GET /api/health`, `GET/POST /api/notas`, `GET /api/notas/consulta`, `GET /api/conciliacoes`, `POST /api/conciliacoes`, `POST /api/sie/webhook`, `GET /api/sie/eventos`, `GET /sie` |
| OCR interno (`5002`) | `GET /health`, `POST /extract` — somente acessível na rede Docker |

Consulte os arquivos de implementação para payloads, parâmetros e respostas completos. A lista de rotas é um resumo e pode evoluir.

## Referências técnicas e materiais do projeto

### Documentação primária deste repositório

- [`docs/arquitetura.md`](docs/arquitetura.md) — separação de responsabilidades entre frontend, Python e automação.
- [`docs/contrato-documentos.md`](docs/contrato-documentos.md) — formato de eventos/documentos e conceitos de status.
- [`Checklist — SIGp + n8n Webhook de Contas de Provedores.md`](Checklist%20%E2%80%94%20SIGp%20%2B%20n8n%20Webhook%20de%20Contas%20de%20Provedores.md) — implementação encontrada, validações e pendências.
- [`Fatura-Algar-555851004.xml`](Fatura-Algar-555851004.xml) e `algar.pdf` — amostras locais de documentos usadas nos testes. Não são documentação normativa.

### Documentação externa

- [Flask Quickstart](https://flask.palletsprojects.com/en/stable/quickstart/) — rotas HTTP e execução local da API.
- [Docker Compose Quickstart](https://docs.docker.com/compose/gettingstarted/) — serviços, imagens, redes, volumes e orquestração local.
- [n8n Webhook node](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/) — webhooks de teste/produção e acionamento de workflows.
- [Python `venv`](https://docs.python.org/3/library/venv.html) — isolamento de dependências do backend.
- [SQLite documentation](https://www.sqlite.org/docs.html) — banco utilizado nos protótipos locais.
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) — motor de reconhecimento óptico usado pelo serviço OCR.
- [Poppler](https://poppler.freedesktop.org/) — utilitários de extração de texto e conversão de PDF usados antes/de suporte ao OCR.
- [API de localidades do IBGE](https://servicodados.ibge.gov.br/api/docs/localidades) — consulta do nome do município pelo código.
- [Portal Nacional da NFS-e](https://www.gov.br/nfse/pt-br) — contexto institucional do documento fiscal. O parser existente é baseado nos formatos/testes do projeto; não deve ser considerado certificado para todo leiaute nacional/municipal.

As referências acima fundamentam tecnologias e integrações usadas ou previstas. A compatibilidade efetiva dos leiautes/XMLs e dos campos reconhecidos continua sendo validada por testes com documentos reais e revisão humana.
