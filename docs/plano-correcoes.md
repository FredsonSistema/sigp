# Plano de correções e adequação — SIGp + n8n + LLM local

> Documento vivo. Atualize o **status** das tarefas, o **registro de alterações** (seção 13) e as **decisões** (seção 12) a cada entrega.
> Criado em 12/11/2026. Última atualização: 15/11/2026 (v30: situações 3 a 5 — código do cliente/contrato).

Legenda: `[ ]` pendente · `[~]` em andamento · `[x]` concluído · `[!]` bloqueado/aguarda decisão.

## 0. Arquitetura alvo e plano de adequação (direção oficial, 12/11/2026)

> Esta seção orienta todas as demais. Quando uma tarefa antiga conflitar com ela, vale esta seção.

### 0.1 Papéis

| Sistema | Papel | Fica? |
|---|---|---|
| **n8n** | Orquestra tudo: busca (Gmail, NSDocs, ERP), OCR, extração, LLM, conciliação analisada, alertas, relatórios. Usa o máximo de recursos nativos do n8n | sim, é o núcleo |
| **SIGp** (SQLite) | Recebe as decisões do n8n, mantém as localidades informadas (faturas, vencimentos, alertas), abas **SIG** (gerente) e **SIE** (executivo). Enquanto não há ERP/NSDocs, é a **porta de entrada manual** (NFS-e XML/JSON, fatura PDF, nota paga). Futuro: executável no Windows | sim, como receptor e entrada manual |
| **LLM local** (Docker, Ollama) | Classifica, extrai o que a regra não resolve, analisa conciliação, redige SIG/SIE, aprende com associar/descartar/decisões. Nenhum dado sai da rede | sim, chamada só pelo n8n |
| **OCR** (Docker) | Texto dos PDFs | sim, chamado pelo n8n |
| ERP, NSDocs | Fontes futuras; entram pelo mesmo contrato de API que a entrada manual usa hoje | futuro |

**Toda interligação é por API/webhook.** O SIGp não processa documentos: envia ao n8n e recebe o resultado.

### 0.2 Fluxos

```text
ENTRADA (hoje)                          ENTRADA (futuro)
SIGp manual: NFS-e XML/JSON, fatura PDF  NSDocs: NFS-e / NFCom
Gmail: faturas (automático)              ERP: nota lançada, nota paga
        │ webhook / busca                         │ busca agendada / webhook
        ▼                                         ▼
┌────────────────────────────── n8n ───────────────────────────────┐
│ receber → OCR → extrair (regras) → LLM local (classifica/confere)  │
│ → envia ao SIGp por API ──────────────────────────────────────────►│ SIGp grava, atualiza o provedor da
│                                                                    │ localidade, concilia as evidências
│ ◄── evento "3 evidências" (lançada + paga + fatura) ───────────────│
│ → LLM analisa → resultado SIG ────────────────────────────────────►│ aba SIG: gerente valida/corrige/devolve
│ ◄── decisão do gerente ────────────────────────────────────────────│
│ → LLM consolida → resultado SIE ──────────────────────────────────►│ aba SIE: executivo
│ alertas diários: atrasadas, pagas, divergentes ───────────────────►│ + e-mail / WhatsApp / Telegram
└─────────────────────────────────────────────────────────────────────┘
```

### 0.3 Onde fica cada regra

| Regra | Onde | Motivo |
|---|---|---|
| Extração de campos (emissor, número, valor, vencimento, CNPJ, linha digitável) | **n8n** (biblioteca `n8n/lib/`, testada com `node`, injetada nos nós Code) | o n8n é quem extrai; vale para Gmail, NSDocs, ERP e entrada manual |
| Classificação e conferência por LLM, análise SIG/SIE | **n8n** chamando o Ollama | orquestração e prompt ficam no n8n |
| Valor padrão `999999999`, recorrência do mês, provedor da localidade, alertas, auditoria | **SIGp** (ao receber) | é quem guarda os dados e informa as localidades |
| Conciliação determinística (3 evidências) | **SIGp** (dispara o evento) | decide quando há evidências; o n8n analisa |
| Extrator do backend (`/api/extracao/texto`) | **SIGp, só como contingência** | usado quando o n8n estiver fora (seção 0.6) |

Reavaliação do que já foi feito: tudo continua válido. A única inversão é a extração: hoje o WF-03 chama o extrator do SIGp; no destino o n8n tem o próprio extrator (a versão Python, com 88 testes e a comparação de 29 PDFs reais, vira a especificação da versão em JS).

### 0.4 Situação atual (verificada em 12/11/2026)

| Item | Situação |
|---|---|
| Gmail → n8n (WF-08) → SIGp | automático; extrator próprio em JS; LLM Qwen 3B |
| Fatura PDF manual → n8n (WF-03) → SIGp | funciona; extração delegada ao SIGp (inverter) |
| NFS-e XML/JSON manual | lida **no navegador**; o n8n (WF-01/02) só repassa |
| "Extrair dados" das Notas recebidas | SIGp chama o OCR direto, sem o n8n |
| 3 evidências → WF-05 | ✅ desde 12/11/2026: LLM local analisa MATCH e DIVERGENCIA; resultado vai ao SIG para o gerente |
| Decisão do gerente | ✅ aba SIG com validar/corrigir/devolver, gravada no SIGp; validadas seguem ao n8n e à SIE (WF-07 só para o painel legado) |
| SIE | 🟡 resumos executivos só após a validação do gerente; indicadores ainda contam todo MATCH |
| Ollama | ✅ `sigp_ollama` no Compose principal desde 12/11/2026 (1ª chamada ~54 s carregando o modelo em CPU; depois ~4 s) |
| Aprendizado | `extracao_feedback` grava associações e descartes; ainda não volta para o prompt |
| LoRA existente | `docs/entrega-academica/ia/finetuning`: Qwen 0.5B, 120 exemplos **sintéticos**, tarefa acadêmica (contratado/divergente/revisar); não é o modelo de extração do WF-08 (confirmar com o usuário se há outro ajuste com 100 notas reais) |

### 0.5 Plano de adequação

Ordem pensada para não parar o que funciona. Cada fase termina com o sistema utilizável.

**Fase A — Contrato de API SIGp ⇄ n8n** (base de tudo; o ERP e o NSDocs usarão o mesmo)

| ID | Tarefa | Status |
|---|---|---|
| A-01 | Documento único do contrato (versão 3 de `docs/contrato-documentos.md`): webhooks de entrada do n8n (documento manual, decisão do gerente) e API de recebimento do SIGp (nota recebida, nota lançada, nota paga, fatura, resultado SIG, resultado SIE, alerta), com id de documento, idempotência, `X-API-Key` e códigos de retorno | `[x]` `docs/contrato-documentos.md` v3: o que está em uso, o que muda e o planejado (envelope v3, idempotência, códigos) |
| A-02 | Fila de saída no SIGp para tudo que vai ao n8n (como já existe para eventos), com reenvio e estado visível na tela | `[ ]` |
| A-03 | Retorno assíncrono: o n8n responde "recebido" na hora e devolve o resultado por API ao SIGp (documentos grandes e LLM lenta não travam a tela) | `[ ]` |

**Fase B — Extração no n8n**

| ID | Tarefa | Status |
|---|---|---|
| B-01 | `n8n/lib/extrator.js`: porte das regras Python (emissor por linha, rótulos, datas no meio da linha, linha digitável, valor padrão), com os testes Python convertidos e a comparação sobre os 29 textos reais (deve empatar com o Python) | `[x]` `n8n/lib/extrator.js` (namespace `ExtratorSIGp`); 10 testes node (`tests/n8n/extrator.test.js`); paridade com o backend em 232/232 casos (`tests/n8n/paridade_extrator.py`, também no `unittest`). Duas regras novas nos dois lados: "Nº documento: X" no meio da linha e chave na linha de baixo do rótulo (44/50 dígitos) |
| B-02 | WF-03 usa a biblioteca no próprio n8n (deixa de chamar o SIGp) | `[x]` nó Code com a lib (gerado por `n8n/wf03/build_wf03.py`); se falhar, a saída de erro chama `POST /api/extracao/texto` (contingência). Publicado; resposta com `extrator: n8n_lib_extrator_v1`; e2e C2 16/16. Caminho de contingência não exercitado ao vivo |
| B-03 | WF-08 (Gmail) usa a mesma biblioteca no lugar de `wf08_lib.extrairCampos` | `[~]` `extrairCampos` reescrita sobre a lib (destinatário pelo grupo e valor/vencimento do texto ficam no WF-08); testes do WF-08 ok; JSON gerado e conferido. Importado em 13/11/2026 (backup da versão anterior em `n8n/wf08/backup_wf08_antes_v3_2026-11-13-0934.json`); **inativo até o usuário testar e ativar** |
| B-04 | "Extrair dados" das Notas recebidas passa a pedir a extração ao n8n (webhook), com o OCR do SIGp só como contingência | `[ ]` |
| B-05 | NFS-e XML/JSON manual: o SIGp envia o arquivo ao n8n (WF-01/02), que normaliza (porte do `normalizer.py`) e devolve; a leitura no navegador fica só como contingência | `[ ]` |

**Fase C — Evidências, SIG e SIE (fluxo de análise)**

| ID | Tarefa | Status |
|---|---|---|
| C-01 | WF-05 chama a LLM local com o prompt que já monta; saída em JSON Schema (conclusão, resumo, pontos de atenção, ação sugerida); regra determinística continua sendo a autoridade (D13) | `[x]` WF-05 chama a LLM local (MATCH e DIVERGENCIA, D14) com JSON Schema; fatos calculados no fluxo; falha da LLM segue com a regra |
| C-02 | Aba SIG: cada análise com **validar**, **corrigir** e **devolver** (com justificativa), gravado no SIGp com auditoria | `[x]` aba SIG "Para decidir": validar / corrigir / devolver com justificativa; `POST /api/sig/decisoes` com auditoria |
| C-03 | WF-07 grava a decisão no SIGp (hoje vai ao painel legado) e dispara a etapa executiva | `[x]` a decisão é gravada no SIGp e chega ao n8n pela fila de eventos (`decisao_gerente`); WF-07 fica só para o painel legado |
| C-04 | SIE só recebe ciclos validados pelo gerente; LLM redige o resumo executivo | `[x]` resumo executivo e indicadores da SIE só com ciclos `VALIDADA`/`CORRIGIDA`; card "Aguardando o gerente" (valor, quantidade, devolvidos) |
| C-05 | Alertas diários (WF-06) de atrasadas, pagas e divergentes também gravados no SIGp e enviados por e-mail/WhatsApp/Telegram quando configurados | `[~]` WF-06 inclui pagas (`PAGO`, `PAGO_COM_ATRASO`), alerta do provedor sem duplicar o da nota, valores em R$; envio por e-mail/WhatsApp/Telegram aguarda credenciais |

**Fase D — LLM: aprender e falar melhor**

| ID | Tarefa | Status |
|---|---|---|
| D-01 | Subir e fixar o Ollama no Compose principal (hoje fora do ar), com o modelo e a versão registrados | `[x]` serviço `ollama` (0.40.14) no Compose principal, só na rede interna, modelos qwen2.5:3b e 0.5b copiados localmente; n8n com `SIGP_OLLAMA_URL/MODEL`; iniciador confere OCR e LLM |
| D-02 | Endpoint no SIGp que devolve exemplos confirmados por provedor (associações, descartes, decisões do gerente) para o n8n montar o prompt (exemplos do mesmo provedor nos meses anteriores) | `[ ]` |
| D-03 | Guia de linguagem em pt-BR para os prompts: tom operacional no SIG, executivo no SIE, glossário (competência, fatura atual, divergência), sem inventar valores, frases curtas | `[~]` prompts SIG e SIE em pt-BR (`n8n/wf05/prompt_*.md`) e fatos calculados no fluxo; falta guia para o WF-08 |
| D-04 | Avaliação contínua: acurácia por campo e por provedor a partir do `extracao_feedback`; a decisão do gerente vira rótulo da análise | `[ ]` |
| D-05 | Exportar o conjunto rotulado real (JSONL) e refazer o ajuste fino quando houver volume (gatilho em D10), sempre local | `[ ]` |

**Fase E — Redundância (n8n fora do ar)**

| ID | Tarefa | Status |
|---|---|---|
| E-01 | Nada se perde: fila de saída no SIGp (A-02) e Gmail com etiquetas (o que não foi etiquetado é reprocessado); tudo idempotente | `[ ]` |
| E-02 | Modo contingência no SIGp: se o n8n não responder, a entrada manual continua (extrator e OCR do SIGp, gravação direta), marcada como "processada em contingência" para o n8n reanalisar quando voltar | `[ ]` |
| E-03 | Monitor: indicador na tela do SIGp (n8n, OCR, Ollama no ar; documentos na fila) e alerta externo se cair | `[ ]` |
| E-04 | Recuperação: backup do `n8n_data`, workflows versionados no Git e roteiro de restauração testado | `[ ]` |

**Fase F — Integrações futuras**: NSDocs (NFS-e/NFCom), ERP (lançadas e pagas), pelo contrato da Fase A, como workflows agendados no n8n.

**Fase G — SIGp executável no Windows**: empacotar API + interface + SQLite num executável (ex.: PyInstaller com waitress), configuração da URL do n8n e da chave.


**Fase H — Prioridades do usuário (14/11/2026), quando o fluxo estiver ajustado.** Dois objetivos: uso diário (contas vencidas) e duas disciplinas (Projeto de IA; Otimização e Segurança de Banco de Dados). Haverá nova entrega acadêmica.

