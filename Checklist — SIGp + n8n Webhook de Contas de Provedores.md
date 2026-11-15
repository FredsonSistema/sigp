# Checklist de implementação — SIGp, NFS-e, backend, n8n e SIE

**Atualizado em:** 09/10/2026 (verificação no computador atual; ver seções 0 e 9)  
**Objetivo:** refletir o estado encontrado no código e separar implementação local, integração configurada e trabalho ainda pendente. Este checklist substitui o plano antigo, que mantinha como não feitos vários módulos já presentes e marcava como concluídas integrações que ainda têm placeholders.

## Como interpretar os estados

- [x] **Implementado no repositório:** há código ou configuração correspondente. Isso, sozinho, não comprova execução em produção.
- [~] **Parcial / depende de configuração:** existe implementação inicial, mas faltam integração, credenciais, validação ou cobertura.
- [ ] **Pendente:** não encontrei implementação suficiente no repositório.

**Limite desta atualização:** a simulação de pagamento até o painel legado `/sie` foi executada no computador anterior. Em 09/10/2026, no computador atual, foram reexecutados os testes automatizados, o fluxo da API e o webhook de PDF; o webhook de notas não pôde ser testado porque o workflow não existe na instância n8n deste computador. A simulação não comprova nem registra um pagamento real.

**Nomes:** SIG = Sistema de Informação **Gerencial** (aba existente). SIE = Sistema de Informação **Executiva** (aba dedicada, ainda não criada). O `/sie` da porta `5000` é o painel legado de conciliação, criado com o nome trocado.

---

## 0. Ambiente do computador atual (09/10/2026)

- [x] `.venv` excluído: apontava para `C:\Users\fredson.santos\...` (computador anterior) e não executava. **Verificado.**
- [x] `.venv-1` adotado como ambiente do projeto (Python 3.14, Flask 3.1.0); `Iniciar SIGp.ps1` já o usa como alternativa. **Verificado:** 12/12 testes.
- [x] Docker Desktop com `sigp_n8n` (n8n 2.42.4), `sigp_sie` e `sigp_fatura_ocr` em execução. **Verificado.**
- [x] Healthcheck do `sigp_sie` com prazo maior (estourava 5 s e marcava `unhealthy`).
- [x] Workflows WF-01, 02, 05 e 06 importados e publicados; WF-99 importado (a instância só tinha o de PDF). **Verificado com teste ponta a ponta.**
- [x] API no Compose (`sigp_api`), chamada pelo n8n como `http://api:5001`. **Verificado.**
- [x] API só em `127.0.0.1`, waitress, sem depurador; CORS restrito; `X-API-Key` opcional. **Verificado** (nenhum processo do Windows escuta na rede na porta 5001).
- [x] Repositório Git próprio em `SIGp_n8n` com `.gitignore` (`git init -b main`; sem commit ainda).

---

## 1. SIGp — contas de provedores e webhooks

### Interface e eventos

- [x] Campo de valor nos provedores de link e comparação de provedores antes/depois por ID ao salvar locais.
- [x] Geração dos eventos `conta_criada`, `conta_atualizada`, `conta_paga` e `conta_excluida`.
- [x] Configuração da URL, token, habilitação/desabilitação e teste de conexão do webhook.
- [x] Campo de token oculto por padrão, com opção de mostrar/ocultar.
- [x] Payload de conta com `versao: 1`, evento, timestamp e dados.
- [x] Envio assíncrono com timeout; falhas HTTP ou de rede geram log e podem ir para a fila.
- [x] Fila local persistida no navegador, reenvio de item, reenvio geral manual e tentativa automática a cada cinco minutos.
- [x] Log local limitado aos 200 eventos mais recentes, com resultado/status.
- [x] A fila, separada do log, permite reenviar ou remover manualmente um evento pendente.
- [x] A interface SIGp permanece utilizável quando o webhook está desabilitado ou o n8n está indisponível.
- [x] Fluxos de criação, atualização e exclusão dos locais chamam a comparação de provedores.

### Validação registrada anteriormente

