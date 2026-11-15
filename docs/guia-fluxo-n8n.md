# Guia — fluxo alvo do SIGp com n8n, SIG e SIE

**Atualizado em:** 09/10/2026
**Para quem:** quem vai continuar o desenvolvimento do SIGp, configurar os workflows n8n ou preparar a integração com Praxio/Globus.

Este guia descreve o fluxo que queremos ter em produção, compara esse fluxo com o que existe hoje (verificado em execução) e organiza o plano de ação. O estado detalhado de cada item fica no [checklist](../Checklist%20%E2%80%94%20SIGp%20%2B%20n8n%20Webhook%20de%20Contas%20de%20Provedores.md).

---

## 1. Vocabulário

| Termo | Significado |
|---|---|
| **SIGp** | O sistema inteiro (interface + API + bancos). |
| **SIG** | *Sistema de Informação Gerencial*: aba do SIGp com a visão operacional/gerencial — notas, pagamentos, pendências, divergências, faturas ausentes, vencimentos. |
| **SIE** | *Sistema de Informação Executiva*: aba **dedicada**, separada do SIG, para a diretoria. Exibe ciclos fechados (nota lançada + nota paga + fatura com `MATCH`), análises gravadas pelo n8n e, em seção própria, notas recebidas por Gmail ainda em andamento. Recebidas não entram nos indicadores de custo fechado. |
| **Painel legado `/sie`** | `buscador_nfse.py` na porta `5000` (container `sigp_sie`). Foi criado com o nome trocado: é um painel de **conciliação**, não o SIE executivo. Fica como legado até a migração; não é a base do SIE novo. |
| **Nota lançada** | A nota fiscal recebida (obrigação). Em produção chega por API; hoje é importada manualmente (XML/JSON). |
| **Nota paga** | O registro do pagamento daquela nota. Em produção chega por **outra** API; hoje é importada manualmente. |
| **Fatura** | PDF do provedor. Opcional na entrada, mas necessária para o `MATCH` completo do fluxo alvo. |
| **Local** | Agência, rodoviária ou garagem. Toda nota e fatura pertence a um local. |

---

## 2. Fluxo alvo (produção: API + webhook)

```text
 Praxio/Globus (API)          Praxio/Globus (API)            Upload manual / e-mail
 nota lançada                 nota paga                      fatura PDF
      │                             │                              │
      ▼                             ▼                              ▼
 ┌──────────────── n8n (orquestrador) ─────────────────────────────────────────┐
 │ WF-01 receber lançada   WF-02 receber paga    WF-03 extrair fatura (OCR)   │
 │   normaliza → contrato v2 → POST API SIGp (com token)                       │
 └──────────────────────────────┬──────────────────────────────────────────────┘
                                ▼
                 API SIGp (fonte única da verdade)
          valida · deduplica · concilia 3 vias · guarda histórico
                                │
        ┌───────────────────────┼─────────────────────────────┐
        ▼                       ▼                             ▼
  divergência →           sem fatura →                 MATCH 3 vias →
  correção manual         alerta "fatura não           WF-05 IA executiva → aba SIE
  na interface            disponível" no SIG           + Gmail + WhatsApp + Telegram
        │
        └──► WF-04 IA gerencial → aba SIG

  WF-06 (agendado, diário): vencimentos por agência/rodoviária/garagem
        → "vence em X dias", "vence hoje", "vencido/atrasado" → SIG + mensageria
  WF-99 (Error Trigger): qualquer falha → log + alerta técnico
```

Regras que valem para todo o fluxo:

1. **A API SIGp decide; o n8n orquestra.** O n8n extrai, normaliza, chama a API e notifica. A regra de conciliação e a gravação ficam no backend, para que o resultado seja o mesmo no modo manual e no automático.
2. **Manual e automático usam o mesmo contrato e os mesmos endpoints.** A importação manual de hoje deve ser exatamente o que a API Praxio/Globus vai enviar amanhã, com `origem` diferente (`manual`, `n8n`, `praxio`, `globus`). Assim, ligar a integração é trocar a fonte, não reescrever o sistema.
3. **Duas entradas separadas e obrigatórias:** nota lançada e nota paga são documentos e APIs diferentes. Não há conciliação sem as duas.
4. **Correção manual sempre possível e auditada:** qualquer campo extraído (XML, PDF, API) pode ser corrigido por uma pessoa, e a correção fica registrada (quem, quando, valor antigo/novo).
5. **IA analisa, não aprova.** A IA gera resumo, explicação de divergência e destaques. Ela não muda status nem libera `MATCH`.

---

## 3. O que existe hoje (verificado em 09/10/2026)

Testes executados nesta data, com backup e restauração do banco ao final:

| Teste | Resultado |
|---|---|
| Suíte `unittest` (`tests/`) com `.venv-1` | 12/12 passaram |
| API: lançada → duplicada (409) → paga parcial → conciliar → `PAGO_PARCIAL` | OK |
| API: pagamento complementar → `MATCH` | OK |
| API: valor divergente → `DIVERGENCIA`; serviço `PENDENTE` não libera `MATCH`; nota inexistente → 404 | OK |
| API: anexar fatura PDF a nota (`/api/faturas`) e rejeitar arquivo não-PDF | OK |
| API: `/api/sig/resumo` e período inválido (400) | OK, mas ver bug B1 |
| n8n `sigp-faturas-pdf` com `algar.pdf` (OCR local) | HTTP 200 em 27 s; valor R$ 121,69 e vencimento 16/09/2026 corretos; emissor parcial ("TELECOM S/A"), número errado ("como"), CNPJ e emissão não reconhecidos |
| n8n `sigp-notas` (evento de nota conciliada) | **404: a instância deste computador só tem o workflow de PDF** (`n8n list:workflow`); notas e contas nunca foram importados aqui |
| n8n → API SIGp via `host.docker.internal:5001` | Alcança (com a API em `0.0.0.0`) |
| Container `sigp_sie` | Responde, mas o healthcheck do Docker estoura 5 s com frequência (`unhealthy`) |

> **Atualização (09/10/2026, mesmo dia):** as fases 0, 1 e 2 do plano foram implementadas e testadas (29 testes automatizados + 13/13 verificações ponta a ponta pelo n8n). A tabela abaixo registra o diagnóstico **antes** dessas fases; o estado atual de cada item está no plano (seção 7) e no checklist.

### Prontidão por etapa do fluxo alvo (diagnóstico inicial)

| Etapa | Situação | O que existe / o que falta |
|---|---|---|
| Importar nota lançada | Parcial | Manual (XML/JSON) no modal do local, campos preenchidos e editáveis, gravação em `POST /api/notas/lancadas`. **Não passa pelo n8n** e a `origem` sai sempre `manual`. |
| Importar nota paga | Parcial | Endpoint separado `POST /api/notas/pagas`. Na interface, só é enviada se a linha já tiver a lançada; não passa pelo n8n. |
| n8n extrai e preenche notas | Não | A extração de XML/JSON é feita no navegador e no backend. O n8n só extrai PDF. |
| Fatura PDF: extração + correção manual | **Sim** | Workflow `sigp-faturas-pdf` + OCR local + revisão obrigatória + `POST /api/faturas`. |
| Correção manual em divergência | Parcial | Edição no modal e novo salvamento. Não há `PATCH`, nem trilha de auditoria; corrigir chave/número de nota já gravada gera 409. |
| Alerta "fatura não disponível" | Não | O backend sabe se há fatura (`fatura_anexada`), mas nada usa essa informação. |
| `MATCH` com 3 vias (lançada + paga + fatura) | Não | A conciliação compara só lançada × paga. A comparação com a fatura existe no upload, mas não entra no status. |
| IA alimentando SIG | Não | O SIG é calculado pelo backend; não há nó de IA nem local para gravar a análise. |
| Aba SIE executiva | Não | Não existe. O `/sie` legado é outra coisa (ver vocabulário). |
| Gmail / WhatsApp / Telegram | Não / parcial | Só WhatsApp (Evolution API) no workflow de contas, com placeholders. |
| Alertas de vencimento por local | Parcial | Navegador: `vencimentoFatura` por local e `diaVencimento` por provedor, com badges e "Resumo do dia". O n8n **não consegue** fazer isso porque os locais e provedores só existem no `localStorage` do navegador. |
| Prontidão Praxio/Globus | Parcial | Há normalizador, contrato v2 (não usado), campo `origem` e endpoints por documento. Faltam autenticação, ID externo, idempotência por origem e locais no backend. |