| Item | O quê | Recomendação registrada | Status |
|---|---|---|---|
| H-01 | Importação CSV das localidades do sistema antigo | Modelo de CSV + prévia (o que será criado/atualizado/ignorado) antes de gravar; chave de correspondência por nome+cidade ou código antigo; relatório de erros por linha | `[x]` Importar CSV com prévia (14/11) |
| H-02 | Níveis de permissão | Perfis administrador, gerente (decide no SIG), operador (associa, lança, paga), leitura (SIE); usuário e senha com hash no SQLite; cada rota da API exige o perfil; auditoria já existe | `[ ]` |
| H-03 | Segurança do banco (requisito da entrega) | Criptografia em repouso (SQLCipher ou volume cifrado), backups cifrados e testados, menor privilégio, trilha de auditoria, integridade (`PRAGMA integrity_check`), índices e plano de consultas para a parte de otimização | `[ ]` |
| H-04 | Acessos criptografados | HTTPS no nginx local (certificado interno), chave da API por usuário/token com validade em vez de uma chave única, segredos só no `.env` fora do Git | `[ ]` |
| H-05 | IA/LLM para a entrega: treinamento simples, segurança e demonstração por interface ou endpoints (sem SaaS/web) | Ver D-02 a D-05: base rotulada vinda do uso (`extracao_feedback`, associações e descartes, gabarito dos XML) → JSONL → fine-tune LoRA do `qwen2.5:0.5b` local → avaliação comparando regras, modelo base e modelo ajustado → endpoint local de avaliação e tela de resultados | `[ ]` |
| H-06 | Painel legado (porta 5000) | Manter; colocar links para ele nas abas SIG e SIE, para ver as decisões da IA. Não prioritário | `[x]` links nas abas SIG e SIE (14/11) |
| H-07 | Leituras antigas (descrição com rótulo, número ausente) | Sugestão: reler sob demanda (ao abrir a nota) e marcar a versão do extrator, sem carregar o n8n; reprocessamento em lote só se o usuário quiser | `[x]` versão das regras em cada leitura; aviso e releitura gravada sob demanda (14/11) |
| H-08 | P1-10 (aba NFS-e) | Recomendação: a aba vira consulta; lançamento e pagamento ficam em "Notas fiscais do local" (fluxo único, já com as regras novas) | `[ ]` |
| H-09 | Notificações (C-05) | Depois que o fluxo estiver pronto | `[ ]` |


**Ordem de execução acordada (14/11/2026)** — por impacto no uso e complexidade, respeitando dependências. Princípio: a LLM sugere e escolhe; o SIGp acumula tudo; o operador revisa; a regra calcula valores e datas.

| # | Etapa | Itens | Complexidade | Impacto | Depende de |
|---|---|---|---|---|---|
| 1 | Ganhos rápidos | H-07 (versão do extrator em cada leitura; releitura sob demanda das notas antigas) e H-06 (links do painel legado no SIG/SIE) | Baixa | Médio | — |
| 2 | Triagem pela LLM | WF-08 grava tudo no SIGp com o veredito da IA; fila "Ignorados pela IA" separada; aviso por execução (lidos / para revisar / ignorados); confirmar ignorados em lote ou resgatar | Média | Alto | — |
| 3 | Importação CSV das localidades | H-01 (prévia, correspondência, relatório por linha) | Baixa–média | Alto | — |
| 4 | Memória de exemplos no prompt | API devolve os casos confirmados mais parecidos (remetente, provedor); o WF-08 os coloca no prompt; toda associação, descarte, resgate e correção vira exemplo | Média | Alto | 2 (e 3 melhora a sugestão de local) |
| 5 | Métricas de acerto da IA | Acerto por semana em triagem, local e campos; tela própria | Baixa–média | Médio (confiança e evidência acadêmica) | 2, 4 |
| 6 | Robustez | E-01 a E-03: fila de envio com reenvio, indicador de saúde (n8n, OCR, Ollama) | Média | Médio | — |
| 7 | Permissões | H-02 (perfis administrador, gerente, operador, leitura; senha com hash; rota por perfil) | Alta | Médio (uso) / Alto (entrega) | — |
| 8 | Segurança do banco e acessos | H-03, H-04 (criptografia em repouso, backup cifrado, HTTPS local, token por usuário, índices e planos de consulta) | Alta | Alto (entrega) | 7 |
| 9 | Pré-associação por mérito | Provedor com N meses sem correção: cartão chega pré-associado, confirmação em um clique | Média | Alto | 4, 5 e meses de dados |
| 10 | Fine-tune para a entrega | H-05 com dados reais anonimizados: base × LoRA × memória de exemplos | Média–alta | Alto (entrega) | 4, 5 e dados acumulados |
| 11 | Depois | H-08 (aba NFS-e como consulta), H-09 (notificações) | Baixa–média | Baixo | fluxo pronto |

### 0.6 Redundância recomendada

1. **Não perder entrada**: fila de saída no SIGp com reenvio; Gmail é durável; id único por documento.
2. **Continuar trabalhando**: contingência no SIGp para a entrada manual (o extrator e o OCR do SIGp já existem; ficam como reserva, não como caminho principal).
3. **Saber que caiu**: indicador na tela e alerta.
4. **Voltar rápido**: Docker com `restart: always`, backups e roteiro. Modo fila do n8n (Redis + workers) fica para quando sair do protótipo.

Não duplicar a orquestração em outro sistema: duas versões das regras é o problema que já ocorreu com os três extratores.

### 0.7 Ordem sugerida

1. A-01 (contrato) e D-01 (Ollama no ar).
2. C-01 a C-04: fecha o fluxo SIG → gerente → SIE, que é o que falta para o uso real.
3. B-01 a B-03: extração no n8n.
4. A-02, A-03, E-01 a E-03: robustez e contingência.
5. B-04, B-05, D-02 a D-05.
6. F e G.

### 0.8 Pendências antigas que continuam

**Registro para apresentação:** toda mudança entra também em `docs/registro-mudancas.md` (antes → depois → verificação), além do histórico abaixo.

P1-08 (valor padrão nas 34 notas antigas), P1-10 (formulário da aba NFS-e), remetente "[object Object]" no WF-08, D13/D14 (autoridade da LLM e quais eventos analisa), D5/D6 (adiados).

## 1. Objetivo e ordem de dependência

Garantir que notas e faturas cheguem aos locais com os dados corretos, para que o próximo fluxo, **alertas de vencimento**, seja confiável.

```text
P1 Extração correta ─► P2 Associação ao local ─► P3 Campos obrigatórios ─► Alertas de vencimento
        ▲                                                   ▲
        └── P4 Integração dos extratores ───────────────────┘
        └── P5 Aprendizado da LLM (descartar + feedback da associação) melhora P1 ao longo do tempo
```

## 2. Decisões do usuário em vigor

| # | Decisão | Efeito no plano |
|---|---|---|
| D1 | Valor genérico **somente para chave e número**, quando vierem vazios **ou preenchidos incorretamente**. **Valor, vencimento e nome são obrigatórios**: se o OCR não identificar, a inserção é manual. | P1-01 a P1-04, P3 |
| D1b | **Valor padrão confirmado: `999999999`**, para chave e número. Constante única. | P1-01 |
| D11 | Extração de **NFS-e e nota paga em PDF** (modais "Adicionar NFS-e" e "Marcar como pago"): **ajuste futuro**, usando a própria LLM (a mesma esteira de extração), o que também ajuda no treinamento. XML/JSON seguem como estão. | F-01 (seção 9.5) |
| D12 | **Conciliação com análise por LLM no n8n.** A regra das três evidências **fica como está**. | seção 8.4 (P6) |
| D2b | Os extratores de NFS-e (XML/JSON) são um **fluxo complementar**. Fora da unificação de PDF; recebem só a regra do valor padrão e a validação. | seção 4.5, P1-10 |
| D3 | **Unificar** os extratores. | P4 |
| D4 | Ampliar a busca da **data de emissão** (data de emissão, data da fatura, data do documento…). Se não achar, usar a **data de recebimento** e **registrar** que foi assim. | P1-09, P2-01 |
| C1, C2 | Duas correções de interface relatadas em uso: chave da API pedida a todo login; fatura PDF do provedor só abre depois de salvar o nome e reabrir. Comportamento correto da fatura: selecionar → extrair → validar → associar aqui → preencher nome, valor e dia de vencimento. | seção 10 |
| D5, D6 | Tratar depois (terá tratativa diferente). | seção 12 |
| — | Treinar/melhorar a LLM com botão **Descartar** em Notas recebidas e com as notas **associadas** como base. | P5 |

## 3. Diagnóstico (evidências)

### 3.1 Dados reais (leitura de `backend/data/sigp.db`, 12/11/2026)

| Item | Resultado |
|---|---|
| Notas recebidas (Gmail) | 34: 16 aguardando associação, 15 em revisão, 3 associadas |
| Sem número / chave | 11 (32%) / 30 (88%) |
| Sem valor | 14 (41%) |
| Sem vencimento | 9 (26%) |
| Sem nome do emissor | 7 (21%) |
| Sem data de emissão | 27 (79%) |
| Marcadas para revisão manual | 17 |
| Notas lançadas | 6, sendo 1 sem número |
| Locais | 10 (7 agências, 2 garagens, 1 rodoviária) |

Parte dos vazios é documento que não é cobrança. Hoje não existe como registrar isso (não há "descartar"), o que impede medir a acurácia real. Ver P5.

### 3.2 Ambiente

Situação em 12/11/2026, depois da preparação (P0):

- O `.venv-1` apontava para o Python de outro usuário (`C:\Users\Fredson\...`) e não iniciava. Foi renomeado para `.venv-1-antigo` (pode ser apagado) e recriado com o Python 3.14.7 e as dependências do `requirements.txt`.
- **Linha de base dos testes Python:** 60 testes, 59 passam. A falha já existia antes das correções: `test_legacy_received_gmail_table_migrates_to_per_attachment_deduplication` (`tests/test_fluxo_alvo.py:679`). A migração de uma tabela legada de notas recebidas não cria a coluna `nota_lancada_id`. Não afeta o banco atual, que já tem a coluna, mas deve ser corrigida.
- **A interface na porta 8000 é servida por um container nginx (`sigp_web`)**, que monta `agencias.html` e `frontend/` do repositório e responde com `no-cache`. Mudanças na interface valem ao recarregar a página. O README ainda cita `http.server`; está desatualizado. Já o **backend é copiado para dentro da imagem**: mudanças em `backend/` exigem `docker compose up -d --build api`.
- **Testes no navegador:** `tests/e2e/` (Playwright com o Edge instalado, `playwright-core` 1.65.0 fixo). Rodam contra uma **API de teste** (container `sigp_api_test`, porta 5011, dados copiados do backup em `tests/e2e/.data-test`) e se recusam a apontar para a API real (5001). Usam o n8n e o OCR locais apenas para extrair. Comandos: `node tests/e2e/c1_chave_api.js` e `node tests/e2e/c2_fatura_provedor.js`.

## 4. Inventário dos extratores (onde estão, função, dependências)

### 4.0 Fluxo real nas localidades (agências, rodoviárias e garagens)

Descrição do usuário comparada com o código (`frontend/modules/notas-locais.js`, `faturas-provedores.js`, `api-client.js`, `agencias.html`):

| Passo | Como o usuário descreve | Como o código funciona hoje | Conferência |
|---|---|---|---|
| Fatura PDF do provedor | Modal, escolhe o PDF, pede extração, valida e usa; fica gravado | `openForProvider` abre o modal; "Extrair dados" envia o PDF ao webhook `sigp-faturas-pdf` (**WF-03 no n8n**, nó E4); o usuário revisa; "Salvar" grava `POST /api/faturas`, a nota lançada de referência (opcional) e atualiza o provedor do local | **Confere**, mas só abre depois de salvar o nome do provedor e reabrir o cadastro (C2, seção 10.2) |
| Adicionar NFS-e | Modal, escolhe a NFS-e, pede ao n8n para extrair, revisa e usa | "Importar NF · Nota lançada" abre o editor; aceita **XML ou JSON**, que é lido **no navegador** (`importarNotaArquivo`, E8). **O n8n não extrai nada aqui.** Para **PDF** a tela diz "preencha manualmente". Os dados vão para a API ao salvar o local (`syncRecord`) | **Diferente**: extração local no navegador, PDF sem extração |
| Marcar como pago | Modal, escolhe a nota paga ou a mesma nota, n8n extrai, preenche o valor pago, revisa e usa | Mesmo editor com `tipo = paga`: XML/JSON lidos no navegador; valor pago e data digitados; PDF não é lido | **Diferente**: igual à NFS-e |
| Envio ao n8n | O sistema envia ao n8n para conciliar e analisar | As notas passam pelo n8n só como **repasse**: `api-client.js` chama os webhooks `sigp-nota-lancada` (WF-01) e `sigp-nota-paga` (WF-02), que apenas repassam o corpo à API (com queda direta na API se o n8n não responder). **A conciliação é feita no backend** (`reconciliation.py`); a API então emite o evento ao WF-05, que faz a **análise** (texto por LLM, gravação no SIG/SIE e notificações) | **Parcialmente diferente**: n8n não concilia |
| Envio individual | Pode enviar cada documento sozinho | Sim. A API aceita lançada, paga e fatura em qualquer ordem | Confere |
| Regra das três evidências | Só concilia e analisa com as três | **Não é assim hoje.** O backend concilia com duas (`PAGO_PARCIAL`, `AGUARDANDO_FATURA`, `DIVERGENCIA`) e o WF-05 gera análise para `MATCH`, `DIVERGENCIA`, `AGUARDANDO_FATURA`, `PAGO_PARCIAL` e `PENDENTE`. Só o `MATCH` (três evidências) gera análise executiva (SIE) e só `MATCH` e `DIVERGENCIA` geram notificação | **Mantido por decisão do usuário (D12)**; a análise por LLM será construída em P6 |

Consequência: a extração por LLM só alcança hoje a fatura em PDF (modal do provedor) e as Notas recebidas (Gmail). **NFS-e e nota paga em PDF não têm extração nenhuma**; ficam como ajuste futuro (D11, F-01).

Também importa para os alertas: o modal da fatura é o único que atualiza `valor`, `dataVencimento` e `diaVencimento` do provedor no local, e isso acontece no navegador. A associação de Notas recebidas não faz o mesmo (problema 2.5).

### 4.1 Visão geral

Há **quatro caminhos de leitura de PDF**, que passam por **um OCR comum**, mais **dois normalizadores de XML/JSON** (fluxo complementar) e **uma camada de classificação**. A tabela resume cada peça.

### 4.2 Mapa

```text
PDF ─► E1 OCR (ocr/app.py, porta 5002) ─► texto
          ├─► E2 Python  _extract_invoice_fields ─► botão "Extrair dados do PDF" (aba Notas recebidas)
          ├─► E3 JS      wf08_lib.extrairCampos  ─► WF-08 (Gmail, automático) ─► + E5 + E6 ─► consolidar
          └─► E4 JS      WF-03 nó "Identificar dados da fatura" ─► aba Faturas (por local, manual)

XML/JSON NFS-e ─► E7 backend/normalizer.py  (POST /api/notas/lancadas, /pagas)
              └─► E8 frontend/notas-fiscais.js (importação na interface, espelho do E7)
```

### 4.3 Detalhe