- [x] A versão anterior deste checklist registrava como executados os cenários de criar, editar, pagar e excluir provedor, deixar o n8n offline e reenviar a fila.
- [ ] Repetir esses cenários no ambiente atual e registrar evidências da execução; eles não foram revalidados nesta atualização.

---

## 2. n8n — workflow de contas de provedores

Arquivo: `n8n_workflow_contas_provedores.json`.

- [x] Workflow exportado com webhook `contas-provedores` e nó de normalização/enriquecimento dos quatro eventos.
- [x] Nós configurados para upsert do estado atual das contas e append de eventos no histórico via Google Sheets.
- [~] O cálculo de atraso existe, mas é simplificado: compara o dia do mês com `diaVencimento`; não é cálculo completo baseado em uma data de vencimento.
- [~] Há nós de criação de HTML e preparação de arquivo para o comprovante.
- [~] Há nós para Gotenberg e notificação por WhatsApp via Evolution API, mas endereço, credenciais, instância e destinatário ainda são valores de exemplo.
- [ ] Configurar IDs de planilha, abas/cabeçalhos e credencial Google Sheets reais.
- [ ] Configurar e executar o envio de notificações com Evolution API; não há nó de envio de e-mail no workflow atual.
- [ ] Configurar e validar o conversor Gotenberg/PDFShift.
- [ ] Ligar o PDF convertido como anexo na mensagem: o workflow ainda contém um nó `noOp`/TODO para envio de mídia.
- [ ] Importar e executar o workflow no n8n ativo e confirmar persistência, notificações e tratamento de falhas. Em 09/10/2026 ele não existe na instância deste computador.
- [ ] Corrigir a conexão para o nó inexistente "TODO: converter em PDF de verdade" (o nó "Preparar HTML" está órfão e o Gotenberg nunca executa) e adicionar `webhookId`.

---

## 3. SIGp — notas fiscais e documentos

### Cadastro e armazenamento no navegador

- [x] Módulo NFSe com armazenamento local `sigp_nfse_v1`, normalização de notas e itens de serviço.
- [x] Seção de lançamento manual e lista de notas dentro da interface de Configurações; **não é uma nova aba principal dedicada**.
- [x] Campos para chave/número/série, provedor, local/cidade, valor, datas, observação e status.
- [x] Criação e atualização de nota no módulo, registro de pagamento e estados `PAGA`/`PAGO_PARCIAL`.
- [x] Importação e interpretação de JSON e XML; extração de campos da NFS-e, itens de serviço e tentativa de extrair vencimento de `xInfComp`.
- [x] Importação do XML de fatura Algar no formato `faturaAlgar`, extraindo número fiscal/série quando informados, emissor, datas e valor; não inventa chave de acesso ausente.
- [x] Aba principal **Faturas** para importar PDFs opcionalmente por agência, rodoviária ou garagem, com vínculo de cada resultado ao cadastro selecionado.
- [x] Nota lançada selecionável como referência opcional; extração e comparações de emissor, valor e vencimento são revisáveis antes de salvar.
- [x] Persistência de múltiplas faturas como registros filhos do local e armazenamento dos PDFs no backend.
- [x] Histórico na aba **Faturas**, filtrado pelo tipo/local selecionado, com resultados da extração, estado de comparação e acesso ao PDF.
- [~] Fatura sem nota de referência é aceita; o sistema compara a origem com o provedor esperado, mas valor e vencimento ficam sem referência.
- [x] Serviço OCR local construído e iniciado no Docker; saúde HTTP confirmada e idiomas Tesseract português/inglês instalados.
- [x] Teste do endpoint OCR com `algar.pdf`: OCR local retornou texto e o parser reconheceu emissor, número, vencimento e valor; CNPJ e emissão não foram reconhecidos e exigem conferência manual.
- [x] O workflow publicado na instância n8n encaminha o PDF ao serviço OCR local do Compose: extração via Poppler e fallback Tesseract em português nas primeiras 10 páginas.
- [ ] Validar os campos com outros formatos de faturas reais; OCR pode errar e a revisão humana permanece obrigatória.
- [x] Interface de notas vinculadas aos cadastros de agência, rodoviária e garagem.
- [x] Classificação por serviço como `PENDENTE`, `CONTRATADO` ou `DIVERGENTE`, com gravação das notas e da conciliação ao salvar o cadastro.
- [x] Consulta do nome do município pelo código via serviço do IBGE, quando necessário.

