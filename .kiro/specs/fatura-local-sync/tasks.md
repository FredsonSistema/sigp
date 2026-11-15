# Implementation Plan: Sincronização de Dados de Provedor entre Fatura e Local

## Overview

Este plano implementa a sincronização automática de dados de provedor (valor, dataVencimento, diaVencimento) entre faturas PDF e registros de Locais no banco SQLite. A implementação seguirá uma abordagem incremental, começando pela lógica core de sincronização, seguida pelos endpoints da API, integração com frontend, e finalizando com a suíte completa de testes.

A estratégia prioriza a criação de funções puras testáveis (normalização de nomes, cálculos de datas) separadas da lógica de persistência, facilitando a escrita de testes unitários e de propriedade.

## Tasks

- [ ] 1. Implementar funções auxiliares puras em database.py
  - Criar função `_normalize_provider_name(nome: str) -> str` para normalizar nomes de provedores
  - Remover acentuação usando `unicodedata.normalize('NFKD', nome).encode('ASCII', 'ignore').decode('ASCII')`
  - Converter para lowercase usando `casefold()`
  - Remover caracteres não-alfanuméricos mantendo apenas letras e números
  - Criar função `_calcular_dia_vencimento(data_vencimento: str) -> int` para extrair dia do mês de string AAAA-MM-DD
  - Criar função `_valores_iguais(valor1: float, valor2: float, tolerancia: float = 0.01) -> bool` para comparar valores com tolerância
  - Criar função `_calcular_vencimento_minimo(provedores: List[Dict]) -> str` que retorna menor dataVencimento válida do array
  - _Requirements: 1.4, 2.1, 4.1, 5.1_

- [ ]* 1.1 Escrever testes unitários para funções auxiliares puras
  - Testar `_normalize_provider_name` com variações: acentos, maiúsculas/minúsculas, espaços, caracteres especiais
  - Testar `_calcular_dia_vencimento` com datas válidas (início, meio, fim do mês)
  - Testar `_valores_iguais` com valores idênticos, próximos (< 0.01) e distantes (> 0.01)
  - Testar `_calcular_vencimento_minimo` com múltiplas datas válidas, array vazio, datas inválidas
  - _Requirements: 1.4, 2.1, 4.1, 5.1_

- [ ]* 1.2 Escrever testes de propriedade para normalização de nomes
  - **Property 2: Normalização de nome identifica provedor corretamente**
  - **Validates: Requirements 2.1**
  - Usar Hypothesis para gerar strings aleatórias
  - Verificar que normalização é idempotente: `normalize(normalize(x)) == normalize(x)`
  - Verificar que variações de case produzem mesmo resultado: `normalize(x.upper()) == normalize(x.lower())`
  - _Requirements: 2.1_

- [ ] 2. Implementar função core sync_provider_from_invoice em database.py
  - [ ] 2.1 Criar função `sync_provider_from_invoice(local_id, emissor_nome, valor_total, data_vencimento, origem)` com validação de entrada
    - Validar que `local_id` existe no banco (SELECT FROM locais WHERE id = ?)
    - Validar que `emissor_nome` não está vazio, lançar ValueError se inválido
    - Converter `valor_total` para float, usar 0.0 se conversão falhar
    - _Requirements: 1.1, 2.1_

  - [ ] 2.2 Implementar busca e deserialização do Local
    - Executar SELECT para buscar registro do Local
    - Deserializar `provedores_json` usando json.loads, assumir [] se JSON corrompido
    - Logar WARNING se JSON corrompido for detectado
    - _Requirements: 1.1_

  - [ ] 2.3 Implementar lógica de identificação do provedor por nome normalizado
    - Normalizar `emissor_nome` usando `_normalize_provider_name`
    - Iterar por array de provedores, normalizar cada `provedor["nome"]`
    - Comparar nomes normalizados para encontrar provedor existente
    - Logar WARNING se múltiplos provedores com nome normalizado idêntico forem encontrados
    - _Requirements: 2.1, 2.2_

  - [ ] 2.4 Implementar verificação de idempotência
    - Se provedor encontrado, comparar `valor`, `dataVencimento` e `diaVencimento` atuais com novos valores
    - Usar `_valores_iguais` para comparação de valores
    - Se todos os campos idênticos, retornar Local sem modificações e sem registrar evento
    - _Requirements: 4.1_

  - [ ] 2.5 Implementar lógica de atualização ou criação de provedor
    - Se provedor existe: atualizar campos `valor`, `dataVencimento`, `diaVencimento`, preservar `nome` original
    - Se `valor_total` é None ou 0, preservar `valor` existente
    - Se `data_vencimento` vazio ou inválido, preservar `dataVencimento` existente
    - Se provedor não existe: criar novo objeto com UUID único, `nome=emissor_nome`, campos extraídos
    - Calcular `diaVencimento` usando `_calcular_dia_vencimento`
    - _Requirements: 1.2, 1.3, 1.4, 2.2, 2.3, 2.4, 2.5, 4.2, 4.3_

  - [ ] 2.6 Implementar recálculo de vencimentoFatura do Local
    - Usar `_calcular_vencimento_minimo` para obter menor vencimento entre provedores
    - Se resultado vazio (todos provedores sem data válida), preservar `vencimento_fatura` atual do Local
    - _Requirements: 1.5, 5.1, 5.2_

  - [ ] 2.7 Implementar persistência e logging
    - Serializar array de provedores usando json.dumps
    - Executar UPDATE locais SET provedores_json=?, vencimento_fatura=?, updated_at=? WHERE id=?
    - Registrar evento `provedor_sincronizado` via `log_event` com payload completo
    - Buscar e retornar Local atualizado usando `get_local(local_id)`
    - _Requirements: 1.6, 5.3, 8.1_