### Bugs e inconsistências encontrados

| Id | Onde | Problema |
|---|---|---|
| B1 | `backend/dashboard.py:114-119` | O SIG escolhe a "conciliação mais recente" por `updated_at` com precisão de segundos. Se o pagamento parcial e o complementar forem conciliados no mesmo segundo, o SIG mostra `PAGO_PARCIAL` em vez de `MATCH` (reproduzido no teste). Com o n8n enviando em lote, isso vai acontecer com frequência. |
| B2 | n8n | Nesta instância só existe `SIGp - Extrair fatura PDF de provedor`. `SIGp - Notas API + SIE Webhook` e `SIGp - Contas de Provedores` estavam no volume `n8n_data` do outro computador e não vieram na troca. |
| B3 | `n8n_workflow_nfse_conciliacao.json` | Ramo `nfse_lancada` quebrado (corpo `{payload: "<string>"}` gera 400 no legado), evento SIE duplicado, status fixo `PAGA`. |
| B4 | `n8n_workflow_contas_provedores.json` | Conexão para nó inexistente; Gotenberg nunca executa; webhook sem `webhookId`; `headerAuth` sem credencial. |
| B5 | `backend/app.py:512`, `buscador_nfse.py:774` | `debug=True` em `0.0.0.0` (API exposta na rede com o depurador do Werkzeug), CORS `*`, sem autenticação. |
| B6 | Frontend | Evento de `MATCH` usa envelope v1 por um cliente sem fila/retry; o contrato v2 e a fila `sigp_nfse_eventos_v1` não são usados. |
| B7 | Frontend | Bloco de notas em Configurações é código morto (removido logo após renderizar). |
| B8 | Frontend/Backend | Status `PAGO_PARCIAL` × `PARCIAL` × `PAGAMENTO_PARCIAL` em lugares diferentes; `PAGO_COM_ATRASO` nunca é calculado. |
| B9 | `backend/dashboard.py` | "Vencidas" usa a data final do filtro, não a data de hoje. |
| B10 | Frontend | Limite de 7 dias fixo em dois cards, ignorando `CONFIG.alertaFaturaDias`. |
| B11 | Repositório | O Git está na pasta pessoal (`C:\Users\Fredson`), não em `SIGp_n8n`; não há `.gitignore`. |

---

## 4. O que o n8n oferece para o SIGp

Todos os recursos abaixo existem no n8n instalado (2.x, Docker Desktop). O que é "nó" é configurado no editor, sem programar.