### Integração do SIGp com o backend

- [x] A tela lista notas lançadas do backend, mostra o estado de conexão da API e usa o armazenamento local como cache de leitura quando a API não responde.
- [x] Novos lançamentos da seção NFSe são gravados pela API antes de serem considerados salvos na interface.
- [x] A interface de notas locais salva notas lançadas e pagas na API e pede a conciliação quando existem os dois registros.
- [x] A tela de conciliação exige chave ou número, valor pago positivo e cidade antes de consultar o backend.
- [x] A tela exibe o resultado e as comparações de chave, valor e cidade; `MATCH` é a condição para tentar notificar o n8n.
- [~] Existe uma fila local de eventos NFSe (`sigp_nfse_eventos_v1`), mas a gravação nessa fila não demonstra, por si só, reenvio automático equivalente à fila de contas.
- [~] O módulo define eventos e payloads de documento versão 2; a emissão de `nfse_lancada`, `nfse_atualizada` e `nfse_cancelada` não está conectada de forma consistente a todas as ações da interface.
- [~] O webhook de NFS-e é configurado separadamente do webhook de contas; os eventos observados no fluxo de pagamento usam `nota_paga`.
- [ ] Criar uma aba principal dedicada com busca, filtros por status e gestão completa de notas, se esse continuar sendo o requisito.
- [ ] Completar o ciclo de eventos de criação, edição, cancelamento e pagamento, incluindo envio/reenvio e registro de falhas para NFS-e.
- [ ] Validar sincronização e reconciliação quando a API cai durante uma operação; o cache local é apresentado para leitura e não substitui gravação no backend.

### Contrato de documentos

- [x] Contrato de documento versão 2 com documento, itens por local, resumo, timestamp e status, documentado em `docs/contrato-documentos.md`.
- [x] Funções para normalizar local/itens, construir payload e validar campos básicos (`chave` ou `número`, provedor, local/cidade e valor positivo).
- [~] O contrato está disponível como módulo compartilhado, mas nem todas as rotas e workflows consomem o mesmo formato como contrato único.
- [ ] Adotar e validar o contrato versão 2 de ponta a ponta entre SIGp, backend, workflow e dashboard.

---

## 4. Backend Flask — persistência e conciliação operacional

Arquivos: `backend/app.py`, `backend/database.py` e `backend/normalizer.py`. API local padrão na porta `5001`.

### API e banco

- [x] Inicialização SQLite e criação/evolução das tabelas `notas_lancadas`, `notas_pagas`, `conciliacoes` e `api_events`.
- [x] `GET /api/health`.
- [x] `GET /api/notas/lancadas`, `POST /api/notas/lancadas`.
- [x] `GET /api/notas/pagas`, `POST /api/notas/pagas`.
- [x] `GET /api/notas/conciliacoes`, `POST /api/notas/conciliar`.
- [x] `POST /api/sie/webhook` para registrar evento recebido.
- [x] `POST /api/notas/lancadas/<nota_id>/fatura`, com validação do PDF, limite de 15 MiB, emissor confirmado, comparação obrigatória do nome com o provedor cadastrado e campos obrigatórios revisados.
- [x] `GET /api/notas/lancadas/<nota_id>/fatura` e rota de download; metadados persistidos na tabela `faturas_provedores`.
- [x] A listagem de notas lançadas informa se há fatura anexada; vencimento da fatura só preenche o vencimento ainda vazio da nota.
- [x] Upsert de notas por ID quando a identidade fiscal não muda, serialização JSON dos itens de serviço e registro dos eventos recebidos.
- [x] Rejeitar reutilização de ID para outra identidade fiscal e duplicação de chave com HTTP 409; pagamentos idênticos no mesmo dia/valor são bloqueados, pagamentos parciais distintos são preservados.
- [x] Criar uma conciliação para cada par nota lançada + nota paga, evitando substituir conciliações de outros pagamentos da mesma nota.
- [x] Endpoint SIG com período limitado a 36 meses e exclusão/sinalização de chaves fiscais ambíguas nos indicadores.
- [x] Normalização de entrada JSON e XML no backend, incluindo extração dos campos e serviços da NFS-e.
- [x] Conexão da interface SIGp com a API de notas da porta `5001`.
- [x] Criada suíte `unittest` focada em regras de conciliação, parcial, persistência/idempotência, chaves duplicadas, conciliações por par e resumo do SIG; 12 testes passaram.
- [ ] Expandir testes para normalização XML/JSON, upload de PDF, outros cenários-limite e integração de workflows.
- [ ] Adicionar paginação/limites às listagens.
- [ ] Substituir SQLite caso requisitos de produção, concorrência ou operação multiusuário o exijam; PostgreSQL é uma direção documentada, não uma implementação atual.

