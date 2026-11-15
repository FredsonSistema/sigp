# Requirements Document

## Introduction

O SIGp gerencia notas fiscais de provedores de internet/telecom para um grupo de empresas de transporte (ROTA TRANSPORTES, VIAÇÃO JEQUÊ, EXPRESSO BRASILEIRO). Cada agência, rodoviária ou garagem (Local) possui um array de provedores; cada provedor mantém campos de valor e vencimento que alimentam o card do local, o painel SIG e os alertas de vencimento.

Atualmente, quando uma fatura PDF é associada a um Local — seja pelo upload manual (aba Faturas) ou pela associação de uma nota recebida do Gmail (WF-08) — os campos `valor`, `dataVencimento` e `diaVencimento` do provedor **não são persistidos na API**. No fluxo manual eles são escritos apenas no `localStorage` do navegador; no fluxo Gmail eles não são escritos em lugar algum. O resultado é que o card do Local exibe dados desatualizados e os alertas de vencimento do backend ficam sem referência.

Esta feature implementa a **sincronização automática dos dados do provedor** na API (Flask + SQLite) sempre que uma fatura PDF for salva, associada ou reavaliada em qualquer dos dois fluxos, eliminando a dependência do `localStorage` para essa finalidade.

---

## Glossary

- **Local**: Agência, rodoviária ou garagem. Registrado na tabela `locais` com `id`, `tipo`, `nome`, `cidade`, `vencimento_fatura`, `provedores_json` e `dados_json`.
- **Provedor**: Objeto dentro do array `provedores` de um Local. Campos relevantes: `id`, `nome`, `valor`, `diaVencimento`, `dataVencimento`, `pagoAte`, `faturaAtualId`.
- **Fatura PDF**: Documento PDF de cobrança de um provedor; armazenado em `faturas_locais` ou `faturas_provedores`.
- **vencimentoFatura**: Campo de nível raiz do Local (`vencimento_fatura` na tabela `locais`). Representa o menor vencimento entre todos os provedores ativos; usado pelos alertas e pelo card.
- **diaVencimento**: Número do dia do mês (1–31) em que o provedor normalmente vence. Derivado de `dataVencimento`.
- **Fluxo Manual**: Upload de fatura PDF pelo usuário na aba Faturas (via POST `/api/faturas`).
- **Fluxo Gmail**: Importação automática via WF-08 e associação via PATCH `/api/notas-recebidas/{id}/associar`.
- **Sincronização**: Operação de atualizar `provedores_json` e `vencimento_fatura` do Local na API com base nos dados extraídos da fatura.
- **API_Backend**: Servidor Flask em `backend/app.py`.
- **Banco_de_Dados**: SQLite acessado via `backend/database.py`.

---

## Requirements

### Requirement 1: Sincronização de provedor ao salvar fatura (Fluxo Manual)

**User Story:** Como operador, quero que ao salvar uma fatura PDF pela aba Faturas os campos de valor e vencimento do provedor naquele Local sejam atualizados na API automaticamente, para que o card e os alertas reflitam os dados corretos sem depender do armazenamento local do navegador.

#### Acceptance Criteria

1. WHEN o endpoint `POST /api/faturas` recebe uma fatura com `entidadeTipo`, `entidadeId` e `emissorNome` válidos, THE API_Backend SHALL invocar `sync_provider_from_invoice` para atualizar os dados do provedor correspondente no Local antes de retornar a resposta.
2. WHEN `sync_provider_from_invoice` é invocada, THE Banco_de_Dados SHALL atualizar o campo `valor` do provedor com o `valorTotal` da fatura.
3. WHEN `sync_provider_from_invoke` é invocada, THE Banco_de_Dados SHALL atualizar o campo `dataVencimento` do provedor com o `dataVencimento` extraído da fatura.
4. WHEN `dataVencimento` está presente no payload da fatura, THE Banco_de_Dados SHALL derivar e persistir o campo `diaVencimento` como o número do dia do mês daquele vencimento (1–31).
5. WHEN `sync_provider_from_invoice` é invocada, THE Banco_de_Dados SHALL recalcular e persistir `vencimento_fatura` do Local como o menor `dataVencimento` entre todos os provedores com `dataVencimento` não vazio.
6. WHEN a resposta do `POST /api/faturas` é retornada, THE API_Backend SHALL incluir o campo `localAtualizado` no JSON de resposta, contendo o objeto do Local após a sincronização.

