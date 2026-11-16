# SIGp — Auditoria de faturas de provedores

> **Entrega 2:** veja [`README-ENTREGA2.md`](README-ENTREGA2.md) (documentos e como testar), [`GUIA-INSTALACAO.md`](GUIA-INSTALACAO.md) e [`ENDPOINTS.md`](ENDPOINTS.md).

**Grupo e integrantes:** ver [`identificacao.json`](identificacao.json) (a mesma identificação de todos os PDFs).  
**Disciplinas:** Projeto de Inteligência Artificial; Segurança e Otimização de Banco de Dados.

## Parte 2 (16/11/2026)

- **[Relatório de andamento da parte 2](relatorio-parte2.pdf)**: o que foi feito desde a parte 1, limites, evidências e contribuição individual (gerado por `gerar_parte2.py`).
- Evidências: [`sqlserver/evidence/parte2/`](sqlserver/evidence/parte2/) (n8n ponta a ponta, casos de teste, IA sem permissão e injeção, auditoria, mascaramento, benchmark e planos, latência e custo, memória de exemplos) e [`seguranca/permissoes-perfis.md`](seguranca/permissoes-perfis.md) (matriz de perfis e permissões da API).
- Casos de teste: [`ia/casos-de-teste-parte2.md`](ia/casos-de-teste-parte2.md) · Prompts: [`ia/prompts/CHANGELOG.md`](ia/prompts/CHANGELOG.md) · Roteiro do vídeo/prints: [`roteiro-video-parte2.md`](roteiro-video-parte2.md).
- Histórico de todas as mudanças (antes e depois, com a verificação): [`../registro-mudancas.md`](../registro-mudancas.md).

## Parte 1 (02/11/2026)
**Disciplinas:** Projeto de Inteligência Artificial; Segurança e Otimização de Banco de Dados.

## Problema e objetivo

Quem acompanha as contas de internet de agências, rodoviárias e garagens precisa identificar faturas vencidas, diferenças de valor e serviços cobrados que não constam no contrato. Hoje os dados chegam em arquivos separados e em momentos diferentes. O SIGp organiza esses documentos e destaca casos para conferência humana, sem autorizar pagamentos.

## Usuário, entradas e saídas

- **Usuário:** responsável por conferir contas e auditor.
- **Entradas:** faturas PDF e notas/pagamentos fictícios em XML ou JSON, importados manualmente ou por fluxo n8n.
- **Saídas:** conciliação, divergências justificadas, itens pendentes de revisão e trilha de auditoria.
- **Interface da entrega acadêmica:** comandos de terminal e API local; não depende de SaaS, site ou chatbot.

## Estado da implementação acadêmica (02/11/2026)

```text
JSON fictício → API acadêmica → procedure SQL Server com RLS
                       → busca lexical em 20 documentos fictícios
                       → regra determinística + comparação Qwen local
                       → decisão, fontes e auditoria
```

O SIGp operacional ainda usa SQLite; não houve migração. O SQL Server acadêmico e o corpus são isolados e usam somente dados sintéticos. Nos cinco casos da API, as regras e verificações de segurança acertaram 5/5, mas o modelo concordou em 3/5. Um fine-tuning LoRA separado obteve macro-F1 0,522 → 0,900 em 20 exemplos sintéticos de teste; cenários repetidos entre partições tornam o resultado exploratório, e o adaptador não está integrado ao serviço. O endpoint direto está testado; o workflow n8n está importado e inativo. Embeddings/Qdrant e integração NSDocs/Globus permanecem pendentes. Veja [`guia-do-aluno.md`](guia-do-aluno.md), [`plano-tecnico.md`](plano-tecnico.md) e [`ia/finetuning/README.md`](ia/finetuning/README.md) para detalhes e limites.

## Material da entrega

O SQL Server aplica RLS e testes de papéis/permissões; os detalhes e evidências estão em [`sqlserver/README.md`](sqlserver/README.md). O resultado real dos cinco casos está em `sqlserver/evidence/ai-test-results.json`. Os resultados do fine-tuning LoRA e o adaptador ficam em [`ia/finetuning/README.md`](ia/finetuning/README.md). Os PDFs devem ser regenerados depois de qualquer mudança nesses documentos.

## Maior risco e MVP em três semanas

**Risco:** sugestão errada ou instrução maliciosa em um documento influenciar a análise. Mitigação: contexto delimitado, citações, testes de prompt injection, permissões sem escrita para IA e aprovação humana.

**MVP proposto:** SQL Server local com carga sintética, duas consultas medidas, CLI de importação/consulta e fluxo n8n de entrada. RAG local e relatório de sugestões só entram se forem realmente implementados e validados no prazo.

**Repositório:** <https://github.com/FredsonSistema/sigp>. Instruções detalhadas, métricas e matriz de permissões em [`plano-tecnico.md`](plano-tecnico.md).

## PDFs da entrega
- [Relatório da parte 2](relatorio-parte2.pdf)

- [Parte de IA](parte-ia.pdf)
- [Parte de Segurança e Otimização](parte-seguranca.pdf)
- [Parte de Integração](parte-integracao.pdf)
- [Entrega completa (as três partes)](entrega-completa.pdf)
- [Guia do aluno — revisão crítica, custos, LGPD e pendências](guia-do-aluno.pdf)

O guia confronta as propostas acadêmicas com o estado observado do SIGp e lista o que ainda precisa ser implementado ou comprovado. O adaptador LoRA é um experimento isolado; não confundir com o LLM usado pelo endpoint nem apresentar como funcionalidade integrada.

Para recriar os arquivos neste ambiente: `pip install -r requirements-pdf.txt`, `python gerar_pdfs.py` e `python gerar_parte2.py`.