### Conciliação atual e validação pendente

- [x] A regra compara identidade fiscal, tipo/ID do local, valor total, valor pago acumulado e serviços, e persiste resultado/status.
- [x] Classificações dos serviços lançados e pagos precisam estar como `CONTRATADO`; classificação pendente não libera `MATCH`, divergência ou conteúdo diferente resulta em `DIVERGENCIA`.
- [x] Pagamento incompleto resulta em `PAGO_PARCIAL` e não libera evento de pagamento `MATCH`; registros distintos de pagamento da mesma nota são acumulados.
- [x] Identidades insuficientes permanecem pendentes; comparações usam chave, ou número+série+provedor e data de emissão quando a chave não existe.
- [x] Conciliação repetida do mesmo par atualiza seu próprio registro; pagamentos associados à mesma nota mantêm conciliações distintas.
- [~] `MATCH` indica correspondência dos dados cadastrados, não confirmação bancária; a simulação existente não é pagamento real.
- [ ] Validar formatos e limites de entrada, em especial valores inválidos e corpos JSON que não sejam objetos.
- [ ] Definir autenticação e restringir CORS antes de expor a API; hoje há CORS `*` e o servidor de desenvolvimento usa `debug=True`/`0.0.0.0` (o log de 07/10/2026 mostra a API publicada no IP da rede local com o PIN do depurador).
- [ ] Corrigir o desempate da "conciliação mais recente" no SIG (`dashboard.py:114-119`): com `updated_at` em segundos, `PAGO_PARCIAL` e `MATCH` gravados no mesmo segundo fazem o SIG mostrar `PAGO_PARCIAL`. **Reproduzido em 09/10/2026.**
- [ ] "Vencidas" no SIG usa a data final do filtro, não a data de hoje.
- [ ] Padronizar `PAGO_PARCIAL` × `PARCIAL` × `PAGAMENTO_PARCIAL`; calcular `PAGO_COM_ATRASO` (hoje nunca é calculado).

---

## 5. Buscador de NFS-e e painel legado de conciliação (`/sie`)

Arquivo: `buscador_nfse.py`; serviço local padrão na porta `5000`, com banco `buscador_nfse.db`. Apesar do nome, este painel **não** é o SIE executivo (ver seção 9).

### Persistência e API

- [x] SQLite com tabelas `nfse_oficial`, `documentos`, `documentos_itens`, `conciliacoes` e `sie_eventos`.
- [x] Dados de demonstração para NFS-e/documentos no primeiro início, quando as tabelas correspondentes estão vazias.
- [x] API para listar/cadastrar NFS-e oficial: `GET/POST /api/nfse`.
- [x] Consulta oficial por chave ou por CNPJ + número + série: `GET /api/nfse/consulta`, com resposta 404 quando não encontrada.
- [x] API para criar/listar/consultar documentos e listar pendentes/pagos: `/api/notas`, `/api/notas/consulta`, `/api/notas/pendentes`, `/api/notas/pagas`.
- [x] API de conciliação por chave: `GET/POST /api/conciliacoes`.
- [x] `GET /api/health` e página `/health` com estado e contagens.
- [x] Recepção e listagem de eventos do SIE: `POST /api/sie/webhook`, `GET /api/sie/eventos`.
- [x] Serviço SIE executado no Docker Compose, na mesma rede interna do n8n e com o banco SQLite existente montado; painel/API permanecem acessíveis em `127.0.0.1:5000`.