| Necessidade | Recurso n8n | Uso no SIGp |
|---|---|---|
| Receber documentos | **Webhook** (produção/teste, autenticação por header) | Um webhook por documento: lançada, paga, fatura. Token obrigatório. |
| Buscar documentos em sistemas | **HTTP Request** (OAuth2, API key, paginação, retry) | Puxar notas da API Praxio/Globus; chamar a API SIGp. |
| Rotinas diárias | **Schedule Trigger** (cron) | Vencimentos, faturas ausentes, relatório diário/semanal. |
| Regras e transformação | **Code**, **IF**, **Switch**, **Merge**, **Set** | Normalizar para o contrato v2, rotear por status. |
| Leitura de PDF | **Extract From File** + OCR local (`ocr:5002`) | Já em uso no workflow de fatura. |
| IA | **AI Agent**, **Basic LLM Chain**, **Information Extractor**, **Text Classifier**, **Summarization Chain**; modelos OpenAI, Anthropic (Claude), Gemini ou **Ollama local** | Extrair campos de faturas com layout difícil (Information Extractor com esquema fixo), explicar divergências, redigir o resumo executivo do SIE. Para documentos fiscais, preferir modelo local (Ollama) ou contrato corporativo com retenção zero. |
| E-mail | **Gmail** (OAuth2) ou **Send Email** (SMTP) | Relatório executivo com HTML/PDF anexo. |
| WhatsApp | **WhatsApp Business Cloud** (oficial Meta) ou **HTTP Request** para Evolution API | Alerta de `MATCH`, vencimento, divergência. |
| Telegram | **Telegram** (bot token) | Mesmo alerta; também pode receber comandos ("resumo de hoje"). |
| Erros | **Error Trigger** + "Retry on fail" por nó | Workflow único de erros com aviso técnico. |
| Espera/aprovação | **Wait** (até webhook de retomada) | Aguardar correção manual antes de seguir. |
| Reuso | **Execute Workflow** (sub-workflows) | Um sub-workflow "notificar" chamado por todos. |
| Planilhas/BI | **Google Sheets**, **Postgres** | Espelho para BI, se necessário. |
| Integração com IDE/agentes | **MCP** (já configurado no `.vscode/mcp.json`) | Inspecionar e editar workflows pelo VS Code. |

---

## 5. Arquitetura alvo

- **API SIGp** passa a ser a única fonte de: locais, provedores, notas lançadas, notas pagas, faturas, conciliações, correções, alertas, análises de IA (SIG e SIE).
- **n8n** chama a API SIGp. Hoje ele alcança a API por `http://host.docker.internal:5001`; o passo recomendado é colocar a API no próprio `docker-compose.yml` (serviço `api`) e chamá-la por `http://api:5001`, igual ao que já é feito com o OCR. Isso deixa o ambiente local igual ao de produção e permite tirar a API do `0.0.0.0` do Windows.
- **Autenticação:** a API exige `X-API-Key` (ou Bearer) para chamadas do n8n; os webhooks do n8n exigem Header Auth. As chaves ficam em variáveis de ambiente/credenciais do n8n, nunca nos arquivos versionados.
- **Contrato v2** (`docs/contrato-documentos.md`) passa a ser o formato único de entrada: com `origem`, `sistemaOrigem`, `idExterno` e `idempotencyKey`.

### Endpoints a acrescentar na API

| Endpoint | Para quê |
|---|---|
| `GET/POST/PATCH /api/locais` e `/api/locais/<id>/provedores` | Trazer agências, rodoviárias, garagens e provedores (com dia de vencimento) do navegador para o backend. Pré-requisito do WF-06 e da integração. |
| `PATCH /api/notas/lancadas/<id>` e `/api/notas/pagas/<id>` | Correção manual com auditoria (`correcoes`: campo, antes, depois, usuário, data). |
| `POST /api/conciliar/3vias` (ou evoluir `/api/notas/conciliar`) | `MATCH` só com lançada + paga + fatura conferida; status `AGUARDANDO_FATURA` quando faltar o PDF. |
| `GET /api/alertas?tipo=vencimento|fatura_ausente|divergencia` | Lista que o n8n consulta no agendamento e o SIG exibe. |
| `POST /api/analises` (`escopo=SIG|SIE`) | O n8n grava aqui a análise da IA; as abas leem daqui. |
| `GET /api/sie/resumo` | Indicadores executivos só de ciclos fechados. |

---

## 6. Workflows n8n planejados