- [ ]* 2.8 Escrever testes de integração para sync_provider_from_invoice
  - Testar criação de novo provedor em Local vazio
  - Testar atualização de provedor existente (mesmo nome normalizado, valores diferentes)
  - Testar preservação de nome cadastrado quando emissorNome varia
  - Testar idempotência (mesmos valores não atualizam updated_at)
  - Testar recálculo de vencimentoFatura com múltiplos provedores
  - Testar tratamento de dados inválidos (valor None, data vazia)
  - Usar banco SQLite em memória para isolamento
  - _Requirements: 1.2, 1.3, 1.4, 1.5, 2.2, 2.3, 2.4, 4.1, 4.2, 4.3, 5.1_

- [ ]* 2.9 Escrever testes de propriedade para lógica de sincronização
  - **Property 1: Sincronização de campos do provedor**
  - **Validates: Requirements 1.2, 1.3, 1.4**
  - **Property 3: Provedor é criado ou atualizado sem duplicação**
  - **Validates: Requirements 2.2, 2.3, 2.5**
  - **Property 5: vencimentoFatura reflete menor vencimento válido**
  - **Validates: Requirements 1.5, 5.1**
  - **Property 6: Sincronização é idempotente**
  - **Validates: Requirements 4.1, 8.2**
  - Usar Hypothesis para gerar valores aleatórios de fatura (valor, data)
  - Verificar que sincronizar duas vezes não altera resultado
  - Verificar que vencimentoFatura é sempre o mínimo válido
  - _Requirements: 1.2, 1.3, 1.4, 1.5, 2.2, 2.3, 2.5, 4.1, 5.1, 8.2_

- [ ] 3. Checkpoint - Validar função core de sincronização
  - Executar testes unitários e de integração de sync_provider_from_invoice
  - Verificar que todos os testes passam
  - Perguntar ao usuário se há dúvidas sobre a lógica implementada

- [ ] 4. Modificar endpoint POST /api/faturas em app.py
  - [ ] 4.1 Adicionar chamada a sync_provider_from_invoice após salvar fatura
    - Extrair `emissor_nome`, `valor_total`, `data_vencimento` do payload ou dados extraídos
    - Envolver chamada em try-except para não falhar salvamento se sincronização falhar
    - Logar erro com `app.logger.error` se exceção ocorrer
    - Definir `origem="fluxo_manual"`
    - _Requirements: 1.1, 1.6_

  - [ ] 4.2 Modificar resposta JSON para incluir localAtualizado
    - Adicionar campo `localAtualizado` no objeto de resposta
    - Se sincronização falhou, definir `localAtualizado=None`
    - _Requirements: 1.6_

- [ ]* 4.3 Escrever testes de integração para POST /api/faturas
  - Usar Flask test client
  - Mockar ou usar OCR real para extração de dados
  - Criar Local de teste no banco
  - Enviar POST com PDF e metadados
  - Verificar que resposta contém `localAtualizado` com provedor atualizado
  - Verificar que banco foi atualizado corretamente
  - Testar erro de sincronização não falha salvamento de fatura
  - _Requirements: 1.1, 1.2, 1.3, 1.6, 7.1_