| ID | Peça | Onde | Função | Entrada → saída | Depende de | Usado por |
|---|---|---|---|---|---|---|
| E1 | OCR | `ocr/app.py` | `pdftotext -layout`; se vazio, `pdftoppm` + Tesseract (por, psm 11). Normaliza datas com mês por extenso e "Emissão desta conta". Limites: 15 MiB, 10 páginas, 1 PDF por vez (semáforo). | PDF → `{text, ocrUsado}` | Poppler, Tesseract (container) | E2, WF-03, WF-08 |
| E2 | Extrator Python | `backend/app.py:1345` `_extract_invoice_fields`; rota `/api/notas-recebidas/<id>/extrair` (1508) | Regex em camadas (inline e coluna) para emissor, número, chave, série, descrição, emissão, vencimento, valor, CNPJs; linha digitável prevalece em valor e vencimento. Mescla com o que já estava salvo (só preenche vazios). | texto → campos + `camposParaRevisar` | E1 via `SIGP_OCR_URL`; PDF salvo em `backend/data/notas_recebidas/` | Botão na aba Notas recebidas (`notas-recebidas.js:196`, mapa de campos na linha ~202) |
| E3 | Extrator JS do WF-08 | `n8n/wf08/wf08_lib.js` (`extrairCampos`, `consolidar`) embutido em nós Code por `build_wf08.ps1` | Mesmas ideias do E2, mais empresa destinatária por lista fixa `EMPRESAS_DO_GRUPO`, descarta emissor que seja empresa do grupo, `consolidar` junta regras + extração + IA e decide `importar`/`ignorar`. | texto + IA → `dadosExtracao` | E1, E5, E6; `testes_wf08.js`, `verificar_sintaxe.js`; ID do workflow `5sQcHD7eYRgHxqgK` | WF-08 (gatilho Gmail a cada 5 min e busca histórica), grava via `POST /api/notas-recebidas` |
| E4 | Extrator do WF-03 | `n8n_workflow_extrair_fatura_pdf.json`, nó Code (≈5 KB) | Regex mais simples (valor só com rótulos "total da fatura/conta", "a pagar"; emissor por palavras "telecom/internet"; sem linha digitável). Devolve **comparação** com o esperado (`provedorEsperado`, `valorEsperado`, `vencimentoEsperado`). Marca todos os campos para revisão. | texto + query → `numeroFatura`, `emissorNome`, `cnpjCandidatos`, `comparacao`… | E1; parâmetros de query vindos da aba Faturas | `frontend/modules/faturas-provedores.js` (webhook `sigp-faturas-pdf`) |
| E5 | Classificador por regras | `backend/app.py:1107` `/api/notas-recebidas/classificar` | Categoria e confiança por termos fiscais/internet, provedores cadastrados nos locais e e-mail do remetente. Não extrai campos. | texto + assunto + remetente → categoria | `list_locais()` (provedores e e-mails) | WF-08 |
| E6 | LLM (Qwen 2.5 3B no Ollama) | nó "Classificar com Qwen" do WF-08; `prompt_classificacao.md`, `schema_classificacao.json` | Classifica o tipo do documento e sugere provedor, destinatário, número, valor, vencimento, competência, com confiança. Temperatura 0, JSON Schema. Cerca de 58 s por PDF em CPU. | texto compactado (3.000 caracteres) + meta → JSON | container Ollama (`SIGP_OLLAMA_URL`/`MODEL`), E1 | WF-08 (`consolidar`) |
| E7 | Normalizador XML/JSON | `backend/normalizer.py` | Converte NFS-e/NFCom em nota padronizada (id, número, serviços, `xInfComp` → vencimento). | XML/JSON → nota | formatos municipais | `POST /api/notas/lancadas` e `/pagas` (`app.py:652,690`) |
| E8 | Normalizador no navegador | `frontend/modules/notas-fiscais.js` (`parseXmlImportado`, `normalizarNFSE`, `extrairDataVencimentoXInfComp`) | Lê o XML/JSON da NFS-e e da nota paga **no navegador**, antes de enviar ao backend. Espelho do E7. **Não passa pelo n8n.** | XML/JSON → nota | `localStorage`; `salvarNotaLancadaBackend` | Modais "Importar NF · Nota lançada" e "Marcar como pago" das localidades (`notas-locais.js`), formulário da aba NFS-e em `agencias.html` |
| E9 | IA acadêmica | `docs/entrega-academica/ia/app.py` (`_normalize_invoice`) | Normaliza fatura para o parecer de contrato (RAG sintético, Qwen 0.5B, LoRA opcional). **Não extrai do PDF.** | JSON de fatura → parecer | SQL Server acadêmico, Ollama próprio | WF-05 (parecer) |
| — | WF-01/02 (nós Code) | `n8n_workflow_wf01…`, `wf02…` | Só repassam o corpo à API e definem `origem`. Validação é do backend. | — | API | Interface e Praxio/Globus |

### 4.4 Divergências entre E2, E3 e E4 (confirmadas na leitura)

| Aspecto | E2 Python | E3 WF-08 | E4 WF-03 |
|---|---|---|---|
| Nome do campo do número | `numero` | `numero` | `numeroFatura` |
| Número em coluna "Nº Documento" | sim | sim | **não** |
| Número curto "Nº.: 16713" | sim | sim | **não** |
| Linha digitável (valor e vencimento) | sim | sim | **não** |
| Rótulos de valor | 8 | 5 | 4 |
| Emissor | Rótulos Beneficiário/Prestador/Cedente | idem, mais IA e remetente, exclui empresa do grupo | Palavras "telecom/internet…" |
| Destinatário | CNPJ por rótulo | lista fixa de empresas do grupo | não extrai |
| Divergência entre fontes | não sinaliza | sinaliza (`divergencias`) | não aplica |
| Data de emissão | rótulos "emissão", "data do documento" | idem | só "emissão"/"emitida em" |
| `camposParaRevisar` | nome, valor, emissão, vencimento | + tipo, confiança, divergências | **todos, sempre** |
| Testes | nenhum | `testes_wf08.js` | nenhum |

### 4.5 O que pode e o que não deve ser integrado

| Grupo | Peças | Decisão | Motivo |
|---|---|---|---|
| Extração de campos a partir de **texto OCR** | E2, E3 (parte determinística), E4 | **Integrar** em uma implementação única no backend | Mesma entrada, mesma saída, regras duplicadas e divergentes |
| Classificação | E5 | **Integrar no mesmo pacote** (mesma chamada) | Hoje o WF-08 faz duas chamadas HTTP em sequência sobre o mesmo texto |
| LLM | E6 | **Manter a chamada no n8n**, mas a decisão final (`consolidar`) passa para o backend | O Ollama leva ~58 s por PDF; manter a espera no n8n evita timeout no waitress e deixa a chamada visível no editor. O backend recebe o JSON da IA e consolida |
| OCR | E1 | **Manter** como serviço único | Já é compartilhado |
| XML/JSON | E7, E8 | **Fora do escopo agora**. Só aplicar nele as mesmas regras de chave/número padrão e validação | Entrada diferente (estruturada). O espelho no navegador (E8) deve virar chamada ao E7 numa etapa futura |
| IA acadêmica | E9 | **Não integrar** | Stack isolada com dados sintéticos, tarefa diferente (parecer de contrato) |

## 5. Plano de integração dos extratores (P4)

### 5.1 Arquitetura-alvo

```text
              ┌────────────────────────── backend/extracao/ (novo) ──────────────────────────┐
PDF ─► E1 ─►  │ campos.py     constantes, normalizar_numero/chave, validar_campos            │
texto         │ extrator.py   extrair_campos(texto, contexto) → campos + fontes + revisão     │
              │ classificar.py  regras do E5                                                  │
              │ consolidar.py  junta extração + regras + IA (porta do consolidar do WF-08)    │
              └───────────────────────────────────────────────────────────────────────────────┘
   Endpoints:  POST /api/extracao/campos        (texto, contexto opcional)    ← botão Notas recebidas, aba Faturas (via WF-03 enxuto), WF-08
               POST /api/extracao/consolidar    (texto, ia, meta)             ← WF-08 depois do Qwen
   Compatibilidade: /api/notas-recebidas/<id>/extrair e /classificar continuam, chamando o pacote.
```

Contrato de saída (único): `numero`, `chave`, `serie`, `emissorNome`, `cnpjEmissor`, `empresaDestinataria`, `cnpjDestinatario`, `valorTotal`, `dataEmissao`, `dataVencimento`, `descricaoServico`, `linhaDigitavel`, `fontes{campo→origem}`, `camposParaRevisar[]`, `avisos[]`, `numeroPadrao`/`chavePadrao`/`dataEmissaoOrigem`. O WF-03 continuará devolvendo `numeroFatura` e `comparacao` (alias), para não quebrar `faturas-provedores.js`.

### 5.2 Etapas

| ID | Tarefa | Critério de aceite | Status |
|---|---|---|---|
| P4-01 | **Testes de caracterização**: reunir textos de OCR (fictícios ou anonimizados) e registrar a saída atual de E2, E3 e E4 | Conjunto único (≥ 30 casos) com saída esperada; roda contra Python e contra JS; mostra as divergências da seção 4.4 | `[x]` `tests/e2e/comparar_extratores.py`: 29 textos OCR reais distintos, WF-03 antigo x backend |
| P4-02 | Criar `backend/extracao/` com o contrato único e portar a **união** das regras (a mais completa de cada campo) | Todos os casos de P4-01 passam; nenhum caso que E2 resolvia piora | `[~]` união das regras no extrator do backend (rótulos do WF-03, emissor por linha, datas no meio da linha, CNPJ perto do emissor); módulo `backend/extracao/` ainda não separado |
| P4-03 | Expor `POST /api/extracao/campos` (e `/consolidar`) e fazer `/extrair` e `/classificar` chamarem o pacote | Respostas antigas continuam válidas (campos e `camposParaRevisar`) | `[x]` `POST /api/extracao/texto` (não grava nada) |
| P4-04 | Migrar o **botão da aba Notas recebidas** (menor risco, já usa E2) | UI inalterada, mesmos campos; testes de `notas-recebidas.js` manuais | `[x]` o botão de Notas recebidas já usava o extrator do backend |
| P4-05 | Migrar o **WF-03 (aba Faturas)**: nó Code vira chamada ao backend; mantém `comparacao` e `numeroFatura` | `faturas-provedores.js` funciona sem alteração; ganha linha digitável e demais regras | `[x]` WF-03 chama o backend; versão anterior em `n8n_workflow_extrair_fatura_pdf.legado.json`; publicado |
| P4-06 | Migrar o **WF-08**: depois do OCR, uma única chamada ao backend (extração + classificação); depois do Qwen, `/consolidar`. Regenerar o JSON com `build_wf08.ps1` | Mesmo resultado no lote de referência (20 mensagens); menos nós Code | `[ ]` |
| P4-07 | Mover `EMPRESAS_DO_GRUPO` para configuração do backend (hoje fixa no `wf08_lib.js` e repetida no prompt) | Uma lista, editável sem regenerar o workflow | `[ ]` |
| P4-08 | Remover as cópias antigas (E2 interno, `wf08_lib.js`, nó do WF-03) e atualizar `README.md` e `n8n/wf08/README.md` | Nenhum extrator duplicado restante | `[ ]` |
| P4-10 | **Ajuste futuro (F-01, D11):** extração de PDF nos modais "NFS-e" e "Marcar como pago" pela própria LLM. Detalhes na seção 9.5 | Fora do ciclo atual | `[!]` futuro |
| P4-09 | Reimportar o WF-03 e o WF-08 no n8n e atualizar os scripts de instalação (`instalarsigp.bat` publica só alguns IDs) | Workflows publicados e testados nos dois caminhos | `[ ]` |

Reversão: cada migração (P4-04, P4-05, P4-06) deve poder voltar ao comportamento antigo com um sinalizador (`SIGP_EXTRACAO_UNIFICADA=0`) até P4-08, e o JSON antigo do workflow deve ser guardado no Git.

Riscos: (1) o E4 hoje extrai nomes com "telecom/internet", o que o E2 não faz; o teste de caracterização precisa cobrir esse caso para não perder cobertura. (2) A porta do `consolidar` para Python precisa manter a regra "linha digitável prevalece" e a de não ignorar documento com falha de IA. (3) O texto do `sigp-faturas-pdf` já passou pelo OCR no WF-03; se o backend chamar o OCR de novo, haverá OCR duplicado. Em P4-05 o n8n envia o texto, não o PDF.

### 5.3 Resultado da caracterização (12/11/2026)

29 textos OCR distintos (34 notas recebidas e faturas da base de teste, cópia dos dados reais). Sem gabarito: conta quantos campos cada extrator preenche; as divergências foram conferidas no texto.

| Campo | WF-03 antigo | Backend unificado | Só o antigo achou |
|---|---|---|---|
| Emissor | 16 | 25 | 0 |
| Número | 4 | 9 | 3 (todos lixo: "Emissor", "Compet") |
| Emissão | 7 | 19 | 0 |
| Vencimento | 12 | 19 | 0 |
| Valor | 2 | 18 | 0 |
| CNPJ do emissor | 9 | 17 | 0 |

Erros do antigo encontrados: vencimento trocado pela emissão em boletos com cabeçalho "Emissão / Vencimento"; "CNPJ" tirado da linha digitável; emissor = título do documento ("FATURA / NOTA FISCAL…", "(+) PROVIMENTO…"). Lacunas do backend que foram corrigidas: emissor como rótulo ("Prestador", "DANFECom", "Agência/Código beneficiário"), prefixos ("Razão Social:", "PROVEDOR / PRESTADOR:"), "Valor total da fatura/conta", datas no meio da linha ("DATA DE VENCIMENTO: …").

Pendente em P4: WF-08 (Gmail) ainda usa `wf08_lib.js`; migrar para `/api/extracao/texto` (P4-06) e remover as cópias (P4-08).
## 6. Ponto 1 — Extração correta (chave e número padrão, datas)

### 6.1 Problemas confirmados

| # | Problema | Onde |
|---|---|---|
| 1.1 | Não existe nenhum valor padrão. Número e chave vazios permanecem vazios e, sem chave e sem número, a associação é bloqueada (30 de 34 notas não têm chave). | `app.py` (associar), `database.py` `integrar_nota_recebida` |
| 1.2 | "Preenchido incorretamente" não é detectado (por exemplo, o número capturar um CNPJ, uma data, um valor ou um rótulo; a chave com tamanho errado). O E2 só descarta CNPJ na coluna "Nº Documento". | extratores |
| 1.3 | A releitura só preenche vazios: um valor ruim salvo antes nunca é corrigido por uma extração melhor. | `app.py` `extrair_nota_recebida` |
| 1.4 | O placeholder seria tratado como identidade real em: `invoice_identity_matches` (`reconciliation.py`), `_find_duplicate_document` (`database.py`; com chave, compara `lower(trim(chave))`) e `_compare_received_invoice` (`app.py`). Duas notas diferentes com o mesmo placeholder se fundiriam ou receberiam 409. **Isso é mais grave para a chave** do que para o número. | `reconciliation.py`, `database.py`, `app.py` |
| 1.5 | A busca de data de emissão cobre só "emissão", "data do documento" (coluna) e "emitida em". Faltam "data da fatura", "data de emissão da fatura", "emitido em", "data de processamento". Nada registra de onde a data veio. | E2, E3, E4 |
| 1.6 | A interface, ao extrair, sobrescreve o que o usuário já digitou nos campos (`notas-recebidas.js:~210`). | `notas-recebidas.js` |