### Página SIE

- [x] Página `/sie` com contadores, tabela e badges para status de conciliação.
- [x] Cartões-resumo clicáveis para filtrar categorias, busca por chave/número/fornecedor/local/cidade, filtro por status exato e ação para limpar filtros.
- [x] Detalhes expansíveis por registro com chave/número/série, tipo de local, valores lançado/pago e diferença, datas, status e observação.
- [x] Validar a tela com o evento de pagamento simulado: linha da nota da Algar visível na página `/sie` com status `PAGA`.

---

## 6. n8n — workflow de NFS-e e conexão entre serviços

Arquivo: `n8n_workflow_nfse_conciliacao.json`; webhook configurado no arquivo como `sigp-notas`.

- [x] Workflow exportado com webhook, normalização de payload, condição para `nfse_lancada`, condição para `nota_paga` + `MATCH`, nós de API e notificação de evento para SIE.
- [~] Workflow publicado e ativo na instância n8n **do computador anterior** como `SIGp - Notas API + SIE Webhook`, ID `sigpNFSE20261006`. Em 09/10/2026, `POST /webhook/sigp-notas` responde 404 neste computador: o workflow não foi importado.
- [ ] Ramo `nfse_lancada` quebrado: o nó envia `{payload: "<string>"}` e o legado responde 400; "Validar nota e status" lê um campo que não existe na resposta; o evento SIE é enviado em duplicidade. O ramo `nota_paga` grava status fixo `PAGA`.
- [x] Workflow da pasta chama os endpoints do Buscador/SIE pela rede Compose em `http://sie:5000`.
- [x] Definição do workflow ajustada para conter o `webhookId` exigido pelo n8n e corrigir o nome divergente do nó na conexão do evento `nota_paga`.
- [~] A regra “Validar nota e status” compara valores e produz `RECEBIDA` ou `DIVERGENCIA_CADASTRAL`; ela consulta `/api/notas/consulta`, não `/api/nfse/consulta`, portanto não valida contra o cadastro `nfse_oficial` do Buscador.
- [ ] Cobrir nota oficial não encontrada, identidade ambígua e erros técnicos com ramos explícitos e testes.
- [ ] Revisar e testar o payload e as expressões de cada nó no n8n com a versão atualmente utilizada.
- [ ] Implementar tratamento separado para não encontrada, erro técnico, retry e ambiguidade de identidade.
- [ ] Implementar o motor financeiro completo: prazo, atraso, acréscimo, valor inferior e pagamentos parciais.
- [ ] Implementar workflow agendado para expiração de pendências, se ainda fizer parte do escopo.
- [ ] Configurar e testar os destinos e credenciais de produção.

### Workflow de extração de fatura PDF

Arquivo: `n8n_workflow_extrair_fatura_pdf.json`; webhook `sigp-faturas-pdf`.