### Requirement 2: Identificação e upsert do provedor pelo nome normalizado

**User Story:** Como operador, quero que a sincronização encontre o provedor correto pelo nome (mesmo com variações de acento, caixa ou espaço) e crie um novo registro de provedor se ele ainda não existir no Local, para que nenhuma fatura fique sem associação.

#### Acceptance Criteria

1. WHEN `sync_provider_from_invoice` busca o provedor no Local, THE Banco_de_Dados SHALL normalizar o nome do emissor e os nomes dos provedores existentes usando a função `_normalize_provider_name` (remoção de acentos, `casefold`, somente alfanuméricos) antes de comparar.
2. WHEN um provedor com nome normalizado igual ao do emissor é encontrado no Local, THE Banco_de_Dados SHALL atualizar o registro desse provedor e não criar um duplicado.
3. WHEN nenhum provedor com nome normalizado correspondente é encontrado no Local, THE Banco_de_Dados SHALL criar um novo registro de provedor com `nome` igual ao `emissorNome` da fatura, `valor`, `dataVencimento` e `diaVencimento` extraídos.
4. IF o campo `nome` do provedor já está preenchido no Local e é diferente do `emissorNome` da fatura, THEN THE Banco_de_Dados SHALL preservar o nome cadastrado e não substituí-lo pelo nome extraído do PDF.
5. WHEN um novo provedor é criado, THE Banco_de_Dados SHALL atribuir um `id` único (UUID) a esse registro.

### Requirement 3: Sincronização de provedor ao associar nota recebida (Fluxo Gmail)

**User Story:** Como operador, quero que ao associar uma nota recebida do Gmail a um Local (PATCH `/api/notas-recebidas/{id}/associar`) os campos de valor e vencimento do provedor sejam atualizados na API, para que o fluxo automático também mantenha os dados do Local atualizados.

#### Acceptance Criteria

1. WHEN o endpoint `PATCH /api/notas-recebidas/{id}/associar` conclui com sucesso e cria ou atualiza uma `fatura_local`, THE API_Backend SHALL invocar `sync_provider_from_invoice` para o Local associado antes de retornar a resposta.
2. WHEN `sync_provider_from_invoice` é invocada pelo fluxo Gmail, THE Banco_de_Dados SHALL usar os dados extraídos já gravados em `dados_json` da `fatura_local` como fonte para a sincronização.
3. WHEN a resposta do `PATCH /api/notas-recebidas/{id}/associar` é retornada, THE API_Backend SHALL incluir o campo `localAtualizado` no JSON de resposta com o objeto do Local após a sincronização.
4. IF `sync_provider_from_invoice` falhar internamente (erro SQLite ou dado ausente), THEN THE API_Backend SHALL registrar o erro no log e continuar retornando a resposta de sucesso da associação, sem reverter a operação de associação já confirmada.

### Requirement 4: Idempotência da sincronização

**User Story:** Como sistema, quero que reenviar a mesma fatura não altere os dados do Local se os valores já forem idênticos, para evitar conflitos em reprocessamentos.

#### Acceptance Criteria

1. WHEN `sync_provider_from_invoice` detecta que `valor`, `dataVencimento` e `diaVencimento` do provedor já correspondem aos valores da fatura recebida (diferença de valor < R$ 0,01), THE Banco_de_Dados SHALL omitir a escrita no banco e não atualizar `updated_at` do Local.
2. WHEN o payload da fatura apresenta `valorTotal` nulo ou zero, THE Banco_de_Dados SHALL preservar o `valor` existente do provedor sem alterá-lo.
3. WHEN o payload da fatura apresenta `dataVencimento` vazio ou inválido, THE Banco_de_Dados SHALL preservar o `dataVencimento` existente do provedor sem alterá-lo.

### Requirement 5: Atualização do campo `vencimentoFatura` do Local