### 6.2 Plano

| ID | Tarefa | Critério de aceite | Status |
|---|---|---|---|
| P1-01 | Módulo `campos.py` (e espelho no WF-03 até P4-05): constante do valor padrão, `numero_invalido(v)`, `chave_invalida(v)`, `aplicar_padrao_identificacao(campos)` | Vazio, só espaços, só zeros, CNPJ/CPF, data, valor monetário, só letras (rótulo), tamanho > 80 → número inválido. Chave: diferente de 44 dígitos (confirmar tamanho aceito para NFS-e nacional) → inválida. Inválido ou vazio vira padrão e entra em `camposParaRevisar` com `numeroPadrao`/`chavePadrao: true`. Guardar o valor lido original em `numeroOriginal`/`chaveOriginal` quando houver | `[x]` `backend/campos.py` |
| P1-02 | Aplicar o padrão no fim de cada extrator e na associação | Nenhum fluxo termina com número ou chave vazios. **Valor, vencimento e nome nunca recebem padrão** (D1). | `[~]` backend (extração, importação do Gmail, associação) e modal da fatura; o WF-08 em si ainda não, mas o backend aplica a regra ao receber |
| P1-03 | Regra de atualização | Dado real substitui padrão; padrão nunca substitui dado real; dado real novo diferente de dado real antigo exige ação do usuário (ou extração com fonte mais confiável, como linha digitável). Valor ruim salvo antes pode ser corrigido pela releitura quando a fonte nova é melhor (campo `fontes`) | `[x]` `mesclar_identificacao` |
| P1-04 | **Neutralizar o padrão nas comparações** (fazer antes de gravar qualquer padrão) | `invoice_identity_matches`, `_find_duplicate_document`, `_compare_received_invoice` e índices de chave ignoram o padrão. Teste: duas notas de meses diferentes, mesmo provedor, ambas com padrão, convivem sem 409 nem match | `[x]` conciliação, duplicidade, comparação, correção e indicadores do SIG |
| P1-10 | Aplicar a regra nas **entradas por XML/JSON e nos modais das localidades** (fluxo complementar) | Remover os bloqueios "Informe a chave ou o número" em `notas-locais.js` (submit do editor), `agencias.html` (`btnSalvarNFSE`, `validarPagamentoNFSE`) e no backend; chave/número vazios ou inválidos viram `999999999` com aviso. Na aba NFS-e de `agencias.html`, `validarPagamentoNFSE` procura a lançada **por chave ou número**: com o padrão ele pegaria a nota errada; passar a exigir seleção explícita da nota quando o identificador for o padrão. Nos modais das localidades o par lançada/paga já é explícito (`notaLancadaId`) | `[~]` editor de nota do local e API (`/api/notas/lancadas` e `/pagas`) aplicam o padrão, exigindo o provedor; falta o formulário da aba NFS-e em `agencias.html` |
| P1-09 | Busca ampliada da data de emissão | Rótulos: "data de emissão", "emissão", "emitida/emitido em", "data da fatura", "data do documento", "data de processamento", em linha e em coluna. Ordem de preferência registrada. Se nada for achado: `dataEmissao` = data de recebimento (`recebida_em`, ou `created_at` se vazio) e `dataEmissaoOrigem = "recebimento"`; caso contrário `"documento"` + o rótulo usado. Nunca bloquear a associação por falta de emissão | `[x]` rótulos ampliados e data de recebimento com origem registrada |
| P1-05 | Não sobrescrever o que o usuário digitou | A extração na interface só preenche campos vazios ou que ainda estão com o valor original da extração anterior; destaca os campos alterados | `[x]` |
| P1-06 | Replicar na extração manual dos locais (aba Faturas) | Resolvido por P4-05; até lá, aplicar a regra no nó do WF-03 e no formulário (`numeroFatura`) | `[x]` modal da fatura usa o extrator unificado (via WF-03) e a regra do valor padrão |
| P1-07 | Testes | Número ausente, número inválido (CNPJ, data, rótulo), chave com tamanho errado, padrão não funde notas, real substitui padrão, emissão por cada rótulo, emissão por recebimento com origem registrada | `[~]` `tests/test_campos.py` (8 casos) e verificações na API de teste |
| P1-08 | Retroativo | Rotina com backup prévio: aplica o padrão em notas recebidas e lançadas existentes sem número/chave; preenche emissão por recebimento com origem; relatório do que mudou. Só depois de P1-04 | `[ ]` |

## 7. Ponto 2 — Associação aos locais

### 7.1 Problemas confirmados

| # | Problema | Onde |
|---|---|---|
| 2.1 | Data de emissão é obrigatória na associação e 79% das notas não a têm. | `associar_nota_recebida_route` |
| 2.2 | Chave **ou** número obrigatório trava as notas sem ambos. | `app.py`, `database.py` |
| 2.3 | Sugestão de local só por CNPJ ou nome exato do destinatário; sem destinatário extraído não há sugestão, e o cadastro dos locais pode não ter CNPJ. | `_serialize_nota_recebida_api` |
| 2.4 | Nota candidata por "mesmo emissor + mesmo vencimento": se algum dos dois vier errado, nasce nota duplicada. | `_compare_received_invoice`, `integrar_nota_recebida` |
| 2.5 | Associar **não atualiza o local** (`provedores[].diaVencimento`, `pagoAte`, `valor`, `vencimento_fatura`), que é o que os alertas por provedor e por local leem. | `database.py`, `backend/alerts.py` |
| 2.6 | Dados do local existem no navegador e na API; a associação grava só na API. | `notas-locais.js`, `faturas-provedores.js` |
| 2.7 | Variações do nome do emissor ("ALGAR TELECOM" x "Algar Telecom S/A") dependem de `normalize_company_name`, sem aliases. | `app.py:78` |
| 2.8 | O original extraído não é preservado: ao associar, os campos corrigidos substituem o que veio da extração. Sem isso não há como medir nem aprender (P5). | `app.py`, `database.py` |

### 7.2 Plano

| ID | Tarefa | Critério de aceite | Status |
|---|---|---|---|
| P2-01 | Associar sem exigir emissão | Emissão segue P1-09 (documento → recebimento); registrar `dataEmissaoOrigem` | `[x]` |
| P2-02 | Associar sem exigir chave nem número | Aplica o padrão (P1-01), avisa na interface e segue. Valor, vencimento e emissor continuam obrigatórios; se faltarem, a interface destaca em vermelho, impede associar e pede preenchimento manual | `[x]` valor, vencimento e emissor continuam obrigatórios, destacados na interface |
| P2-03 | Preservar a extração original | Guardar `dadosExtraidos` (snapshot imutável da primeira extração, com `fontes`) e `dadosFinais` na associação; a diferença é o "rótulo" para P5 | `[~]` extraído x confirmado gravados em `extracao_feedback`; o `dados_json` da nota ainda é sobrescrito |
| P2-04 | Atualizar o cadastro do local para os alertas | Depois de associar/salvar fatura, atualizar no backend o provedor do local (`diaVencimento`, `valor`, `dataVencimento`, `faturaAtualId`), com a mesma regra que a aba Faturas já aplica no navegador. É a **mesma função** do modal do provedor (C2-08); se o provedor não existe no local, é criado | `[x]` `backend/provedores.py` + `aplicar_fatura_no_local`; o navegador aplica o mesmo provedor devolvido pela API |
| P2-05 | Nota candidata mais robusta | Prioridade: chave real > (emissor + número real) > (emissor + vencimento + valor). Com chave/número padrão, só o último critério; coincidência apenas de vencimento exige confirmação | `[ ]` |
| P2-06 | Sugestão de local ampliada | Nome parcial normalizado, cidade, CNPJ, remetente e histórico de associações do mesmo provedor (aprendizado de P5). Sempre sugestão com motivo e confiança; nunca associa sozinho | `[~]` sugestão por histórico: provedor já associado ao local e e-mail do remetente cadastrado no provedor |
| P2-07 | Aliases de provedor | Lista de aliases normalizados por provedor, usada na comparação e na sugestão | `[~]` mesma empresa reconhecida pela primeira palavra significativa do nome (ex.: OPIX); lista de aliases editável ainda não |
| P2-08 | Testes | Associar sem emissão e sem número/chave; padrão não funde notas; local atualizado e alerta gerado depois da associação; snapshot preservado | `[~]` associação atualizando o provedor e o alerta (6 verificações na interface) |
| P2-09 | Reavaliar os 31 pendentes depois de P1/P2 e anotar o resultado nas métricas | Seção 9 atualizada | `[ ]` |

### 7.3 Regra única: nota ou fatura associada preenche o provedor do local (decisão do usuário, 12/11/2026)

> "A regra de fato é preencher automaticamente quando associar uma nota, em todos os fluxos."

Ponto único no backend: `_atualizar_provedor_do_local` (`backend/app.py`) → `aplicar_fatura_no_local` (`backend/database.py`) → `aplicar_fatura_no_provedor` (`backend/provedores.py`). Preenche nome (se vazio), valor, data e dia de vencimento e, quando há PDF, a fatura atual.

| Fluxo | Rota | Situação |
|---|---|---|
| Associar nota recebida (Gmail) | `PATCH /api/notas-recebidas/<id>/associar` | aplicado |
| Fatura PDF (modal do provedor e aba Faturas) | `POST /api/faturas` | aplicado (com o id da linha do provedor, quando há) |
| NFS-e / nota lançada no local, WF-01 (n8n), Praxio/Globus | `POST /api/notas/lancadas` | aplicado |
| Fatura pela nota (rota antiga) | `POST /api/notas/lancadas/<id>/fatura` | aplicado |
| Dados antigos | `python -m backend.retroativo_provedores [--gravar]` | executado em 12/11/2026 |

Correspondência do provedor: id da linha → nome normalizado igual → um nome contém o outro → mesma primeira palavra significativa ("OPIX INTERNET" = "OPIX SERVIÇOS DE TECNOLOGIA"). Mais de uma possibilidade: não altera e avisa. Fatura mais antiga que a atual: fica só no histórico. Local inativo: não é alterado.

Navegador: depois de cada gravação, `SIGP_API.refreshLocationProviders` traz da API o provedor atualizado para o cadastro local (sem gravar de volta) e as telas de locais recarregam. Sem isso, salvar o local a partir da tela desfaria a atualização.
### 7.4 Notas recorrentes: atualizar e substituir (decisão do usuário, 12/11/2026)

> "Essas notas serão recorrentes: todo mês a mesma nota, só com a data de vencimento e do documento diferentes. A LLM precisa fazer isso tanto manualmente quanto de forma automática."

**Regra:** mesmo local + mesma empresa + mesmo mês de vencimento = **a mesma cobrança**. A nota que chega atualiza e substitui a existente (ex.: nota fiscal e boleto do mesmo mês), em vez de criar outra. Mês diferente = nota nova, e o provedor do local passa para a fatura mais recente (seção 7.3).

| Item | Onde | Situação |
|---|---|---|
| "Mesma empresa" com nomes diferentes (OPIX INTERNET x OPIX SERVIÇOS…) | `mesma_empresa` (`backend/provedores.py`) | feito |
| Mês da cobrança | `competencia` (`backend/provedores.py`) | feito |
| Associação do Gmail encontra a nota do mês e a atualiza | `encontrar_nota_da_competencia` (`database.py`), `_compare_received_invoice` (`app.py`) | feito |
| Sem confirmação desnecessária: número padrão e nome da mesma empresa não contam como divergência | `_compare_received_invoice` | feito |
| Ao atualizar, o número/chave real da nota existente não é trocado pelo valor padrão | `integrar_nota_recebida` | feito |
| Duplicadas antigas | `python -m backend.unir_notas [--gravar]` (une, repassa notas recebidas, faturas e conciliações e registra na observação o número unido) | executado nos dados reais (OPIX nov/2026, nº 302500); nenhuma duplicada restante |
| Nota lançada direta (NFS-e no local, WF-01) sem número real no mesmo mês | `POST /api/notas/lancadas` (`_aplicar_recorrencia` em `save_nota_lancada`) | feito: nota nova sem número/chave real no mesmo mês atualiza a do mês (mantém número real e nome do provedor); com número real diferente continua sendo outra cobrança; regravar sem número mantém o número real. A tela une as linhas e avisa |
| Gravação do cadastro pela tela não apaga nem faz regredir a fatura atual do provedor | `preservar_fatura_atual` (`database.py`) | feito (corrigiu uma condição de corrida) |

**Caminho da LLM (médio prazo), manual e automático:**

1. **Manual (hoje):** o usuário associa ou descarta; cada ação grava o exemplo em `extracao_feedback` (extraído x confirmado).
2. **Automático assistido (próximo):** ao chegar uma nota, o sistema identifica provedor e local pelas associações anteriores (remetente, CNPJ, nome) e encontra a nota do mês pela regra acima. A LLM só precisa ler o que muda (vencimento, emissão, valor). Os exemplos do mesmo provedor nos meses anteriores entram no prompt (seção 9, camada B).
3. **Automático:** com acurácia medida por provedor (P5-04), as notas de provedores com histórico confiável são associadas sem clique, sempre com a regra determinística como autoridade e com a possibilidade de desfazer.

### 7.5 Interface sem cliques obrigatórios

- Local excluído pela tela fica **inativo** na API (o histórico é preservado). Não há botão "inativar": excluir é inativar. As regras ignoram locais inativos (alertas e preenchimento do provedor).
- O cadastro do local abre sempre com uma linha vazia de provedor e de nota, sem precisar clicar em "+". Linhas que continuam vazias são descartadas ao salvar.
- Provedor e nota também são criados automaticamente pelo backend quando uma nota ou fatura é associada (seção 7.3), o que permite o preenchimento via LLM sem a tela.
## 8. Ponto 3 — Valor, nome, vencimento e campos corretos (obrigatórios)

Prioridade para o alerta: **vencimento > valor > nome do emissor** (obrigatórios, entrada manual se o OCR falhar) > demais campos.