- [x] Workflow atualizado importado e publicado na instância n8n, mantendo o ID existente; exportação da versão publicada confirmou o novo nó OCR local.
- [x] Webhook de produção `sigp-faturas-pdf` executado com `algar.pdf`: HTTP 200, `ok=true`, `textEncontrado=true` e `ocrUsado=true`.
- [x] Execução posterior confirmada pelo usuário em 08/10/2026 às 19:42:34: workflow concluído com sucesso em 2,313 s, entrada indicada de 16 KB, execução `#2`, versão `b6b0a084`. Confirma o processamento do PDF pelo workflow; não comprova, isoladamente, persistência via interface SIGp.
- [x] Teste do parser no percurso publicado reconheceu emissor, número, vencimento e valor; CNPJ e emissão não foram reconhecidos e permanecem sujeitos a revisão manual.
- [x] Painel n8n acessível pelo Windows em `http://127.0.0.1:5678/healthz` durante a validação (Docker Desktop).
- [x] **Reteste em 09/10/2026:** `algar.pdf` → HTTP 200 em 27 s, `ocrUsado=true`; valor R$ 121,69 e vencimento 16/09/2026 corretos; emissor "TELECOM S/A" (parcial), número "como" (errado), CNPJ e emissão vazios. Observação: o `Invoke-WebRequest` do PowerShell 5.1 derrubou a conexão no upload; com `curl.exe` funcionou.
- [x] Configurar e salvar no navegador a URL `http://127.0.0.1:5678/webhook/sigp-faturas-pdf`; enviar `algar.pdf` pela interface autenticada acionou o n8n e abriu a etapa de revisão.
- [x] Comparação na revisão com a nota `88468`: valor confere, emissor esperado confere pela comparação; vencimento diverge da referência (`2026-09-16` extraído versus `2026-10-10` cadastrado).
- [~] A tela de revisão recebeu a extração, mas o OCR leu o emissor/número parcialmente, não reconheceu CNPJ/data de emissão e exige conferência/correção humana. O usuário confirmou o vínculo desta fatura/nota 88468 com `a_muxd1bz4qek1t`, já existente. A outra nota com a mesma identidade fiscal em `a_muxc15mpwo330` permanece inalterada e fora dos indicadores até resolver a duplicidade.
- [x] Workflow atualizado importado/ativado e webhook de produção testado; integração interface → n8n → revisão verificada. A persistência da fatura pelo fluxo da interface ainda depende da revisão dos campos e de salvar um resultado corrigido.
- [~] O usuário confirmou que o PDF pertence à nota 88468 e ao local `a_muxd1bz4qek1t`; nenhum vínculo precisou ser alterado. A nota com identidade fiscal duplicada em `a_muxc15mpwo330` continua sem alteração. O PDF não foi usado como evidência de pagamento.

### SIG integrado ao SIGp

- [x] Aba **SIG** adicionada à navegação principal, separada do Dashboard geral e da operação de notas/faturas.
- [x] Endpoint `GET /api/sig/resumo` usa as tabelas operacionais do backend SIGp, com período, tipo de local, provedor e status.
- [x] Indicadores iniciais de valores lançados/pagos/pendentes, vencidas, conciliações `MATCH` e divergências; gráficos mensais e por provedor/local.
- [x] Grupos de notas lançadas com chave duplicada são excluídos dos indicadores e sinalizados, sem alterar registros originais.
- [~] A implementação e os testes da API passaram; a validação visual da aba autenticada ainda depende de acessar uma conta existente. Não criar usuário nem alterar dados para contornar essa limitação.
- [ ] Validar com o usuário a semântica do saldo e dos pagamentos parciais e acrescentar drill-down até as notas de origem.

### Integração a alinhar antes de declarar o fluxo fim a fim concluído

- [x] Há dois serviços e dois bancos distintos: backend SIGp/SQLite na porta `5001` e Buscador/SIE/SQLite na porta `5000`.
- [x] O frontend persiste e concilia notas via `/api/notas/lancadas`, `/api/notas/pagas` e `/api/notas/conciliar` na porta `5001`.
- [x] O workflow aponta para `/api/notas`, `/api/notas/consulta` e `/api/conciliacoes` no SIE (`sie:5000`); o backend SIGp/SQLite `5001` continua responsável por persistir a nota e calcular a conciliação.
- [x] Teste de pagamento simulado provou o envio após `MATCH`: a API SIGp gravou o pagamento e conciliação; o n8n atualizou a nota no SIE e registrou `nfse_conciliada`.
- [x] Documentar e validar a integração entre os bancos separados: a API SIGp (`5001`) persiste e concilia; o workflow n8n adapta o resultado para o banco e a tela SIE (`5000`).
- [x] Executar teste ponta a ponta da simulação: SIGp → API `5001` → n8n → SIE `5000` → conferência da nota `PAGA` na página `/sie` e do evento `nfse_conciliada`; não representa pagamento real nem incluiu o PDF.

---

## 7. Testes e evidências

