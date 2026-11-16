# SIGp — Entrega 2 (IA · Segurança e Otimização de Banco · Integração)

Este arquivo diz **onde está cada documento da entrega 2** e **como testar**.

**Equipe:** Fredson Pereira de Oliveira Santos · Maciel Lopes Francisco · Aeverton Santos · Jonatas de Jesus Souza
**Repositório:** <https://github.com/FredsonSistema/sigp>

## O que é avaliado

A entrega acadêmica é um **serviço local**, sem site, sem SaaS e sem landing page. Ele audita faturas de internet de localidades (agências, rodoviárias e garagens):

```text
fatura (JSON) → webhook do n8n → API da IA → SQL Server (RLS, escopo por local)
              → RAG (documentos citados) → Qwen 0.5B local → classificação + auditoria
```

- Para testar, use o **terminal** (PowerShell), o **Postman** ou o **n8n**.
- Todos os dados são **fictícios**.
- A regra decide a classificação. O modelo só sugere. Nada é pago automaticamente.

> **Sobre o restante do repositório.** O repositório também contém o SIGp de uso pessoal do autor, que tem interface web (`frontend/`, `web/`) e fluxos de produção (`n8n/wf*`). **Essas pastas não fazem parte da avaliação.** Tudo o que é avaliado está em `docs/entrega-academica/`.

## Onde estão os documentos

Caminhos relativos a `docs/entrega-academica/`.

| O quê | Arquivo |
|---|---|
| **Relatório da entrega 2** (5 páginas, na ordem do enunciado) | [`relatorio-parte2.pdf`](relatorio-parte2.pdf) |
| Partes separadas | [`parte-ia.pdf`](parte-ia.pdf) · [`parte-seguranca.pdf`](parte-seguranca.pdf) · [`parte-integracao.pdf`](parte-integracao.pdf) · [`entrega-completa.pdf`](entrega-completa.pdf) |
| Roteiro do vídeo | [`roteiro-video-parte2.md`](roteiro-video-parte2.md) |
| **IA**: casos de teste (entrada, esperado, obtido) | [`ia/casos-de-teste-parte2.md`](ia/casos-de-teste-parte2.md) |
| IA: prompts versionados | [`ia/prompts/`](ia/prompts/) e [`ia/prompts/CHANGELOG.md`](ia/prompts/CHANGELOG.md) |
| IA: fine-tuning LoRA (base × ajustado) | [`ia/finetuning/README.md`](ia/finetuning/README.md) |
| IA: código do serviço | [`ia/app.py`](ia/app.py) |
| **Segurança**: papéis, GRANT/DENY e RLS | [`sqlserver/01_schema_seed.sql`](sqlserver/01_schema_seed.sql), [`sqlserver/02_security_tests.sql`](sqlserver/02_security_tests.sql) |
| Segurança: mascaramento de dado sensível | [`sqlserver/07_mascaramento_parte2.sql`](sqlserver/07_mascaramento_parte2.sql) |
| Segurança: perfis e permissões da API | [`seguranca/permissoes-perfis.md`](seguranca/permissoes-perfis.md) |
| **Otimização**: carga de volume e consultas lentas | [`sqlserver/03_load_benchmark.sql`](sqlserver/03_load_benchmark.sql), [`sqlserver/05_benchmark_parte2.sql`](sqlserver/05_benchmark_parte2.sql), [`sqlserver/06_planos_parte2.sql`](sqlserver/06_planos_parte2.sql) |
| **Integração**: workflow do n8n | [`ia/n8n_workflow_academic_ai.json`](ia/n8n_workflow_academic_ai.json) |
| Integração: teste da IA sem permissão e com prompt injection | [`sqlserver/testar-ia-permissao.ps1`](sqlserver/testar-ia-permissao.ps1) |
| **Evidências** (resultados reais, planos `.sqlplan`, tempos, auditoria) | [`sqlserver/evidence/parte2/`](sqlserver/evidence/parte2/) |

## Como testar

1. **Instalar e subir o ambiente:** siga o **[Guia de instalação e execução](GUIA-INSTALACAO.md)** (Docker Desktop, sqlcmd, n8n e modelo local). Um único script configura tudo.
2. **Testar pelo Postman ou outro cliente HTTP:** veja a **[Referência dos endpoints](ENDPOINTS.md)**. A coleção pronta para importar está em [`postman/SIGp-academico.postman_collection.json`](postman/SIGp-academico.postman_collection.json).
3. **Rodar a demonstração completa pelo terminal**, na raiz do projeto:
   ```powershell
   pwsh -File docs/entrega-academica/demo-parte2.ps1
   ```
   Os 8 passos são: fluxo de ponta a ponta, casos de teste, GRANT/DENY, RLS e mascaramento, volume e consultas lentas, IA sem permissão e prompt injection, auditoria e perfis da API. Aperte Enter entre os passos.
   Para ver o workflow executando no editor do n8n, rode com `-VerNoN8n`.

## Resultados principais

Os números saem das evidências em `sqlserver/evidence/parte2/`.

| Tema | Resultado |
|---|---|
| Casos da IA | Decisão correta em 5/5. O modelo concordou em 3/5, e é por isso que ele não tem autoridade sobre a decisão. |
| Fine-tuning LoRA (20 casos de teste) | Acurácia 0,65 → 0,90; F1 macro 0,522 → 0,900 |
| Latência (Qwen 0.5B, CPU) | 305 ms em média (p95 381 ms) |
| Volume | 100.020 notas, 100.020 itens, 50.010 pagamentos |
| Consulta 2 | 33,1 → 16,4 ms; 4.954 → 7 leituras lógicas |
| IA sem permissão | Banco nega, API responde 503 e nenhum dado sai |
| Prompt injection | Classificação REVISAR, sem pagamento automático |

## Próxima etapa

Para a entrega final estão previstas:

- **Separação da interface web de teste.** O repositório de avaliação terá só o serviço acadêmico. A interface web pessoal sairá dele, para não haver dúvida de que a entrega não é um sistema web.
- **Empacotamento do serviço.** Um pacote único com SQL Server, API da IA, n8n e modelo local, instalado por um comando.
- **Alertas de vencimento com IA.** O n8n gera os alertas das contas e o modelo local redige um texto amigável. Uma checagem confere valor, data e localidade e, se o texto não bater, usa um modelo de texto fixo.