| Id | Nome | Gatilho | Passos | Estado |
|---|---|---|---|---|
| WF-01 | Receber nota lançada | Webhook `sigp-nota-lancada` (interface hoje; Praxio amanhã) | contrato v2 (origem `manual`/`n8n`) → `POST /api/notas/lancadas` → devolve a resposta da API | **Publicado e testado** |
| WF-02 | Receber nota paga | Webhook `sigp-nota-paga` (interface hoje; Globus amanhã) | contrato v2 → `POST /api/notas/pagas` (a API concilia e devolve o status) | **Publicado e testado** |
| WF-03 | Extrair fatura PDF | Webhook `sigp-faturas-pdf` | OCR local → parser → devolver para revisão | **Publicado e testado**; falta IA como segunda tentativa |
| WF-04 | Análise gerencial (SIG) | — | Absorvido pelo WF-05 (eventos `AGUARDANDO_FATURA`/`DIVERGENCIA` → análise SIG) e pelo WF-06 (resumo diário no SIG) | Coberto |
| WF-05 | Eventos da API | Webhook `sigp-eventos`, chamado pela API a cada mudança de status | monta análise determinística → se houver fatura com provedor, descrição e valor, consulta Qwen/RAG acadêmico → grava parecer experimental em `dados.parecerIA` com a análise no SIG/SIE; falha ou falta de dados mantém o fallback determinístico | **Publicado/ativo; inferência sintética confirmada pela rede n8n; ponta a ponta até SIG/SIE pendente** |
| WF-06 | Vencimentos e alertas | Schedule 07:00 + a cada 15 min | `GET /api/alertas` → resumo no SIG → notificações (desativadas); reenvio da fila de eventos | **Publicado**; não executado pelo agendamento ainda |
| WF-07 | Tomada de decisão manual | Webhook `sigp-tomada-decisao` | encaminha a decisão para `POST http://sie:5000/api/sig/decisoes`, que mantém aprovação/rejeição e auditoria separadas da conciliação automática | **Publicado e ativo**; payload inválido confirmado com HTTP 400 sem gravar decisão |
| WF-08 | Caixa de entrada Gmail (v2, IA local) | Gmail Trigger a cada 5 min + busca histórica manual (20 por lote) | busca por remetentes de provedores e assuntos de cobrança → OCR local → regras do SIGp (inclui e-mail do provedor) → extração por regras (linha digitável) → **Qwen 2.5 3B no Ollama local** → grava em Revisão/Aguardando associação; etiquetas `SIGp/Importado`, `SIGp/Ignorado`, `SIGp/Sem-anexo` | **v2 importado e validado com um lote real em 10/11/2026 (26 PDFs: 17 aguardando associação, 9 em revisão); inativo até a decisão de ativar o gatilho** |
| WF-09 | Aplicar etiquetas Gmail | Schedule Trigger, a cada minuto | consulta etiquetas pendentes → procura ou cria etiqueta Gmail `SIGp/<tipo>/<local>` → aplica à mensagem original → confirma sucesso/erro na API; erros ficam visíveis no SIGp e são repetidos | **Execução manual de controle confirmou `APLICADA`; workflow publicado e ativo, com agendamento a cada minuto** |
| — | Contas de provedores (legado) | Webhook `contas-provedores` | Substituído pelo WF-06 + locais na API | Não importado |
| WF-99 | Erros | Error Trigger (definido como workflow de erro dos demais) | aviso técnico (Telegram/Gmail desativados) | **Importado** |

**WF-05 e IA experimental:** configure `SIGP_ACADEMIC_AI_KEY` no `.env` com o mesmo segredo de `SIGP_AI_API_KEY` do serviço acadêmico. A API acadêmica deve estar conectada à rede Docker `sigp_n8n_default`. O workflow envia somente provedor, descrição, valor e vencimento da fatura; o corpo não inclui IDs de local nem dados de pagamento. O corpus é demonstrativo e o parecer não representa validação de contratos reais nem altera conciliação/pagamento. Sem fatura/dados suficientes ou se a API falhar, o SIGp mantém o resumo determinístico e registra que o parecer não foi gerado. A chamada sintética à API já foi confirmada pela rede n8n; o teste webhook→gravação em SIG/SIE permanece pendente para evitar inserir dados artificiais na base operacional. Telegram e WhatsApp seguem desativados até configuração das credenciais e destinatários.