**User Story:** Como operador, quero que o campo `vencimentoFatura` do Local reflita sempre o menor vencimento entre os provedores ativos, para que o card exiba a data mais urgente e os alertas funcionem corretamente.

#### Acceptance Criteria

1. WHEN `sync_provider_from_invoice` atualiza os dados de um provedor, THE Banco_de_Dados SHALL recalcular `vencimento_fatura` como o mínimo de `dataVencimento` entre todos os provedores do Local cujo `dataVencimento` seja uma data válida no formato AAAA-MM-DD.
2. WHEN todos os provedores do Local possuem `dataVencimento` vazio ou inválido, THE Banco_de_Dados SHALL preservar o valor atual de `vencimento_fatura` do Local sem alterá-lo.
3. THE Banco_de_Dados SHALL persistir `vencimento_fatura` na tabela `locais` via `UPDATE locais SET vencimento_fatura = ?, updated_at = ? WHERE id = ?` dentro da mesma transação da atualização dos provedores.

### Requirement 6: Endpoint de sincronização manual (reconciliação retroativa)

**User Story:** Como operador, quero poder disparar a sincronização de provedores a partir das faturas já salvas via `POST /api/locais/{id}/sincronizar-provedores`, para corrigir dados históricos de Locais que foram importados antes desta feature.

#### Acceptance Criteria

1. THE API_Backend SHALL expor o endpoint `POST /api/locais/{local_id}/sincronizar-provedores` protegido pela mesma regra de API key dos demais endpoints de escrita.
2. WHEN o endpoint é chamado para um Local existente, THE API_Backend SHALL iterar pelas `faturas_locais` mais recentes por provedor desse Local e invocar `sync_provider_from_invoice` para cada uma.
3. WHEN o endpoint é chamado para um Local existente, THE API_Backend SHALL retornar `{ "ok": true, "localAtualizado": {...}, "provedoresSincronizados": N }` onde `N` é o número de provedores cujos dados foram alterados.
4. IF o `local_id` não corresponder a nenhum Local cadastrado, THEN THE API_Backend SHALL retornar HTTP 404 com `{ "ok": false, "error": "Local não encontrado." }`.

### Requirement 7: Ausência de regressão no fluxo de upload manual do frontend

**User Story:** Como desenvolvedor, quero que o fluxo de upload manual existente no `faturas-provedores.js` continue funcionando após esta feature, sem depender do `localStorage` para propagar dados de fatura ao Local.

#### Acceptance Criteria

1. WHEN o frontend recebe a resposta de `POST /api/faturas` com o campo `localAtualizado`, THE Frontend SHALL utilizar esses dados para atualizar o estado em memória do Local, em vez de escrever diretamente no `localStorage`.
2. WHEN o módulo `faturas-provedores.js` conclui o salvamento de uma fatura, THE Frontend SHALL disparar a re-renderização do card do Local usando o objeto `localAtualizado` retornado pela API, sem chamar `PUT /api/locais/{tipo}` para propagar apenas esse campo.
3. THE Frontend SHALL preservar as demais gravações no `localStorage` não relacionadas à sincronização de fatura (backups, estado de OS, etc.).

### Requirement 8: Rastreabilidade das sincronizações

**User Story:** Como operador, quero que cada sincronização automática de provedor seja registrada no log de eventos, para facilitar auditoria e depuração.

#### Acceptance Criteria

1. WHEN `sync_provider_from_invoice` atualiza com sucesso os dados de um provedor, THE API_Backend SHALL registrar um evento de tipo `provedor_sincronizado` via `log_event` com os campos: `localId`, `localTipo`, `provedorNome`, `valorAnterior`, `valorNovo`, `dataVencimentoAnterior`, `dataVencimentoNovo`, `origem` (`"fluxo_manual"` ou `"fluxo_gmail"`).
2. WHEN `sync_provider_from_invoice` detecta que os dados já estão atualizados (idempotência), THE API_Backend SHALL omitir o registro de evento.
3. FOR ALL chamadas ao endpoint `POST /api/locais/{local_id}/sincronizar-provedores`, THE API_Backend SHALL registrar um evento de tipo `sincronizacao_retroativa` com `localId` e `provedoresSincronizados`.