### 8.1 Problemas confirmados

| # | Problema | Onde |
|---|---|---|
| 3.1 | Fator de vencimento do boleto com base fixa (22/02/2025 = fator 1000): fator < 1000 ou boleto antigo viram "sem vencimento". Sem teste de borda nem plausibilidade. | `_ler_linha_digitavel`, `lerLinhaDigitavel` |
| 3.2 | Sem checagem de plausibilidade de valor e data (vencimento de 2019 ou 2040 passam). | extratores, `associar` |
| 3.3 | Quando linha digitável e texto divergem, só o WF-08 sinaliza. | E2 x E3 |
| 3.4 | Nome do emissor não é validado contra o cadastro do local. Pode vir endereço, rótulo ou empresa do grupo. | extratores |
| 3.5 | Não há registro de **origem** de cada campo (linha digitável, rótulo, IA, manual). | `dados_json` |
| 3.6 | Nota lançada sem vencimento ou com valor 0 some dos alertas sem aviso. | `alerts.py` |
| 3.7 | A obrigatoriedade existe no backend (`associar`), mas a interface só mostra um aviso genérico. | `notas-recebidas.js:302` |

### 8.2 Plano

| ID | Tarefa | Critério de aceite | Status |
|---|---|---|---|
| P3-01 | `validar_campos` único (em `campos.py`) | Retorna problemas por campo: valor ≤ 0; vencimento inválido; emissor vazio, empresa do grupo, parecido com endereço ou rótulo. As faixas de plausibilidade ficam configuráveis e **dependem de D6** | `[!]` |
| P3-02 | Campos obrigatórios na interface | Valor, vencimento e nome ficam vazios e destacados quando o OCR não os identifica; o botão de associar só habilita com os três preenchidos; mensagem diz qual campo e por quê | `[~]` Notas recebidas e modal da fatura; faltam os editores de NFS-e/pago (F-01) |
| P3-03 | `fontes` por campo | Cada campo guarda `linha_digitavel`, `rotulo`, `ia`, `manual` ou `recebimento`; a interface destaca campos vindos só da IA | `[ ]` |
| P3-04 | Tratar divergência igual em todos os caminhos | Linha digitável prevalece; divergência com texto/IA vira aviso em `camposParaRevisar` (resolvido pela unificação P4) | `[ ]` |
| P3-05 | Testes de borda do fator de vencimento | Fator 1000, 9999 e fora da faixa | `[ ]` |
| P3-06 | Casar emissor com o cadastro | Sugerir o provedor do local por nome normalizado, alias ou CNPJ; confirmar quando parcial | `[ ]` |
| P3-07 | Alerta de dado incompleto | `/api/alertas` passa a ter o tipo `dado_incompleto` para nota sem vencimento ou valor | `[ ]` |
| P3-08 | Testes | Matriz valor × vencimento × nome com casos válidos e inválidos; divergência boleto x texto; documento sem vencimento | `[ ]` |

### 8.3 Obrigatoriedade nos modais das localidades

| ID | Tarefa | Critério de aceite | Status |
|---|---|---|---|
| P3-09 | Campos obrigatórios nos editores de NFS-e e de nota paga | Hoje o editor só exige chave ou número (e, na paga, valor pago). Passa a exigir **valor, vencimento (lançada) e nome do emissor/provedor**; na paga, **valor pago e data do pagamento**. Chave e número seguem a regra do valor padrão | `[ ]` |
| P3-10 | Modal da fatura: aplicar `validar_campos` e a regra do número | O modal (`faturas-provedores.js`) já exige emissor, vencimento e valor > 0; incluir número padrão (`numeroFatura`) e a origem dos campos | `[ ]` |

### 8.4 Análise de conciliação com LLM no n8n e regra das três evidências (P6)

**Decisões do usuário (12/11/2026):** a conciliação deve passar por uma **análise feita no n8n com LLM**; a regra das três evidências **fica como está hoje** (D12). Interpretação adotada: status parciais continuam existindo no backend e o WF-05 continua analisando eventos parciais (SIG), com a análise executiva (SIE) só quando há as três (`MATCH`). Se a intenção era a regra original (análise somente com as três), avisar para ajustar P6-04.

**Achado importante (correção da v3):** hoje o WF-05 **não usa LLM** na análise. O nó "Montar análise" monta um `prompt`, mas **nenhum nó o envia a um modelo**; o texto gravado é determinístico (`textoBase`). O único LLM do WF-05 é o "Parecer acadêmico (Qwen + RAG)", que usa o modelo de 0,5B com corpus fictício, só roda quando há fatura com provedor, descrição e valor, e é declarado não autoritativo. Ou seja, a análise com LLM da conciliação ainda **não existe**; precisa ser construída.

Estado atual do WF-05, confirmado no JSON:

| Etapa | Comportamento |
|---|---|
| Gatilho | Webhook `sigp-eventos` com `responseMode: onReceived`: responde logo, então uma análise longa **não** estoura o limite de 15 s da API (`events.py`) |
| Filtro | Eventos `conciliacao_atualizada` e `analise_manual`, status `MATCH`, `DIVERGENCIA`, `AGUARDANDO_FATURA`, `PAGO_PARCIAL`, `PENDENTE` |
| Escopo | `MATCH` → SIE; demais → SIG |
| Texto | Determinístico; `prompt` montado e **não usado** |
| Parecer LLM | Só o acadêmico (0,5B, RAG sintético), com `timeout` de 120 s e `continueOnFail` |
| Notificação | Somente `MATCH` e `DIVERGENCIA` |

Desenho proposto:

```text
API (conciliação determinística = autoridade) ─► evento ─► WF-05
   ─► montar resumo + prompt (já existe)
   ─► Ollama local (Qwen 2.5 3B, JSON Schema, temperatura 0)  ◄── NOVO
        saída: conclusao (concorda|diverge|revisar), resumo, pontosDeAtencao[], camposDivergentes[],
               acaoSugerida, confianca
   ─► validar a saída (schema) ─► gravar análise (conteúdo + dados.parecerLLM)
   ─► se a LLM divergir da regra: marcar para revisão humana (sem mudar status nem pagamento)
   ─► fallback: se a LLM falhar ou demorar, grava o texto determinístico atual
```

Princípios:

- A regra determinística do backend continua sendo a **autoridade** do status. A LLM analisa, explica e aponta o que revisar; **não altera status nem aprova pagamento** (consistente com o README e com o `model_is_authoritative: false` do parecer acadêmico).
- A análise roda no **mesmo Ollama** do WF-08. Em CPU, uma chamada leva dezenas de segundos; as duas cargas precisam de fila e limite de concorrência (uma por vez), senão disputam o modelo.
- Para evitar gasto desnecessário, a análise completa por LLM vale para `MATCH` e `DIVERGENCIA`; os parciais podem usar texto determinístico ou LLM curta (D14).
- Os dados continuam locais (Ollama no Docker).

| ID | Tarefa | Critério de aceite | Status |
|---|---|---|---|
| P6-01 | Registrar D12 (manter regra atual) e D13/D14 | Respostas na seção 12 | `[x]` D12 · `[!]` D13/D14 |
| P6-02 | Schema e prompt da análise de conciliação | `schema_analise_conciliacao.json` e prompt em `n8n/` (como o do WF-08), versionados; usa o `prompt` já montado em "Montar análise" | `[ ]` |
| P6-03 | Nó Ollama no WF-05 entre "Preparar entrada acadêmica"/"Escolher texto" | Chamada com `format` (JSON Schema), `timeout` e `continueOnFail`; resposta validada; fallback determinístico | `[ ]` |
| P6-04 | Fila e concorrência | Uma chamada por vez no Ollama compartilhado com o WF-08; eventos pendentes continuam na fila `eventos_saida` e no reenvio do WF-06 | `[ ]` |
| P6-05 | Gravar `parecerLLM` em `dados` e destacar divergência entre LLM e regra | Interface do SIG mostra o parecer e um aviso quando `conclusao != regra`; nenhum status é alterado pela LLM | `[ ]` |
| P6-06 | Campo explícito `evidencias` (lançada, paga, fatura) no evento | O WF-05 decide o escopo (SIG/SIE) e o tipo de análise sem inferir pelo status | `[ ]` |
| P6-07 | Botão "Enviar para análise" informa as evidências que faltam (`analysis-dispatcher.js`) | Mensagem clara; análise manual segue permitida, rotulada como parcial | `[ ]` |
| P6-08 | Decidir o destino do parecer acadêmico (0,5B, corpus sintético) | Manter como experimental separado, ou substituir pela análise nova; nunca misturar as duas conclusões sem rótulo | `[!]` |
| P6-09 | Testes | Eventos com 1, 2 e 3 evidências; LLM indisponível (fallback); resposta fora do schema; divergência LLM x regra; duas análises simultâneas | `[ ]` |
| P6-10 | Alimentar o aprendizado (P5): guardar parecer da LLM x decisão humana | Decisões de `sig_decisoes` (aprovar/rejeitar, hoje no `buscador_nfse.db` do painel legado) vinculadas ao parecer, como rótulo de acerto da LLM | `[ ]` |
## 9. Ponto 4 — Aprendizado da LLM (descartar + feedback da associação) (P5)

### 9.1 Situação atual

- A LLM do fluxo real é o **Qwen 2.5 3B no Ollama** (WF-08). O prompt é fixo, sem exemplos, e não aprende nada com o uso.
- O experimento **LoRA** da entrega acadêmica usa outro modelo (Qwen 0.5B), outra tarefa (classificar fatura x contrato sintético) e dados fictícios. Não serve de base para a extração das notas reais.
- Existem 34 notas recebidas, 3 associadas. É pouco para ajuste fino de modelo; mas o desenho de coleta pode começar já, e outras técnicas melhoram a acurácia sem treinar o modelo.
- Não há como marcar uma nota como "não é cobrança". Os 15 itens em Revisão misturam documentos inválidos com erros do extrator.

### 9.2 Proposta (em camadas, do mais barato ao mais caro)

| Camada | O que é | Quando compensa |
|---|---|---|
| A. Coleta de feedback | Gravar cada associação e cada descarte como exemplo rotulado: texto OCR, extração original, valores corrigidos pelo usuário, provedor, local, motivo do descarte | Já. É pré-requisito das demais |
| B. Exemplos no prompt (few-shot por recuperação) | Ao processar um PDF, buscar nas notas **já associadas** as mais parecidas (mesmo provedor/remetente ou mesmo layout) e incluir 1–3 exemplos (texto resumido → campos corretos) no prompt do Qwen | Poucas dezenas de exemplos por provedor. Melhora sem treinar. Dados ficam locais |
| C. Regras por provedor | Para provedores recorrentes, guardar o "modelo" do layout (rótulos, colunas, posição) aprendido nas associações e aplicar antes da IA | Provedor com ≥ 3 notas associadas |
| D. Ajuste fino (LoRA) do modelo de extração | Treinar com o conjunto rotulado (extração → valores corretos) | Só com volume e diversidade: sugestão inicial ≥ 300 exemplos rotulados e várias dezenas de descartes (estimativa; validar com o primeiro ciclo de métricas) |

Observação de segurança e privacidade: as notas reais têm CNPJ, valores e endereços. Todo o aprendizado deve ficar **no ambiente local** (backend SIGp e Ollama). Não misturar com a stack acadêmica, que declara usar somente dados sintéticos.

### 9.3 Botão "Descartar nota" (aba Notas recebidas)

Comportamento proposto:

- Novo status `DESCARTADA` (reversível), com `motivo` (lista: não é cobrança de internet, duplicada, ilegível/ sem texto, outro provedor fora do escopo, outro) e texto livre, `operador` e data. O PDF e o registro **não são apagados**.
- Sai da fila de pendentes e não entra nas métricas de "faltantes". Há filtro "Descartadas" com botão **Restaurar**.
- Cada descarte vira exemplo negativo (`tipoDocumento = "outro"`) para a classificação do Qwen/regras e, se o remetente se repetir, sugere uma regra ("remetente X: sempre descartar") **sempre com confirmação**, nunca automática.
- Opcional: aplicar a etiqueta Gmail `SIGp/Descartado` pelo fluxo de etiquetas (WF-09).

### 9.4 Plano

| ID | Tarefa | Critério de aceite | Status |
|---|---|---|---|
| P5-01 | Status `DESCARTADA` + `PATCH /api/notas-recebidas/<id>/descartar` e `/restaurar`; tabela/colunas para motivo, operador, data | Auditado (evento `nota_recebida_descartada`); testes de API | `[x]` `PATCH .../descartar` e `.../restaurar` |
| P5-02 | Botão Descartar/Restaurar na aba Notas recebidas, filtro e contador | Confirmação com motivo; item some da fila | `[x]` |
| P5-03 | Tabela `extracao_feedback`: nota, texto OCR (ou hash + caminho), `dadosExtraidos`, `dadosFinais`, `fontes`, provedor, local, tipo (`associada`/`descartada`), motivo, data | Preenchida automaticamente em associar e descartar (depende de P2-03) | `[x]` tabela `extracao_feedback` (associação e descarte) |
| P5-04 | Métrica de acurácia por campo | Relatório (`GET /api/extracao/metricas`): % de campos que o usuário **não** alterou, por campo, por provedor e por extrator; taxa de descarte. Linha de base com as 3 associadas + 34 | `[ ]` |
| P5-05 | Exemplos recuperados no prompt (camada B) | Nó do WF-08 pede ao backend até 3 exemplos do mesmo provedor/remetente; prompt ganha a seção de exemplos. Comparar a acurácia antes/depois no mesmo lote | `[ ]` |
| P5-06 | Regras por provedor (camada C) | Layout aprendido guardado por provedor; aplicado antes da IA; revisão humana permanece | `[ ]` |
| P5-07 | Exportar o conjunto rotulado (JSONL) para ajuste fino futuro e definir o gatilho (volume mínimo e métrica) | Exportação local; decisão de treinar tomada com os números de P5-04 | `[ ]` |
| P5-08 | Ajuste fino do modelo de extração (camada D) | Só após o gatilho de P5-07; avaliação em conjunto separado (sem repetir cenários entre treino e teste, falha apontada no experimento acadêmico) | `[!]` |

### 9.5 Ajuste futuro F-01 — NFS-e e nota paga em PDF pela própria LLM

Decisão (D11): fica para depois, usando a mesma esteira de extração com LLM. Isso também gera exemplos rotulados para o treinamento. Não entra no ciclo atual.

Notas de projeto, para quando for retomado:

- **Entrada:** os modais "Importar NF · Nota lançada" e "Marcar como pago" passam a aceitar PDF. XML e JSON continuam lidos no navegador (E8), sem mudança.
- **Esteira:** PDF → OCR (E1) → extração unificada (P4) → Qwen com schema próprio → revisão no modal → gravação. O `tipoDocumento` do schema ganha `nfse` e `comprovante_pagamento`.
- **Nota paga:** campos extras `valorPago` e `dataPagamento`, e vínculo com a nota lançada escolhida no modal (par explícito).
- **Regras iguais às demais entradas:** valor padrão `999999999` para chave/número, valor/vencimento/nome obrigatórios, data de emissão com fallback para recebimento.
- **Aprendizado:** cada correção feita no modal grava um registro em `extracao_feedback` (P5-03), com o tipo do documento.
- **Pré-requisitos:** P4 (extração unificada) e P5-03 (tabela de feedback).

| ID | Tarefa | Status |
|---|---|---|
| F-01 | Implementar a extração de PDF nos dois modais conforme as notas acima | `[!]` futuro |
## 10. Correções de comportamento na interface (C1 e C2)

Dois comportamentos incorretos relatados em uso. Ambos foram investigados no código.

### 10.1 C1 — Chave da API pedida a cada login

**Relato:** a tela de login mostra "Conexão com a API SIGp — Chave da API (X-API-Key)" e pede a chave a cada acesso.

**O que o código faz hoje (verificado em `agencias.html` e `api-client.js`):**

- O bloco `#apiKeySetup` é HTML fixo dentro da tela de autenticação, sem `display:none`. Ele aparece **em todo login**, mesmo com a chave já salva em `localStorage` (`sigp_api_key`). Nada em `initAuth()` consulta se a chave existe antes de exibi-lo.
- A chave é salva em `localStorage` só depois de validada por `POST /api/auth/verify` (`agencias.html:5732`). Portanto, em princípio ela persiste entre sessões. O que se repete é a **exibição** do bloco.
- O pedido pode ser real (e não só visual) quando a API devolve 401 depois do login. `showApp()` chama `initializePersistentData()`, que faz `PUT` nos cadastros; com chave ausente ou diferente da do `.env`, volta 401 e a tela cai de novo em "A API recusou a chave".
- A API informa se exige chave: `GET /api/health` devolve `autenticacao: true/false`. A interface não usa esse dado.
- O `.env` desta máquina tem `SIGP_API_KEY` definida, então a API exige a chave em toda escrita.

**Hipóteses que ainda precisam ser confirmadas no navegador (não verificadas):**

1. A chave não persiste: outra origem (`localhost:8000` x `127.0.0.1:8000`, que têm `localStorage` separados; o iniciador abre `127.0.0.1`), modo privativo ou limpeza do armazenamento ao fechar.
2. A chave salva deixou de valer (o `.env` mudou ou os containers foram recriados com outro valor), então o 401 reaparece.
3. Só o bloco aparece, sem 401 (comportamento visual).

**Comportamento correto:** pedir a chave **uma única vez** por navegador. Depois, entrar direto. O bloco só aparece quando (a) a API exige chave **e** não há chave salva, ou (b) a API recusa a chave salva (401), com mensagem clara. A chave continua trocável em Configurações > Integração.

| ID | Tarefa | Critério de aceite | Status |
|---|---|---|---|
| C1-01 | Diagnosticar no navegador (F12 > Application > Local Storage): conferir se `sigp_api_key` existe após fechar e reabrir, e qual origem está em uso | Causa registrada nesta seção (hipótese 1, 2 ou 3) | `[x]` hipótese 3 (visual) confirmada no navegador; a chave persiste |
| C1-02 | Ocultar `#apiKeySetup` por padrão | Com chave salva e válida, o login não mostra o bloco | `[x]` |
| C1-03 | Decidir a exibição no carregamento: ler `GET /api/health` (`autenticacao`) e testar a chave salva com `POST /api/auth/verify`. Mostrar o bloco só se a API exigir chave e (não houver chave ou o `verify` falhar) | Casos: sem exigência → nunca mostra; com chave válida → nunca mostra; sem chave ou inválida → mostra com mensagem | `[x]` |
| C1-04 | Mover o pedido da chave para **depois** do login de usuário, ou para uma tela própria, em vez de dentro do formulário de login | O login de usuário e a configuração da API deixam de se misturar | `[~]` o bloco só aparece quando necessário, mas continua na tela de login |
| C1-05 | Tratar 401 em `showApp()` sem perder o fluxo | Ao receber 401, abre o pedido da chave e, ao validar, continua para o app sem novo login de usuário | `[~]` o pedido reaparece no 401; falta testar o retorno ao app após informar a nova chave |
| C1-06 | Normalizar a origem | Se a página abrir por `localhost`, avisar ou redirecionar para `127.0.0.1` (a mesma origem do iniciador), para não perder o `localStorage` | `[ ]` |
| C1-07 | Testes manuais registrados | Cenários: primeira vez; recarregar; sair e entrar; chave trocada no `.env`; API desligada | `[~]` 11 verificações automáticas; falta o caso "API desligada" |
Segurança: a chave fica em texto simples no `localStorage` (já é o desenho atual, com a nota de "somente neste navegador"). Não registrar o valor em logs nem em documentos; este plano cita apenas o nome da variável.

### 10.2 C2 — "Adicionar fatura PDF" só funciona depois de salvar o nome do provedor e reabrir a tela

**Relato:** na localidade, o botão de fatura PDF do provedor só libera depois de preencher o nome do provedor, salvar, fechar e abrir de novo.

**Causa confirmada no código** (`agencias.html`, `provRowActions`, ~linha 6263):

- O clique usa o objeto `item` capturado quando a linha foi desenhada. O nome digitado agora só existe no campo da tela (`data-f="nome"`), não em `item`. Por isso `if(!item.nome)` mostra "Informe e salve o nome do provedor antes de anexar a fatura", mesmo com o nome preenchido. Só depois de salvar e reabrir é que `item.nome` vem do cadastro.
- O botão "Marcar como pago" da mesma linha tem a mesma dependência do estado antigo (`if(item.diaVencimento)` decide se o botão existe).
- Para local **novo**, `entityId` está vazio até salvar (`dataset.entityId`), e o código bloqueia com "Salve o cadastro do local antes de anexar a fatura".
- O modal só aceita salvar com o provedor esperado preenchido ("Informe o provedor esperado para comparar a origem da fatura") e grava direto em `POST /api/faturas`, que precisa do `entidadeId`.
- Ao concluir, `updateProviderInvoice` preenche `valor`, `dataVencimento`, `diaVencimento` e `faturaAtualId`, mas **não preenche o nome do provedor**. Ela também localiza a linha por `item.id === providerId`; uma linha nova ainda sem `id` pode não ser encontrada ou casar com outra linha sem `id` (a verificar).

**Comportamento correto (definido pelo usuário):**

```text
Adicionar fatura PDF ─► abre o modal (sem exigir nome salvo) ─► selecionar PDF ─► extrair
   ─► validar os campos ─► "Associar aqui" ─► o modal fecha e preenche a linha do provedor:
        nome do provedor · valor · dia do vencimento (e data de vencimento)
```

Ou seja, a fatura PDF passa a **preencher os mesmos campos que o fluxo do Gmail** (extração unificada e associação), em vez de exigir que o provedor já exista.

Desenho:

- **Lê o estado atual da tela**, não o `item` antigo: usar `readRows` (já usado em "Marcar como pago") ao clicar.
- **Sem nome:** o modal abre assim mesmo. O nome do provedor vem do emissor extraído (revisado pelo usuário) e é gravado na linha; se o nome já estava digitado, o emissor extraído é comparado com ele e a divergência é avisada.
- **Local ainda não salvo:** o modal funciona do mesmo jeito. O PDF e a extração ficam **pendentes na memória**, ligados à linha do provedor, e são enviados a `POST /api/faturas` quando o local for salvo (o mesmo gancho de sincronização que as notas usam após salvar). Se o usuário cancelar o cadastro, nada é gravado. Alternativa descartada: criar o local automaticamente ao anexar, porque exigiria nome e cidade e criaria cadastros incompletos.
- **Campos obrigatórios:** valor, vencimento e nome, com entrada manual se o OCR não achar (mesma regra de P3). Número/chave seguem `999999999` (P1).
- **Regra única compartilhada com o Gmail:** a função "aplicar fatura ao provedor do local" (P2-04) passa a ser a mesma para o botão "Associar" de Notas recebidas e para esta associação no modal, atualizando `nome`, `valor`, `dataVencimento`, `diaVencimento` e `faturaAtualId`. Se o provedor não existe no local, é criado.
- **Aprendizado:** a associação grava o registro de feedback (P5-03) com o extraído e o corrigido.

| ID | Tarefa | Critério de aceite | Status |
|---|---|---|---|
| C2-01 | Ler a linha atual da tela (`readRows`) ao clicar em 📄 e em 💰, em vez de `item` | O botão funciona com o nome recém-digitado, sem salvar nem reabrir | `[x]` |
| C2-02 | Remover as travas "Informe e salve o nome" e "Salve o cadastro do local" | O modal abre com o provedor sem nome e com local novo | `[x]` |
| C2-03 | Fluxo do modal: selecionar → extrair → validar → **Associar aqui** (substitui "Salvar" no contexto do provedor) | Ao associar, o modal fecha e a linha mostra nome, valor, dia e data de vencimento | `[x]` |
| C2-04 | Preencher também o **nome** do provedor na associação (`updateProviderInvoice`) e localizar a linha por identificador estável (criar `id` na linha nova) | Nome vem do emissor revisado; não há troca de linha quando existem várias sem `id` | `[~]` nome preenchido pelo emissor; as linhas já recebiam `id` ao desenhar, o risco previsto não existia |
| C2-05 | Fatura pendente para local não salvo: guardar PDF e extração na memória, ligar à linha e enviar quando o local for salvo (`syncRecord`) | Salvar o local envia a fatura e confirma; cancelar descarta; falha de envio avisa e mantém o pendente | `[x]` |
| C2-06 | Aceitar o provedor esperado em branco | "Informe o provedor esperado" deixa de bloquear; o emissor extraído vira o nome (com confirmação) | `[x]` |
| C2-07 | Usar a extração unificada (P4) e as regras de P1 e P3 neste modal | Mesmos campos e avisos da associação do Gmail | `[ ]` |
| C2-08 | Aplicar a mesma função de P2-04 no backend para o fluxo Gmail e no modal | Um único caminho atualiza o provedor do local | `[x]` regra única no backend (`_atualizar_provedor_do_local`) em todos os fluxos; o navegador busca o resultado na API |
| C2-09 | Testes | Provedor sem nome; local novo; várias linhas sem `id`; cancelar; falha de envio; fatura anterior preservada no histórico; alerta de vencimento gerado após a associação | `[~]` 16 verificações automáticas; faltam cancelar o local, falha de envio, várias linhas e alerta |
Decisões abertas desta seção: D15 (onde guardar a fatura enquanto o local não é salvo) e D16 (se o nome digitado diferir do emissor extraído, qual vence).
## 11. Métricas de acompanhamento e ordem de execução

### 11.1 Métricas

| Indicador | Base (12/11/2026) | Atual | Meta |
|---|---|---|---|
| Notas recebidas sem número / chave | 11/34 / 30/34 | — | 0 sem padrão aplicado |
| Sem valor / vencimento / nome | 14 / 9 / 7 de 34 | — | ≤ 10% / ≤ 10% / ≤ 5% das que são cobrança |
| Sem emissão (antes do fallback) | 27/34 | — | 0 sem origem registrada |
| Associáveis sem edição manual | a medir | — | ≥ 70% das cobranças |
| Falsos duplicados por padrão | n/a | — | 0 |
| Acurácia por campo (P5-04) | a medir | — | definir após a linha de base |
| Taxa de descarte | a medir | — | acompanhar |
| Casos de teste entre Python e JS | 0 | — | ≥ 30 |

### 11.2 Ordem sugerida