Os JSON de cada workflow devem continuar exportados na raiz (`n8n_workflow_*.json`) após cada alteração, porque o estado do n8n vive no volume Docker `n8n_data` e não acompanha o repositório (foi o que fez o `sigp-notas` "sumir" ao trocar de computador).

### Caixa de entrada de notas fiscais por Gmail

> **WF-08 v2 (10/11/2026).** A classificação passou a usar IA local como segunda opinião, sem enviar documentos para fora da rede Docker. Fonte, regras de decisão, instalação e desempenho medido estão em [`n8n/wf08/README.md`](../n8n/wf08/README.md). Mudanças em relação ao texto abaixo:
>
> - **Etiquetas no lugar de "marcar como lida":** as mensagens não mudam de estado de leitura. As etiquetas de controle fazem a busca histórica avançar em vez de reler sempre os mesmos 50 e-mails.
> - **Busca mais restrita:** remetentes de provedores, assuntos de cobrança ou PDF com termos de fatura. Documentos de RH ou multas deixam de entrar por padrão.
> - **Documentos ignorados:** um PDF só deixa de ser importado quando três sinais concordam: a IA tem certeza de que não é cobrança, as regras do SIGp não acham evidência e não há linha digitável. A mensagem recebe a etiqueta `SIGp/Ignorado` e nada é apagado. Na dúvida, o documento vai para Revisão.
> - **Remetente:** a v1 gravava `[object Object]` porque o Gmail entrega o remetente como objeto. A v2 grava o texto. A API também compara o remetente com o campo e-mail do provedor (`provedoresPorRemetente`).
> - **Faturas sem PDF** (link ou aplicativo) recebem `SIGp/Sem-anexo` e não entram no SIGp, porque a API exige PDF.

A nova aba **Notas recebidas** persiste os PDFs em `backend/data/notas_recebidas/` e mantém os estados `AGUARDANDO_ASSOCIACAO`, `REVISAO` e `ASSOCIADA`. A identificação por CNPJ ou nome exato da empresa destinatária é somente uma sugestão; não associa nem distribui automaticamente. O operador escolhe entre agências, rodoviárias e garagens ativas ou cria um novo cadastro na própria aba, que fica selecionado para a primeira nota aguardando associação. Os campos de provedor, número/chave fiscal, valor, emissão e vencimento podem ser revisados antes de salvar; uma nota associada pode ser corrigida ou movida para outro local.

O WF-08 exportado inclui uma busca histórica manual de mensagens lidas e não lidas (`has:attachment filename:pdf`, lote de até 50), porque o Gmail Trigger só recebe mensagens novas e não recupera o histórico anterior à ativação. A busca retroativa não marca mensagens como lidas. A classificação v1 é uma linha de base determinística e explicável: cruza palavras fiscais e de internet com os nomes de provedores cadastrados em cada local. Não é treinamento nem inferência de IA; documentos incertos são importados com `REVISAO`, nunca descartados, e não são marcados como lidos. A IA Qwen/RAG existente no WF-05 serve para pareceres de conciliação e ainda não tem contrato específico para classificar anexos do Gmail; só deve ser adicionada como sugestão de segunda etapa, sem rejeitar ou arquivar documentos automaticamente.

Ao confirmar, a API cria ou atualiza a nota lançada e a fatura local ligada ao PDF. Para o mesmo local, provedor e vencimento, a nota e a fatura existentes são atualizadas; outro vencimento permanece como registro separado. A conciliação só reaproveita pagamentos que já existam e nunca inventa quitação. O SIE mostra as notas Gmail vinculadas em uma seção de andamento separada; elas só contam nos indicadores executivos após o `MATCH` de três vias. A API retorna uma etiqueta Gmail hierárquica, por exemplo `SIGp/Agências/Agência Centro`; a mensagem original recebe essa etiqueta, sem reenvio.