- [x] Há instruções locais no `README.md` para iniciar backend, Buscador/SIE e servidor HTTP do frontend.
- [x] Suíte `unittest` do backend criada e executada: 12 testes passaram para conciliação, pagamentos parciais, duplicidade/idempotência, persistência por par e resumo SIG.
- [x] **09/10/2026:** reexecutada a suíte com `.venv-1`: 12/12. Após as fases 0–2: 29/29 (`tests/test_fluxo_alvo.py` novo).
- [x] **09/10/2026:** teste ponta a ponta da API `5001` em execução (12/12 verificações): lançada, duplicidade 409, parcial `PAGO_PARCIAL`, complemento `MATCH`, valor divergente `DIVERGENCIA`, serviço pendente sem `MATCH`, nota inexistente 404, anexo de PDF, rejeição de não-PDF, resumo SIG e período inválido 400. Banco restaurado do backup e PDF de teste apagado ao final.
- [~] Testar a API `5000` separadamente, incluindo respostas de erro (a `5001` foi coberta acima).
- [ ] Testar importação de XML municipal, XML inválido, JSON, valores em formato brasileiro e nota sem itens.
- [x] Testar conciliação aprovada, divergência de identidade/local, pagamento parcial, classificação pendente/divergente, duplicidade de nota, idempotência, conciliações por par e filtros/indicadores SIG.
- [ ] Testar valores inválidos, serviços com valores diferentes, datas ausentes e integração real do workflow com todos os ramos.
- [ ] Testar indisponibilidade/reinício de cada serviço e recuperação sem perda ou duplicação de dados.
- [x] Exercitar a API de anexos com cliente Flask isolado: upload, confirmação e correspondência do emissor (incluindo acentos), rejeição de emissor divergente/data inválida, comparação de valor/vencimento, preenchimento condicional do vencimento, listagem e download.
- [x] Exercitar a API de faturas por local com cliente Flask isolado: upload e download, comparação com nota vinculada, importação sem referência e rejeição de vínculo a local diferente.
- [x] Testar manualmente o webhook de pagamento na interface autenticada e confirmar conciliação `MATCH`, envio ao n8n, evento no SIE e exibição na página `/sie`.
- [ ] Anexar evidências de execução aos itens cuja conclusão dependa de conta, credencial, endpoint ou serviço externo.

---

## 8. Integrações futuras e fora do escopo implementado

- [ ] Conector automático NS Docs/Praxio para obter notas fiscais; dependente de documentação, acesso, credenciais e endpoints do fornecedor.
- [ ] Confirmação automática de pagamento por Globus/Praxio ou instituição financeira.
- [ ] Consulta de documentos diretamente à SEFAZ/municípios ou a intermediário contratado.
- [ ] Conversão e envio efetivo de comprovante PDF anexado ao WhatsApp.
- [ ] Envio por e-mail, caso seja requisito; não está implementado no workflow de contas encontrado.
- [ ] Migrar para PostgreSQL e definir implantação/backup/monitoramento de produção.

---

## 9. Fluxo alvo de produção (API + webhook) — prontidão em 09/10/2026

Fluxo, endpoints e workflows planejados em [`docs/guia-fluxo-n8n.md`](docs/guia-fluxo-n8n.md).

Estado após as fases 0–2, implementadas em 09/10/2026. "Verificado" = executado no ambiente (teste ponta a ponta pelo n8n, 13/13, com banco restaurado ao final) ou coberto pela suíte automatizada (29 testes).

### Entrada de documentos

- [x] Nota lançada: interface → WF-01 (`sigp-nota-lancada`) → `POST /api/notas/lancadas`; origem `manual` (interface) ou `n8n` (integração). **Verificado.**
- [x] Nota paga: interface → WF-02 (`sigp-nota-paga`) → `POST /api/notas/pagas`, que já concilia. **Verificado.**
- [x] Contingência: se o n8n não responder, a interface grava direto na API (modo configurável em Configurações > Integração).
- [x] Origem externa (`sistemaOrigem`, `idExterno`): reenvio do mesmo documento atualiza em vez de duplicar (prontidão Praxio/Globus). **Testado.**
- [x] Fatura PDF: n8n extrai (OCR local), preenche e exige revisão manual antes de salvar. **Verificado.**
- [ ] IA como segunda tentativa quando o parser do PDF não reconhecer campos.
- [ ] Ligar WF-01/WF-02 às APIs Praxio/Globus (depende da documentação e do acesso).