1. **P0:** P0-01 ambiente Python · P0-02 backup do `sigp.db`, `notas_recebidas/` e `faturas/`.
1b. **Correções de interface, independentes e rápidas:** C1-01 (diagnóstico) e C1-02/C1-03; depois C2-01 e C2-02 (destravar o botão). O restante de C1 e C2 segue a integração (C2-03 a C2-09 dependem de P4, P1, P3 e P2-04).`n2. **Rede de segurança:** P4-01 (testes de caracterização) e P1-04 (neutralizar o padrão) **antes** de qualquer gravação de padrão.
3. **Fundação:** P1-01, P3-01 (parte sem D6), P2-03.
4. **Descartar e coleta (rápido e independente):** P5-01 a P5-04. Dá a linha de base real de acurácia.
5. **Integração:** P4-02 a P4-09, seguindo P1-02, P1-03, P1-09, P1-05, P3-03 e P3-04.
6. **Associação:** P2-01, P2-02, P2-04, P2-05, P2-06, P2-07, P3-02, P3-06.
7. **Retroativo e reavaliação:** P1-08, P2-09.
8. **Aprendizado:** P5-05 e P5-06; depois P5-07 e P5-08 conforme as métricas.
9. **Modais das localidades:** P1-10, P3-09, P3-10. A extração de PDF nos modais (F-01) fica para depois.
10. **Análise de conciliação com LLM (P6):** P6-02 a P6-10; pede D13 e D14. Dependência de capacidade: o Ollama é compartilhado com o WF-08, então testar o desempenho antes de ativar os dois juntos.
11. **Alertas:** P3-07 e validação do fluxo de vencimentos (próximo marco).

| ID | Preparação | Status |
|---|---|---|
| P0-01 | Consertar/recriar o `.venv-1` e confirmar `python -m unittest discover -s tests` | `[x]` `.venv-1` recriado; linha de base 59/60 (ver seção 3.2) |
| P0-02 | Backup de `backend/data/sigp.db`, `backend/data/notas_recebidas/` e `backend/data/faturas/` | `[x]` backup em `..\SIGp_n8n_backups\2026-11-12_1704` |
## 12. Decisões pendentes

| ID | Pergunta | Recomendação | Resposta |
|---|---|---|---|
| D1b | Valor padrão para chave e número. | `999999999`, constante única. | **Confirmado em 12/11/2026** |
| D11 | NFS-e e nota paga em PDF nos modais. | Ajuste futuro, pela própria LLM (F-01). | **Decidido em 12/11/2026** |
| D12 | Regra das três evidências e conciliação. | Manter como está; análise de conciliação com LLM no n8n (seção 8.4). | **Decidido em 12/11/2026** |
| D13 | Autoridade da conciliação: a LLM apenas **analisa e sinaliza divergência** (a regra do backend decide o status), ou a LLM pode alterar o status? | A regra decide; a LLM sinaliza e explica. Mudar status por LLM tiraria a rastreabilidade e o controle sobre pagamentos, e o modelo de 3B erra campos (ex.: valor lido errado no primeiro lote do WF-08). | — |
| D14 | Quais eventos recebem análise completa por LLM? | MATCH e DIVERGENCIA completas; AGUARDANDO_FATURA/PAGO_PARCIAL/PENDENTE com texto determinístico, para poupar a CPU compartilhada com o WF-08. | — |
| D15 | Fatura PDF anexada a um local ainda não salvo: guardar na memória do navegador e enviar ao salvar (recomendado), ou salvar o local automaticamente ao anexar? | Memória + envio ao salvar (C2-05). Criar o local sozinho exigiria nome e cidade e geraria cadastros incompletos. | — |
| D16 | Se o nome digitado do provedor for diferente do emissor extraído da fatura, qual vence? | Manter o digitado e avisar a divergência; só preencher o nome quando estiver vazio (C2-04). | — |
| D17 | Onde pedir a chave da API (C1): depois do login de usuário, em tela própria, ou só em Configurações? | Depois do login e só quando a API exigir e a chave faltar ou falhar (C1-03/04). | — |
| D2 | Número real novo substitui o padrão? | Sim (P1-03). | Implícito em D1 |
| D5 | Quais documentos são "cobrança" e exigem os três campos? | Tratar depois (usuário). | Adiado |
| D6 | Faixas de plausibilidade de valor e vencimento. | Tratar depois (usuário). | Adiado |
| D7 | A LLM continua sendo chamada pelo n8n e o backend só consolida? | Sim (seção 4.5): evita timeout do API e mantém a chamada visível no editor. | — |
| D8 | Motivos de descarte: a lista da seção 9.3 serve? | Sim, ajustável. | — |
| D9 | O descarte deve etiquetar o e-mail no Gmail (`SIGp/Descartado`)? | Opcional; pode ficar para depois. | — |
| D10 | Gatilho para ajuste fino da LLM (volume e métrica mínimos). | Definir após a linha de base de P5-04. | — |

## 13. Registro de alterações

| Data | Alteração | Autor |
|---|---|---|
| 12/11/2026 | v1: plano criado a partir da análise dos fluxos de extração, associação e campos prioritários. | Kiro |
| 12/11/2026 | v2: aplicadas as decisões do usuário (padrão só para chave e número, vazio ou incorreto; valor, vencimento e nome obrigatórios; unificar extratores; busca ampliada da data de emissão com fallback para recebimento). Incluídos o inventário dos extratores (seção 4), o plano de integração (seção 5) e o plano de aprendizado da LLM com botão Descartar (seção 9). D5 e D6 adiados. | Kiro |
| 12/11/2026 | v3: valor padrão `999999999` confirmado. Descrito o fluxo real das localidades e comparado com a descrição do usuário (seção 4.0): NFS-e e nota paga são lidas no navegador (não pelo n8n), a conciliação é do backend, e o WF-05 gera análise também com menos de três evidências. Incluídos P1-10, P3-09, P3-10, P4-10 e a seção 8.4 (P6). Novas decisões D11 e D12. | Kiro |
| 12/11/2026 | v4: NFS-e e nota paga em PDF por LLM viram ajuste futuro (F-01). Conciliação passa a ter análise por LLM no n8n (P6 reescrito). **Correção da v3:** o WF-05 não usa LLM na análise (o `prompt` é montado e não é enviado); só o parecer acadêmico usa modelo. Regra das três evidências mantida como está. Novas decisões D13 e D14 pendentes. | Kiro |
| 12/11/2026 | v5: adicionada a seção 10 com as correções C1 (chave da API pedida a todo login: bloco sempre exibido; não verificada a causa de persistência) e C2 (botão de fatura PDF depende do estado antigo da linha; confirmado). Definido o fluxo correto da fatura PDF no provedor. Seções 10 a 13 renumeradas para 11 a 14. Novas decisões D15, D16, D17. | Kiro |
| 12/11/2026 | v6: execução iniciada. P0 concluído (venv recriado, backup, ambiente de teste e testes de navegador). **C1 corrigido** (bloco da chave oculto por padrão; 11/11 verificações no navegador). **C2 corrigido** (fatura PDF do provedor sem exigir nome nem local salvos; associação preenche nome, valor, dia e data de vencimento; fatura pendente enviada ao salvar o local; 16/16 verificações no navegador). Registrada a falha de teste que já existia (migração legada de notas recebidas). | Kiro |
| 12/11/2026 | v7: entregues o valor padrão `999999999` para chave/número (com neutralização nas comparações), a busca ampliada da data de emissão com a data de recebimento como último recurso, a associação sem as travas de emissão e chave/número, e o botão Descartar/Restaurar com a tabela `extracao_feedback` (associações e descartes viram exemplos rotulados). Corrigida a falha de teste antiga (migração legada sem `nota_lancada_id`): 68/68. API real reconstruída; dados íntegros. Encontrado: 7 de 34 notas com remetente "[object Object]" vindo do WF-08 (o backend passou a limpar; a causa no workflow precisa de uma execução real do Gmail para confirmar). | Kiro |
| 12/11/2026 | v8: **P2-04 entregue**: associar uma nota recebida atualiza (ou cria) o provedor do local com nome, valor, data e dia de vencimento e fatura atual; correspondência por nome normalizado, sem alterar quando ambíguo e sem regredir para uma fatura mais antiga. Corrigidos dois problemas encontrados no caminho: (1) **alertas de vencimento** do backend ignoravam a data da fatura atual e usavam só o dia do mês (acusavam "vencido" no ciclo anterior); a interface tinha a mesma falha fora da janela de 5 dias; ambos seguem agora a mesma regra; (2) as telas de Agências/Rodoviárias/Garagens guardavam o cadastro em memória e, ao salvar um local depois de uma associação, desfaziam a atualização; agora recarregam ao entrar na aba e quando outra aba altera o local. 76 testes Python; API real reconstruída. Pendente: preencher os provedores das 3 associações reais feitas antes desta versão (retroativo). | Kiro |
| 12/11/2026 | v9: **regra única em todos os fluxos** (seção 7.3): Gmail, fatura PDF (modal e aba Faturas), NFS-e/nota lançada (inclusive WF-01) e rota antiga de fatura preenchem o provedor do local no backend; o navegador busca o resultado. Reconhecimento da mesma empresa pela primeira palavra do nome. **Retroativo executado** nos dados reais (backup `antes-retroativo-provedores-2026-11-12_195038.db`): Garagem Rota Aracaju recebeu o provedor OPIX INTERNET (R$ 119,90, vencimento 10/11); a Rodoviária Expresso Brasileiro e as agências "teste" e "Ilheus" estão **inativas** e não foram alteradas. **Incidente corrigido:** um teste de tela gravou 1 nota fictícia na API real porque a interface envia notas pelo n8n e o WF-01 grava sempre na API real; a nota e 2 registros de log foram removidos (backup `antes-limpeza-2026-11-12_194750.db`) e os testes agora forçam a entrada direto na API de teste e bloqueiam a API real e os webhooks de gravação do n8n. 79 testes Python; telas: chave 11/11, fatura PDF 16/16, Notas recebidas 6/6, associação 6/6, NFS-e no local 4/4. | Kiro |
| 12/11/2026 | v10: **regra de recorrência** (seção 7.4): mesmo local + mesma empresa + mesmo mês = mesma cobrança, atualizada e substituída; o mês seguinte gera nota nova. A comparação deixou de pedir confirmação por número padrão e por variação do nome da mesma empresa. Ferramenta `unir_notas` para as duplicadas antigas (testada na base de teste). Alertas ignoram locais excluídos (inativos). Cadastro do local abre com linha vazia de provedor e de nota (seção 7.5). Corrigida condição de corrida: a gravação do cadastro pela tela podia apagar a fatura atual do provedor preenchida pelo backend (`preservar_fatura_atual`). Nota lançada/paga sem chave e número recebe o valor padrão, desde que o provedor (ou a nota vinculada) esteja informado. 81 testes Python. | Kiro |
| 12/11/2026 | v11: notas OPIX unidas nos dados reais com o nº 302500 (correção auditada; backup `antes-unir-opix-2026-11-12_203319.db`); alertas sem duplicidade. **Sugestão de local por histórico** (provedor já associado, e-mail do remetente). **Extração unificada (P4)**: endpoint `/api/extracao/texto`; WF-03 (aba Faturas e modal do provedor) passou a usar o extrator do backend, que ficou igual ou melhor em todos os campos sobre 29 textos reais (seção 5.3). 84 testes Python; modal da fatura 16/16 pelo n8n real. | Kiro |
| 12/11/2026 | v12: **recorrência na gravação direta** (NFS-e no local, WF-01, Praxio/Globus): nota sem número/chave real no mesmo mês, local e empresa atualiza e substitui a nota existente, sem 409, mantendo o número real; mês seguinte gera nota nova; número real diferente continua sendo outra cobrança. O editor de nota do local deixou de exigir chave/número (vale o padrão, com o provedor obrigatório). A tela une linhas que viram a mesma nota e avisa "Nota do mesmo mês já existia…". 88 testes Python; tela da recorrência 6/6 e regressões (NFS-e 4/4, associação 6/6, Notas recebidas 6/6, chave 11/11). API real publicada; nenhuma duplicada nos dados reais. | Kiro |
| 12/11/2026 | v13: **arquitetura alvo** definida pelo usuário (seção 0): n8n orquestra tudo; SIGp (SQLite, futuro executável Windows) recebe decisões, informa as localidades e é a entrada manual enquanto não há ERP/NSDocs; integração só por API/webhook; LLM local no Docker chamada pelo n8n. Plano de adequação em fases A–G. Verificado: decisão do gerente (WF-07) grava no painel legado; WF-05 não chama a LLM; Ollama fora do ar; LoRA existente é sintético e acadêmico. | Kiro |
| 12/11/2026 | v14: **A-01** contrato de API v3 (`docs/contrato-documentos.md`). **D-01** Ollama no Compose principal (`sigp_ollama`, versão fixada, sem porta no Windows), modelos copiados do volume acadêmico sem novo download; n8n recriado com `SIGP_OLLAMA_URL/MODEL` (9 workflows ativos preservados); removida do n8n a variável `ANTHROPIC_API_KEY` (vazia e sem uso) para garantir LLM só local; Compose acadêmico deixou de usar o apelido `ollama` na rede do n8n; `Iniciar SIGp.ps1` confere OCR e LLM. Teste: o n8n chama o Ollama (54 s na 1ª, 3,8 s depois); classificou "FATURA… TOTAL A PAGAR" como `nota_fiscal` (melhorar em D-03/D-04). | Kiro |
| 12/11/2026 | v15: **Fase C** (D13 confirmada; D14 pela recomendação: LLM em MATCH e DIVERGENCIA). WF-05 gerado por `n8n/wf05/build_wf05.py` (prompts, schemas e código versionados; anterior em `.legado.json`): toda análise vai ao SIG; ciclo fechado e divergência pela LLM local, com **fatos calculados no fluxo** (sem eles a LLM errava "antes/depois do vencimento" e inventava problemas). Aba SIG "Para decidir" com validar/corrigir/devolver e auditoria (`decisoes_gerente`); a decisão vai ao n8n pela fila de eventos; validadas e corrigidas viram resumo executivo na SIE pela LLM; devolvidas não. Corrigido o atributo `hidden` anulado pelo CSS. 93 testes Python; SIG 9/9 na tela; harness do WF-05 com o Ollama real; regressões ok; WF-05 publicado (9 workflows ativos). Verificada uma associação real do usuário: provedor ITS criado sozinho na Agência Itacaré. | Kiro |
| 12/11/2026 | v16: **C-04** concluída (`validacao_por_nota` em `/api/sie/resumo`; campos `aguardandoGerente`, `valorAguardandoGerente`, `devolvidosPeloGerente`; card na SIE). **C-05** parcial: tipo de alerta `pagamento` (`PAGO`, `PAGO_COM_ATRASO`), vencimento da fatura atual tem prioridade, deduplicação nota × provedor, rótulo sem tipo repetido, valores em R$; WF-06 publicado. 95 testes Python; e2e `sie_ui.js` 3/3 e `sig_decisoes_ui.js` 9/9. API real com 2 alertas. Notificações aguardam credenciais. |
| 12/11/2026 | v17: **Fase B**. B-01 `n8n/lib/extrator.js`, porte fiel do extrator do SIGp (\b Unicode emulado, `splitlines`, `strip` e `float` do Python), paridade 232/232. Correções nos dois lados: "Nº documento: X" no meio da linha (ITS nº 2847941, antes 999999999 com "R$ 174,00" rejeitado), "Nº documento    Vencimento" em colunas e chave na linha de baixo (NFS-e nacional de 50 dígitos; o WF-08 antigo cortava em 44). Nos textos reais: só ganhos (2 números e 7 chaves a mais). B-02 WF-03 publicado com a lib e contingência no SIGp. B-03 WF-08 gerado sobre a lib (emissor achado em +22 PDFs), aguardando importação. 97 testes Python. |
| 12/11/2026 | v17b: duas regras novas no extrator (n8n e SIGp): "NOTA FISCAL Nº X" no meio da linha (DANFE-COM) e chave de 44 dígitos em grupos de 4 em qualquer coluna, aceita só com dígito verificador módulo 11 conferido. Paridade 236/236, 11 testes node, 97 Python. WF-03 republicado; WKVE passa a sair com nº 16210 e chave. Nota lançada real `gmail-5b9ca3…` (WKVE, 999999999) com correção simulada, gravada em 13/11/2026 (PATCH auditado, backup `antes-wkve-16210-*.db`). A nota da ITS já tinha o nº 2847941. |
| 13/11/2026 | v18: **Notas recebidas "Em análise"**: "Manter na caixa, sem associar" não gravava nada (só limpava a tela). Agora "Deixar em análise" grava o status `EM_ANALISE` (observação, operador, data; `PATCH /api/notas-recebidas/<id>/analise` e `/liberar`), filtro próprio, o reprocessamento do Gmail não sobrescreve, e dá para associar, descartar ou voltar para a fila. Dentro da comparação o botão virou "Não associar agora". Corrigida corrida na lista (resposta antiga de outro filtro sobrescrevia a atual). 100 testes Python; e2e `nota_em_analise_ui.js` 7/7, `notas_recebidas_ui.js` 6/6. **Achado**: o WF-08 descarta anexos XML (só PDF), então o XML da NF-e que chega junto da fatura se perde; proposta de tratamento em análise com o usuário. |
| 13/11/2026 | v19: **XML da nota fiscal junto com a fatura PDF** (os dois são guardados; o XML tem prioridade nos campos fiscais, decisão do usuário). `n8n/lib/xml_fiscal.js` lê NFS-e ABRASF, NFS-e nacional, NF-e e NFCom sem DOM e recusa DOCTYPE/ENTITY; 66/66 campos iguais ao gabarito dos 10 XML de `docs/XML para testes`. WF-08: "Preparar anexos" pega PDF e XML da mesma mensagem (liga pelo número da nota; XML que sobra entra sozinho, em Revisão), "Consolidar" aplica a prioridade do XML e registra `divergenciasXml`; documento com XML nunca é ignorado. SIGp: `POST /api/notas-recebidas` aceita o XML (`xml` como arquivo ou `xmlConteudo`), `GET /api/notas-recebidas/<id>/xml` e `GET /api/notas/lancadas/<id>/xml`; na associação o XML vai para a nota lançada do local (com os itens de serviço) e a fatura PDF para o provedor; só XML não associa (a fatura PDF é obrigatória); releitura do PDF não substitui os campos do XML. Tela: bloco do XML no cartão, divergência PDF × XML, "Baixar XML", link "XML da nota fiscal" nas notas do local. **Descrição do serviço** corrigida nos dois extratores: não atravessa mais a quebra de linha (pegava a linha seguinte) e ignora encargos do boleto ("Mora / Multa", "(=) Valor cobrado"); usa a linha de baixo do rótulo e "Referente ao...". 105 testes Python, 17 node, paridade 244/244; e2e `nota_xml_ui.js` 10/10, `nota_em_analise_ui.js` 7/7. WF-03 e WF-08 republicados (WF-08 continua ativo). |
| 14/11/2026 | v19b: **"Enviar para análise" dava "Documento duplicado"** (teste real do usuário: e-mail com PDF + XML, Rodoviária de Jequié). Causa: a análise regrava a nota lançada com a cópia do navegador, que tinha a chave de 41 dígitos do XML (no banco, 999999999 pela regra 44/50) e a emissão com horário; com o mesmo id, a API comparava a identidade ao pé da letra. Correção: mesmo id = atualização do mesmo registro; o padrão 999999999 não conta como identidade; vazio/padrão não apaga o gravado e identificador inválido não substitui o padrão; datas ISO com horário viram só a data. Outro número real ou outro emitente com o mesmo id continuam recusados. A cópia da nota no navegador passa a usar o que a API gravou. Serviço único sem valor (NFS-e nacional) recebe o total da nota (lib do XML e SIGp). 106 testes Python; e2e `nota_xml_ui.js` 14/14 (inclui a cópia antiga e o envio à análise). API e WF-08 republicados. |
| 14/11/2026 | v19c: **"Marcar como pago" + salvar o local dava 409 via WF-01** (corpo lido na execução 4626 do n8n). Causa: a cópia antiga no navegador tinha série vazia; no banco, "1" do XML. Correções: série, emitente e emissão vazios não apagam nem contradizem o gravado (mesmo id); na conciliação, série vazia de um lado é "não informada" (como a emissão), série diferente continua divergindo. Tela: editar uma nota mantém o id e o link do XML (antes gerava id novo); o primeiro pagamento já vem com número, série, valor e serviços da nota lançada (chave só se válida 44/50, senão 999999999); a classificação do serviço vale para a nota e o pagamento; pagamento sem serviços leva os da nota lançada. e2e `nota_xml_ui.js` 17/17 (fecha em MATCH com nota + pagamento + fatura PDF); regressões recorrência, NFS-e e C2 ok; 106 testes Python. API republicada. |
| 14/11/2026 | v19d: **Ciclo de Jequié ficou PENDENTE após marcar como pago.** O pagamento foi gravado sem número, com a chave de 41 dígitos e o nome fantasia ("JET FIBRA"): o leitor de XML antigo do navegador não conhece a NFS-e nacional (`nNFSe`) e preferia o nome fantasia. Sem número e com outro emitente, a regra não liga o pagamento à nota. A "decisão humana" foi registrada no painel legado (`buscador_nfse.py`, porta 5000), que não altera a conciliação nem o SIGp. Correções: o formulário do local importa XML com a mesma lib do n8n (`frontend/modules/xml-fiscal.js`, cópia conferida por teste); mesmo id só é outro documento se chave/número reais conflitam ou o local muda (corrigir emitente, série ou emissão do mesmo registro é permitido); pagamentos também não perdem campos gravados por vazio. Simulado no banco real: o pagamento corrigido fecha em MATCH. 107 testes Python; e2e `nota_xml_ui` 17/17, `sig_decisoes_ui` 9/9. API republicada. |
| 14/11/2026 | v19e: **E-mail da Minas Online sem a etiqueta SIGp/Importado.** A nota estava no SIGp (Revisão) e o WF-08 aplicou a etiqueta (execução 4485, `Label_3`), mas o utilitário "Liberar mensagens para reprocessar" (execução manual 4550) tirou SIGp/Importado de todas as mensagens e a busca histórica só reetiquetou parte. Novo utilitário `WF-08 utilitário - Reaplicar SIGp/Importado` (`n8n/wf08/build_reetiquetar.py`): etiqueta toda mensagem que já está no SIGp, sem reprocessar; manual e diário às 06:00. Primeira execução: 56 mensagens, 0 falhas; Minas Online com a etiqueta de volta. |
| 14/11/2026 | v19f: **"Liberar" substituído por "Reprocessar mensagens (sem tirar etiquetas)"** (pedido do usuário: o n8n trata o reprocessamento e não há trava a remover). O utilitário busca no Gmail as mensagens escolhidas (busca editável, padrão `label:sigp-importado newer_than:3d`, 20) e as entrega ao WF-08 pelo novo gatilho "Reprocessamento (chamado pelo utilitário)" (Execute Workflow). Nenhuma etiqueta é removida; a proteção da API continua (nota associada, descartada ou em análise não tem dados trocados). Teste real: mensagem da Minas Online reprocessada (`origemBusca: reprocessamento`) e etiqueta SIGp/Importado mantida. Geradores: `n8n/wf08/build_reprocessar.py`; versão antiga em `.legado.json`. |
| 14/11/2026 | v20: **Chave lida tem prioridade** (decisão do usuário): o padrão 999999999 só entra quando não há chave; chave fora de 44/50 dígitos fica como veio, com o motivo anotado e sem ir para revisão (SIGp, `n8n/lib/extrator.js` v2, gravação e primeiro pagamento). Número continua com a regra antiga. Testes ajustados (`test_campos`, `test_nota_xml`, e2e `nota_xml_ui` com chave única por execução, `notas_recebidas_ui` com nota própria). 107 Python, paridade mantida, e2e 17/17 e 6/6. API, WF-03 e WF-08 republicados. Criado `docs/registro-mudancas.md` (antes/depois para apresentação) e a fase H com as prioridades do usuário. |
| 14/11/2026 | v21: **Etapa 1 da ordem acordada.** H-07: `versaoRegras` (SIGp `REGRAS_EXTRACAO_VERSAO` = lib `VERSAO_REGRAS` = 2) em toda leitura; `leituraDesatualizada` na API; aviso no cartão; `/extrair` grava a releitura em notas não associadas (`atualizar_extracao_nota_recebida`). H-06: link do painel legado no SIG e na SIE. Também nesta data (entrega acadêmica parte 2): ambiente acadêmico leve, testes de permissão e auditoria da IA, benchmark A/B/C, latência e custo, mascaramento, troca de senhas, prompts v4, casos de teste. 108 Python; e2e notas recebidas 6/6, SIG 9/9, SIE 3/3, XML 17/17. API, WF-03 e WF-08 republicados (backup `antes-etapa1-20261114-135150.db`). |
| 14/11/2026 | v22: **Etapa 2 — triagem pela LLM.** WF-08: Consolidar → Salvar no SIGp (sempre) → etiqueta Ignorado/Importado pela decisão da IA; `triagem` com `execucaoId` ($execution.id). SIGp: status `IGNORADA_IA` (fora de "Todos"; reprocessamento pode tirar da fila), `GET /api/notas-recebidas/triagem`, `POST .../ignorados/confirmar` (lote, vira DESCARTADA "não é cobrança"), `PATCH .../<id>/resgatar`; feedback `ignorado_confirmado`/`ignorado_resgatado`; associar ignorado devolve 409. Tela: resumo da última leitura, atalho e filtro "Ignorados pela IA", cartão com motivo e confiança. 111 Python; e2e `triagem_ia_ui` 5/5. API e WF-08 publicados (backups `antes-triagem-20261114-145922.db`, `n8n/wf08/backup_wf08_antes_triagem_*.json`). |
| 14/11/2026 | v23: **Etapa 3 — H-01 importação CSV** (`frontend/modules/importar-csv.js`): formato do Exportar CSV + Marcadores; listas `|` e partes ` - `; provedor: "venc. dia N", valor "129,90", contato/URL/e-mail, "CONSULTAR" vai para observações, mesmo provedor repetido é unido; responsável sem nome herda o anterior; rede só com IP (texto sem IP vai para observações); correspondência por nome+cidade; mescla sem apagar; Sistemas com bloqueio de senha na observação. Botões nas 4 barras. node 9/9, e2e 4/4. Só frontend (nginx), sem mudança na API. |
| 14/11/2026 | v24: **Etapa 4 — memória de exemplos** (`GET /api/llm/exemplos`, `casos_decididos`, `_exemplo_de`): decisões do operador em documentos parecidos entram no prompt do WF-08 (nó "Buscar exemplos no SIGp", 25 nós; prompt v4.1). Sem valores fiscais; falha na busca não para o fluxo. A/B com qwen2.5:3b: hotel do mesmo remetente passou de `nota_fiscal` para `outro`. 113 Python, e2e 83/83. Publicado; backup do banco e do WF-08 antes. Próxima: etapa 5, métricas de acerto. |
| 14/11/2026 | v25: **Notas recebidas em listas** (`frontend/modules/notas-recebidas.js`, CSS em `agencias.html`): listas por chance de ser internet e por status; e-mails em accordion clássico; partes em disclosure; dados sensíveis fora do cabeçalho; estado aberto preservado. e2e `notas_listas_ui.js` 10/10, regressões 83/83. Teste inverso (Thomson Reuters/Domínio) registrado em `evidence/parte2/teste-inverso-nao-internet.json`: a LLM acerta (`outro` 0,9 a 1,0), mas a regra `DOCUMENTO_FISCAL_REVISAO` impede ignorar; correção proposta aguardando aprovação. |
| 14/11/2026 | v26: **PDFs com senha** (OCR tenta prefixos das raízes de CNPJ do grupo; `SIGP_PDF_SENHA_CNPJS`) e **triagem em três níveis** (alta / baixa / inconclusivo; 3 confirmações do remetente = descarte automático reversível). Respostas do usuário: senha = começo do CNPJ do tomador; 3 confirmações; aviso de pagamento do provedor = marcar como pago automaticamente (situação 1, a fazer). Ordem seguinte: painel da LLM + saúde do banco; situação 1 (vários e-mails da mesma fatura); situação 2 (fatura não recebida); situações 3–5 (identificação do cliente/contrato). |
| 14/11/2026 | v27: **Etapa 5 — Painel da IA** (métricas mensais da LLM, tempo, memória) e **saúde do banco** (verificação, backup verificado com rodízio, manutenção diária pelo n8n às 03:00). Próximo: situação 1 (vários e-mails da mesma fatura: atraso, 2ª via, pagamento informado = marcar como pago). |
| 15/11/2026 | v28: **Situação 1** (evento por e-mail; aviso vinculado à cobrança; pagamento confirmado registra o pagamento; aviso sem anexo entra pelo WF-08), status AVISO, prompt v4.2 (evento; provedor só do documento), memória de exemplos sem semelhança fraca, reprocessamento dos 10 PDFs com senha. Próximo: situação 2 (fatura não recebida). |
| 15/11/2026 | v29: **Situação 2** — alertas FATURA_NAO_RECEBIDA, FATURA_NA_CAIXA e LEITURA_GMAIL_PARADA; periodicidade no cadastro do provedor; WF-06 com os novos alertas no resumo diário. Próximo: situações 3–5 (identificação do cliente/contrato para vários provedores e locais). |
| 15/11/2026 | v30: **Situações 3 a 5** — leitura do código do cliente/contrato/instalação, aprendizado na associação, sugestão de local por código, aviso de provedor em vários locais, avisos com código; histórico preenchido. Pendente com o usuário: limpar o registro de teste de Jequié (JEQUIE FIBRA NET, e-mail de teste). Próximo combinado: robustez E-01..E-03 / permissões H-02 / segurança H-03–H-04. |

## 14. Escopo da análise

Para C1 e C2 li `agencias.html` (tela de autenticação, `initAuth`, `showApp`, `provRowActions`, `updateProviderInvoice`, `readRows`), `api-client.js` e `faturas-provedores.js`, e confirmei que o `.env` define `SIGP_API_KEY` (valor não lido). **Não abri o sistema no navegador**: a causa de C1 (persistência da chave) está como hipótese. Verifiquei no JSON do WF-05 que o `prompt` não alimenta nenhum nó de modelo, e que o webhook responde imediatamente (`onReceived`). Li o código de `agencias.html` (trechos da aba NFS-e), `frontend/modules/notas-locais.js`, `api-client.js`, `analysis-dispatcher.js`, os nós Code do WF-05 e o fluxo de eventos, além de `backend/app.py`, `backend/database.py`, `backend/reconciliation.py`, `backend/alerts.py`, `ocr/app.py`, `n8n/wf08/wf08_lib.js`, `prompt_classificacao.md` e `schema_classificacao.json`, os nós Code do WF-01 e do WF-03, a lista de nós e URLs do WF-08 e dos demais workflows, trechos de `frontend/modules/notas-recebidas.js`, `faturas-provedores.js` e `notas-fiscais.js` e a assinatura das funções do `docs/entrega-academica/ia/app.py`. Consultei o `sigp.db` apenas para leitura. **Não li** `backend/normalizer.py` linha a linha, o corpo dos nós Code do WF-05, WF-06 e WF-09, nem o HTML completo dos modais de localidades (li o código JS que os controla). Não confirmei no navegador o comportamento descrito na seção 4.0; ele vem da leitura do código. Não executei a suíte de testes, não rodei os workflows e não medi acurácia. As estimativas de volume para ajuste fino (seção 9) não foram validadas.