O export anterior do WF-08 e o consumidor WF-09 já tiveram um teste de controle documentado. As mudanças descritas acima estão somente nos arquivos locais até que o novo JSON WF-08 seja importado/republicado e testado no editor n8n; o workflow WF-09 não foi alterado. Depois da importação, selecione a credencial Gmail OAuth2 no novo nó de busca histórica e valide primeiro um lote pequeno. O envio ao financeiro permanece manual: o operador prepara um e-mail e anexa a cópia baixada.

#### Configuração segura antes de ativar o Gmail

1. Entre no editor n8n e crie uma credencial **Gmail OAuth2**. No Google Cloud, habilite a Gmail API, configure a tela de consentimento, crie um cliente OAuth do tipo Web e cadastre exatamente a URL de callback exibida pela credencial do n8n. Autorize a caixa que receberá as notas; solicite acesso de leitura e modificação de mensagens/etiquetas (`gmail.readonly` e `gmail.modify`). Não salve Client Secret em workflow nem no repositório.
2. Crie uma chave aleatória para `SIGP_API_KEY` no `.env` da raiz do projeto. Informe a mesma chave no campo **Configurações → Chave da API (X-API-Key)** do SIGp. O n8n lê o valor do `.env`; não inclua a chave em JSON exportado, prints ou mensagens.
3. Recrie os serviços para carregar a chave: `docker compose up -d --force-recreate api n8n`. Confirme `GET http://127.0.0.1:5001/api/health` com `autenticacao: true`; confirme também uma escrita autenticada antes de avançar.
4. Importe/reimporte `n8n_workflow_wf08_gmail_inbox.json` e selecione a credencial Gmail OAuth2 no Trigger e no nó `Gmail - buscar PDFs históricos`. Não reimporte o WF-09 se ele já estiver correto. O WF-08 lê `SIGP_API_KEY` do ambiente.
5. Teste primeiro com uma mensagem autorizada de controle. Em seguida execute manualmente `Executar busca histórica manual` com lote limitado; confira duplicação idempotente, PDFs de alta confiança e casos `REVISAO`. O fluxo histórico não deve marcar mensagens como lidas; o fluxo novo só marca como lida após classificação de alta confiança, extração suficiente e confirmação da API. Só então ative a versão validada.

---

## 7. Plano de ação

### Fase 0 — Saneamento (inconsistências) — curto prazo

- [x] Ambiente Python: `.venv` quebrado (apontava para o perfil de outro computador) removido; `.venv-1` adotado.
- [x] Documentação: SIG × SIE × painel legado, contradições do README e do checklist.
- [x] B5: API no Compose, publicada só em `127.0.0.1`, waitress, sem depurador; CORS restrito.
- [x] B11: repositório Git próprio em `SIGp_n8n` com `.gitignore` (sem commit ainda).
- [x] B1: desempate por horário com microssegundos, status mais avançado e ordem de gravação + teste.
- [x] B2/B3/B6: `sigp-notas` legado substituído; eventos saem da API (com fila e reenvio) para o WF-05.
- [x] B9, B10: "vencidas" pela data de hoje; prazo de alerta configurável em todos os cards.
- [~] B8: `PAGO_PARCIAL`/`AGUARDANDO_FATURA`/`PAGO_COM_ATRASO` padronizados na API; o módulo `documentos-contract.js` (não usado) ainda tem `PARCIAL`.
- [x] Healthcheck do `sigp_sie` com prazo maior.
- [ ] B7: remover o bloco de notas morto em Configurações.

### Fase 1 — Backend pronto para API (pré-requisito da integração)