- [ ] 5. Modificar endpoint PATCH /api/notas-recebidas/{id}/associar em app.py
  - [ ] 5.1 Adicionar chamada a sync_provider_from_invoice após associar nota
    - Após criar/atualizar fatura_local, buscar `dados_json` da fatura
    - Extrair `emissorNome`, `valorTotal`, `dataVencimento` de `dados_json`
    - Envolver chamada em try-except conforme Requirement 3.4
    - Logar erro mas não reverter associação
    - Definir `origem="fluxo_gmail"`
    - _Requirements: 3.1, 3.2, 3.4_

  - [ ] 5.2 Modificar resposta JSON para incluir localAtualizado
    - Adicionar campo `localAtualizado` no objeto de resposta
    - Se sincronização falhou, incluir campo opcional `syncError` com mensagem de erro
    - _Requirements: 3.3, 3.4_

- [ ]* 5.3 Escrever testes de integração para PATCH /api/notas-recebidas/{id}/associar
  - Criar nota recebida de teste no banco
  - Criar Local de teste
  - Enviar PATCH para associar nota ao Local
  - Verificar que resposta contém `localAtualizado` com provedor atualizado
  - Verificar que banco foi atualizado corretamente
  - Testar erro de sincronização não reverte associação (campo syncError presente, associação mantida)
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [ ] 6. Implementar endpoint POST /api/locais/{id}/sincronizar-provedores em app.py
  - [ ] 6.1 Criar rota com proteção de API key
    - Definir decorator @app.post para rota `/api/locais/<local_id>/sincronizar-provedores`
    - Aplicar validação de API key existente
    - _Requirements: 6.1_

  - [ ] 6.2 Implementar lógica de busca de faturas mais recentes por provedor
    - Buscar Local usando `get_local(local_id)`
    - Retornar 404 se Local não encontrado
    - Buscar todas faturas do Local usando `list_faturas_locais(entidade_tipo, entidade_id)`
    - Agrupar faturas por nome normalizado do emissor, mantendo apenas a mais recente por provedor
    - Comparar campo `created_at` para determinar fatura mais recente
    - _Requirements: 6.2, 6.4_

  - [ ] 6.3 Implementar loop de sincronização retroativa
    - Iterar por faturas mais recentes
    - Para cada fatura, chamar `sync_provider_from_invoice` com `origem="sincronizacao_retroativa"`
    - Capturar exceções individuais e logar erro sem interromper loop
    - Contar provedores sincronizados com sucesso
    - _Requirements: 6.2_

  - [ ] 6.4 Implementar resposta e logging de sincronização retroativa
    - Registrar evento `sincronizacao_retroativa` via `log_event` com localId e contagem
    - Buscar Local atualizado
    - Retornar JSON com `ok=True`, `localAtualizado` e `provedoresSincronizados`
    - _Requirements: 6.3, 8.3_

- [ ]* 6.5 Escrever testes de integração para POST /api/locais/{id}/sincronizar-provedores
  - Criar Local de teste com múltiplas faturas históricas de provedores diferentes
  - Enviar POST para endpoint de sincronização
  - Verificar que resposta contém contagem correta de provedores sincronizados
  - Verificar que Local foi atualizado com dados das faturas mais recentes
  - Testar 404 para Local inexistente
  - Verificar que evento `sincronizacao_retroativa` foi registrado
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 8.3_

- [ ] 7. Checkpoint - Validar endpoints da API
  - Executar todos os testes de integração dos endpoints
  - Verificar que todos os testes passam
  - Testar manualmente com Postman ou curl se necessário
  - Perguntar ao usuário se há dúvidas sobre a implementação backend

- [ ] 8. Atualizar módulo faturas-provedores.js no frontend
  - [ ] 8.1 Modificar função save() para consumir localAtualizado
    - Após receber resposta de POST /api/faturas, extrair campo `result.localAtualizado`
    - Se `localAtualizado` presente, disparar evento customizado `sigp:local-updated` com local no detail
    - Remover código que escreve valor/vencimento de provedor no localStorage (agora vem da API)
    - _Requirements: 7.1, 7.2_

  - [ ] 8.2 Adicionar tratamento de erro de sincronização
    - Se resposta contém `syncError`, exibir alerta ou notificação ao usuário
    - Não bloquear fluxo de salvamento de fatura
    - _Requirements: 3.4_

- [ ] 9. Atualizar página agencias.html para responder a evento de Local atualizado
  - [ ] 9.1 Adicionar listener para evento sigp:local-updated
    - Capturar `event.detail.local` do evento customizado
    - Buscar card do Local na DOM usando `data-local-id`
    - Chamar função de re-renderização do card com dados atualizados
    - _Requirements: 7.2_

  - [ ] 9.2 Atualizar cache global de locais em memória
    - Localizar Local no array `storedLocais` por ID
    - Substituir objeto antigo por `localAtualizado`
    - Garantir que próximas renderizações usem dados atualizados
    - _Requirements: 7.2, 7.3_