### Correção, conciliação e alertas

- [x] Correção manual auditada: `PATCH /api/notas/{lancadas|pagas}/<id>` com usuário e motivo, histórico em `/correcoes`, reconciliação automática; 409 se a nova chave já existir. **Verificado.**
- [ ] Tela própria de correção na interface usando o `PATCH` (hoje se corrige editando e salvando o local).
- [x] Conciliação de três vias: `AGUARDANDO_FATURA` sem fatura, `DIVERGENCIA` com fatura divergente, `MATCH` só com as três; anexar a fatura reconcilia. **Verificado.**
- [x] Histórico reprocessado pela regra nova (`POST /api/notas/reconciliar`): a simulação 88468 ficou `AGUARDANDO_FATURA`, porque o PDF está no outro registro duplicado.
- [x] Alerta "fatura não disponível" / "aguardando fatura" no SIG (`/api/alertas`). **Verificado.**
- [x] Locais e provedores na API (`/api/locais`), sincronizados pela interface; quem some é inativado, não apagado. **Verificado.**
- [x] Alertas de vencimento (provedor por `diaVencimento`/`pagoAte`, local por `vencimentoFatura`, nota com saldo) na API e no WF-06 agendado (07:00).
- [ ] Executar o WF-06 pelo agendamento e conferir o resumo do dia no SIG.

### SIG, SIE e notificações

- [x] Aba SIG com indicadores "Aguardando fatura" e "Sem fatura", painel de alertas e análise gerencial do n8n.
- [x] Análise gerencial gravada pelo WF-05 (eventos `AGUARDANDO_FATURA`/`DIVERGENCIA`) e pelo WF-06 (resumo diário). **Verificado (WF-05).**
- [x] Aba **SIE** (executiva) dedicada, só com ciclos fechados em 3 vias, e análise executiva gravada pelo WF-05 no `MATCH`. **Verificado.**
- [~] IA: nó Claude (`claude-opus-5-5`) pronto no WF-05, desativado até `ANTHROPIC_API_KEY`; sem ele, o resumo é por regra fixa.
- [~] Gmail, Telegram e WhatsApp: nós prontos em WF-05, WF-06 e WF-99, desativados até credenciais e variáveis do `.env`.
- [x] WF-99: workflow de erros definido como `errorWorkflow` dos demais.
- [ ] Retry nos nós HTTP do n8n.

### Infraestrutura para produção

- [x] API SIGp no `docker-compose.yml` (serviço `api`) com waitress, chamada pelo n8n como `http://api:5001`.
- [x] Eventos da API para o n8n com fila (`eventos_saida`) e reenvio a cada 15 min (WF-06).
- [~] Autenticação por chave entre n8n e API pronta (`SIGP_API_KEY`), ainda vazia; Header Auth nos webhooks pendente; CORS restrito.
- [ ] Exportar os workflows para a raiz sempre que forem alterados no editor (o volume `n8n_data` não acompanha o repositório).

---

## 10. Documentação a manter sincronizada

- [x] Criado `docs/guia-fluxo-n8n.md` com fluxo alvo, prontidão, possibilidades do n8n e plano de ação (09/10/2026).
- [x] README, `docs/arquitetura.md` e `backend/README.md` atualizados com SIG × SIE × painel legado, `.venv-1` e Docker Desktop (09/10/2026).

- [x] Este checklist atualizado com os módulos encontrados no repositório.
- [x] Atualizar `backend/README.md` com as rotas de notas, conciliação e resumo SIG implementadas.
- [x] Rever `docs/arquitetura.md` para distinguir a API de persistência `5001`, a aba SIG integrada e o Buscador/SIE `5000`.
- [x] Rever o `README.md` para descrever os dois bancos, o endpoint SIG, a conciliação e as pendências reais do PDF/OCR.
- [ ] Sempre que um item for marcado [x], indicar se foi apenas encontrado no código ou também executado/verificado no ambiente.