- [x] API no `docker-compose.yml` (serviço `api`, volume `backend/data`), waitress, fuso de Brasília.
- [x] Autenticação opcional por `X-API-Key` (n8n e interface enviam) e CORS restrito.
- [x] Locais e provedores na API (`/api/locais`), sincronizados automaticamente pela interface.
- [x] Origem externa: `origem`, `sistemaOrigem`, `idExterno` (reenvio idempotente). `idempotencyKey` separado não foi necessário.
- [x] `PATCH` com trilha de auditoria para correção manual.
- [x] Conciliação 3 vias, `AGUARDANDO_FATURA`, reprocessamento ao anexar fatura e `POST /api/notas/reconciliar`.
- [x] Importação manual de nota paga sem nota lançada: o pagamento é persistido; ao importar depois a nota lançada, a API concilia automaticamente somente se a identidade fiscal e o local produzirem uma associação única.
- [x] `/api/alertas`, `/api/analises`, `/api/sie/resumo`, `/api/eventos`.
- [x] Testes para os endpoints novos (29 no total).

### Fase 2 — n8n como orquestrador

- [x] WF-01 e WF-02 e interface enviando a importação manual por eles (com contingência direta na API).
- [x] WF-06 vencimentos/alertas e reenvio periódico de eventos.
- [x] WF-99 erros. [ ] Retry nos nós HTTP do n8n.
- [ ] Credenciais: Gmail, bot Telegram, WhatsApp (Cloud API ou Evolution) e Header Auth nos webhooks.

### Fase 3 — IA, SIG e SIE

- [~] Provedor de IA: WF-05 preparado para chamar Qwen/RAG acadêmico como parecer experimental. Falta validar a chamada pelo workflow publicado; o corpus demonstrativo não comprova contratos reais.
- [ ] WF-03 com IA como segunda tentativa quando o parser não reconhecer campos.
- [x] Análise gerencial no SIG (WF-05/WF-06) e alertas "fatura não disponível"/"aguardando fatura" no SIG.
- [x] Aba **SIE** dedicada: custo fechado, custo médio, taxa de fechamento, variação mensal, por local/provedor e análise executiva.
- [~] WF-05 com Gmail + WhatsApp + Telegram (nós prontos, desativados até as credenciais).
- [ ] Drill-down do SIG até a nota/fatura de origem.
- [ ] Tela de correção manual na interface usando o `PATCH`.

### Fase 4 — Praxio/Globus

- [ ] Levantar documentação, autenticação, endpoints, limites e ambiente de homologação de cada API.
- [ ] Mapear campos Praxio/Globus → contrato v2 (tabela de/para no `docs/contrato-documentos.md`).
- [ ] Trocar o gatilho de WF-01/WF-02 de webhook manual para a API (pull agendado ou webhook do fornecedor), mantendo a importação manual como contingência.

### Fase 5 — Produção

- [ ] PostgreSQL (ou SQLite com backup testado, se for monousuário), backup de `backend/data`, `buscador_nfse.db` e `n8n_data`.
- [ ] Monitoramento (health de API, n8n, OCR) e rotação de logs.
- [ ] Desativar o painel legado `/sie` depois de migrar o que for útil.

---

## 8. Como testar o que existe hoje

```powershell
# testes automatizados
.\.venv-1\Scripts\python.exe -m unittest discover -s tests

# extração de fatura pelo n8n (use curl.exe; o Invoke-WebRequest do PowerShell 5.1 derruba a conexão em uploads longos)
curl.exe -s -X POST -H "Content-Type: application/pdf" --data-binary "@algar.pdf" "http://127.0.0.1:5678/webhook/sigp-faturas-pdf?provedorEsperado=Algar&valorEsperado=121.69"

# n8n alcança a API SIGp?
docker exec sigp_n8n wget -qO- http://host.docker.internal:5001/api/health
```

Antes de testes que gravam dados, copie `backend/data/sigp.db` e `buscador_nfse.db`; a API não tem `DELETE`.