- [ ]* 10. Escrever testes E2E para fluxos completos
  - [ ]* 10.1 Testar fluxo manual completo (upload PDF → sincronização → atualização UI)
    - Usar Playwright ou Selenium para automação de navegador
    - Criar Local de teste via API
    - Fazer upload de PDF de fatura via interface
    - Verificar que card do Local exibe valor e vencimento atualizados sem refresh manual
    - _Requirements: 1.1, 1.2, 1.3, 1.6, 7.1, 7.2_

  - [ ]* 10.2 Testar fluxo Gmail completo (nota recebida → associação → sincronização)
    - Criar nota recebida de teste via API
    - Criar Local de teste
    - Associar nota ao Local via PATCH
    - Verificar que Local foi atualizado no banco
    - Verificar que evento foi registrado
    - _Requirements: 3.1, 3.2, 3.3, 8.1_

  - [ ]* 10.3 Testar fluxo de sincronização retroativa
    - Criar Local com múltiplas faturas históricas via API
    - Chamar endpoint de sincronização retroativa
    - Verificar que todos provedores foram atualizados
    - Verificar contagem retornada
    - _Requirements: 6.2, 6.3, 6.4, 8.3_

- [ ] 11. Implementar script de migração de dados históricos
  - [ ] 11.1 Criar script Python para executar sincronização retroativa em todos Locais
    - Iterar por todos registros na tabela `locais`
    - Para cada Local, chamar `sync_provider_from_invoice` com faturas mais recentes
    - Logar progresso e erros em arquivo de log
    - Exibir resumo ao final (total de Locais processados, provedores sincronizados, erros)
    - _Requirements: 6.2_

  - [ ] 11.2 Adicionar documentação do script de migração
    - Criar arquivo README_MIGRACAO.md com instruções de uso
    - Documentar pré-requisitos e backup recomendado
    - Incluir exemplos de execução e interpretação de resultados
    - _Requirements: 6.2_

- [ ] 12. Documentar a feature implementada
  - [ ] 12.1 Atualizar README.md do projeto
    - Adicionar seção sobre sincronização automática de provedores
    - Explicar os dois fluxos (manual e Gmail)
    - Documentar endpoint de sincronização retroativa
    - _Requirements: 6.1, 6.2_

  - [ ] 12.2 Adicionar comentários inline no código
    - Documentar funções auxiliares puras com docstrings
    - Adicionar comentários explicativos em lógica complexa (normalização, agrupamento de faturas)
    - Documentar parâmetros e retornos de sync_provider_from_invoice
    - _Requirements: 1.1, 2.1, 6.2_

  - [ ] 12.3 Criar arquivo de changelog
    - Documentar alterações nos endpoints existentes
    - Listar novo endpoint criado
    - Mencionar modificações no frontend (remoção de dependência do localStorage)
    - _Requirements: 1.1, 3.1, 6.1, 7.1_

- [ ] 13. Checkpoint final - Validação completa
  - Executar toda a suíte de testes (unit, integration, E2E)
  - Verificar que todos os testes passam
  - Executar script de migração em ambiente de teste
  - Fazer smoke test manual dos três fluxos (manual, Gmail, retroativo)
  - Perguntar ao usuário se há ajustes necessários antes do deploy

## Notes

- Tasks marcadas com `*` são opcionais e podem ser puladas para entrega mais rápida do MVP
- Cada task referencia requirements específicos para rastreabilidade
- Checkpoints garantem validação incremental antes de avançar
- Property tests cobrem apenas lógica pura (normalização, cálculos); testes de integração cobrem operações de I/O
- Frontend depende do backend; implementar tasks 1-7 antes de tasks 8-9
- Testes E2E (task 10) dependem de backend e frontend completos
- Script de migração (task 11) pode ser executado após implementação completa para corrigir dados históricos

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3"] },
    { "id": 3, "tasks": ["2.4", "2.5"] },
    { "id": 4, "tasks": ["2.6", "2.7"] },
    { "id": 5, "tasks": ["2.8", "2.9"] },
    { "id": 6, "tasks": ["4.1", "5.1", "6.1"] },
    { "id": 7, "tasks": ["4.2", "5.2", "6.2"] },
    { "id": 8, "tasks": ["4.3", "5.3", "6.3"] },
    { "id": 9, "tasks": ["6.4", "6.5"] },
    { "id": 10, "tasks": ["8.1", "9.1"] },
    { "id": 11, "tasks": ["8.2", "9.2"] },
    { "id": 12, "tasks": ["10.1", "10.2", "10.3"] },
    { "id": 13, "tasks": ["11.1", "12.1"] },
    { "id": 14, "tasks": ["11.2", "12.2", "12.3"] }
  ]
}
```
