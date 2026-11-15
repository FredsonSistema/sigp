# READMEKIRO — Visão consolidada do SIGp

Resumo analítico feito a partir de todos os README do projeto. Não substitui os originais: aponta onde cada assunto está, o estado real de cada parte e o que está inconsistente ou desatualizado na documentação.

## 1. README encontrados

| Arquivo | Assunto | Observação |
|---|---|---|
| `README.md` | Documento principal: visão, instalação, Docker, n8n, pendências | 37 KB, o mais completo, mas mistura guia, histórico de testes e backlog |
| `backend/README.md` | API Flask: responsabilidades, endpoints, status, configuração | Referência de rotas |
| `n8n/wf08/README.md` | WF-08: importação de faturas do Gmail com IA local (Qwen/Ollama) | Fonte do JSON do workflow |
| `docs/entrega-academica/README.md` | Entrega acadêmica (IA, Segurança e Otimização de BD) | Sobre grupo, MVP, riscos e PDFs |
| `docs/entrega-academica/sqlserver/README.md` | SQL Server acadêmico, RLS, RAG, benchmark | Dados só sintéticos |
| `docs/entrega-academica/ia/finetuning/README.md` | Experimento LoRA e integração com a API acadêmica | Resultados exploratórios |
| `docs/entrega-academica/ia/finetuning/output/qwen2.5-0.5b-lora/README.md` | Model card gerado pela biblioteca PEFT | Template vazio (`[More Information Needed]`) |

Fora de escopo (bibliotecas de terceiros): `.venv`, `.venv-1`, `.pytest_cache`.

## 2. O que é o sistema

O SIGp é um protótipo local para gestão de agências, rodoviárias e garagens, com notas fiscais de provedores de internet, faturas em PDF e conciliação em três vias (nota lançada, nota paga e fatura). O n8n orquestra a entrada de documentos, a IA e as notificações. A decisão final é sempre humana: nada autoriza pagamento automaticamente.

### Componentes

| Componente | Tecnologia | Porta | Papel |
|---|---|---|---|
| Frontend (`agencias.html`) | HTML/JS, servido por `http.server` no Windows | 8000 | Interface; `localStorage` como cache |
| API SIGp (`sigp_api`) | Flask + waitress, SQLite `backend/data/sigp.db` | 5001 (loopback) | Fonte única dos dados operacionais, conciliação, alertas, SIG e SIE |
| n8n (`sigp_n8n`) | n8n, volume `n8n_data` | 5678 (loopback) | Workflows WF-01 a WF-08 e WF-99 |
| OCR (`sigp_fatura_ocr`) | Poppler + Tesseract (pt/en) | 5002 (só rede Docker) | Extração de texto de PDFs |
| Painel legado (`sigp_sie`) | `buscador_nfse.py`, `buscador_nfse.db` | 5000 (loopback) | Conciliação legada em `/sie`; não é o SIE executivo |
| Stack acadêmica | SQL Server, API RAG, Ollama/Qwen, LoRA | 14333 (SQL) | Isolada, dados sintéticos |

Há dois bancos SQLite distintos (`sigp.db` e `buscador_nfse.db`) que não são sincronizados automaticamente.

### Status de conciliação

`PENDENTE` → `PAGO_PARCIAL` → `AGUARDANDO_FATURA` → `MATCH`, com `DIVERGENCIA` quando algo não bate. `MATCH` exige fatura, a menos que `SIGP_EXIGIR_FATURA=0`.

### Camadas gerenciais

- **SIG:** aba gerencial (notas, pagamentos, pendências, divergências). Falta drill-down.
- **SIE:** aba executiva, só com ciclos fechados (`MATCH`).
- **`/sie` legado:** painel de conciliação com nome trocado; será desativado.

## 3. Workflows n8n

| ID | Função | Estado informado |
|---|---|---|
| WF-01 | Receber nota lançada | Publicado e testado |
| WF-02 | Receber nota paga | Publicado e testado |
| WF-03 | Extrair fatura PDF (OCR) | Publicado e testado |
| WF-05 | Eventos da API: IA, SIG, SIE, notificações | Ativo; parecer Qwen/RAG experimental |
| WF-06 | Vencimentos diários e reenvio de eventos | Publicado; notificações desativadas |
| WF-07 | Tomada de decisão manual | Publicado e ativo |
| WF-08 | Faturas do Gmail com IA local | Gerado de `n8n/wf08/`; importado inativo, a ativar após revisão |
| WF-99 | Erros | Publicado |

Gmail, Telegram e WhatsApp seguem desativados até haver credenciais e destinatários.

## 4. Como rodar

1. Pré-requisitos: Windows, Docker Desktop (WSL 2), Python 3.14 para o `.venv-1`.
2. Copie `.env.example` para `.env` e defina ao menos `SIGP_API_KEY`.
3. Duplo clique em `instalarsigp.bat` (instala e abre sistema e n8n) ou em `Iniciar SIGp.bat`. Para parar: `Parar SIGp.bat`.
4. Manual: `docker compose up -d --build` e `.\.venv-1\Scripts\python.exe -m http.server 8000 --bind 127.0.0.1`.
5. URLs: `http://127.0.0.1:8000/agencias.html`, `http://127.0.0.1:5678`, `http://127.0.0.1:5001/api/health`.
6. Testes: `.\.venv-1\Scripts\python.exe -m unittest discover -s tests`.

Cuidados:

- Não abra `agencias.html` por `file:///`.
- Não use `docker compose down -v`: apaga o volume do n8n.
- O estado do n8n não vem no repositório. Em outro PC, importe os JSONs `n8n_workflow_*.json` ou restaure `n8n_data`.
- Para levar os dados, copie `backend/data/` e `buscador_nfse.db` com os containers parados.

## 5. Estado das partes

### Funcionando segundo a documentação

- Cadastro de locais, importação de XML/JSON, nota lançada e paga, conciliação 3 vias, correção manual auditada.
- Faturas PDF com OCR local, extração assistiva e revisão manual.
- Eventos API → n8n com fila e reenvio; análises gravadas no SIG/SIE.
- 29 testes automatizados e 13/13 no teste ponta a ponta pelo n8n (09/10/2026).
- WF-08: primeiro lote real de 20 e-mails e 26 PDFs, com 17 PDFs em "Aguardando associação" e 9 em "Revisão".

### Limitações declaradas

- OCR e parser erram emissor, número, CNPJ e data de emissão; a revisão humana é obrigatória.
- SQLite serve apenas ao uso local monousuário; não há estratégia de backup, monitoramento ou produção.
- Duplicidades históricas de chave fiscal ficam fora dos indicadores do SIG até revisão manual.
- WF-08 é lento em CPU (cerca de 58 s por PDF) e processa um PDF por vez.
- Sem integração Praxio/Globus/NS Docs, SEFAZ ou confirmação bancária, e sem PostgreSQL.
- A IA acadêmica usa corpus fictício. Os resultados de LoRA (macro-F1 0,522 → 0,900) vêm de 20 exemplos sintéticos com cenários repetidos entre partições, então são exploratórios.

### Pendências principais

- Reimportar dados reais após limpar a base de teste.
- Tela de correção manual na interface (a API `PATCH` já existe).
- Drill-down no SIG e validação das regras de saldo e pagamento parcial.
- Ampliar testes para normalização XML/JSON e casos-limite.
- Segurança antes de expor fora da máquina: `SIGP_API_KEY`, Header Auth nos webhooks, HTTPS e usuários.
- Preencher dados da entrega acadêmica: grupo, matrículas e URL do repositório.

## 6. Inconsistências e pontos desatualizados

Encontrados ao cruzar os README:

1. **Adaptador LoRA integrado ou não?** `docs/entrega-academica/README.md` e `sqlserver/README.md` dizem que o adaptador não está integrado ao serviço. `ia/finetuning/README.md` descreve um `integrate-lora.ps1` que o integra, e há evidência `ai-test-results-lora.json`. Convém unificar o texto: "integração experimental opcional, não autoritativa".
2. **Árvore do repositório desatualizada** no `README.md`: não lista `n8n/wf08/`, `docs/entrega-academica/` nem os workflows WF-01/02/05/06/07/08/99.
3. **WF-07 e WF-08 ausentes de trechos do README principal.** A tabela de webhooks traz o WF-07, mas a lista de workflows da seção de instalação cita só WF-01/02/03/05/06. O WF-08 só está documentado em `n8n/wf08/README.md`. O comando de importação em lote também não publica WF-07 nem WF-08.
4. **Ambiente virtual.** O `README.md` diz que o `.venv` antigo foi excluído e usa `.venv-1`. O `sqlserver/README.md` ainda executa `.\.venv\Scripts\python.exe`. A pasta `.venv` existe no disco, então vale confirmar qual está válido.
5. **Versão do Python.** O host usa 3.14 e os containers usam 3.12-slim. Não é erro, mas só aparece de forma dispersa.
6. **Histórico misturado com guia.** O `README.md` traz verificações datadas (12/12 testes, depois 29/29), correções de bugs e anotações sobre registros específicos (nota 88468, local `a_muxd1bz4qek1t`). Isso caberia melhor num changelog ou no checklist.
7. **Frases já obsoletas.** "Repositório Git próprio… sem commit ainda" e "Nome trocado do SIE" repetido várias vezes. Vale revisar.
8. **Campos de formato de data.** Há datas como 09/10/2026 e 10/11/2026 sem indicar dd/mm; o contexto sugere dd/mm/aaaa.
9. **Model card do LoRA** é só o template da biblioteca. Pode ser preenchido ou removido.
10. **`backend/README.md`** não lista nenhuma rota do WF-07 (decisões manuais) nem da tela `/sig` na porta 5000. Não verifiquei o código para saber onde elas ficam.

## 7. Sugestões

- Dividir o `README.md` em: guia rápido (instalar e rodar), arquitetura, e histórico/backlog (movendo as verificações datadas para o checklist).
- Criar um índice único de workflows com ID, arquivo, gatilho e estado, incluindo WF-07 e WF-08.
- Atualizar a árvore de pastas e corrigir o caminho do venv no `sqlserver/README.md`.
- Alinhar as três descrições do estado do LoRA.

## 8. Escopo desta análise

Li os sete README e consolidei o conteúdo. Não executei o sistema, os testes nem os containers, e não verifiquei o código-fonte. Os estados "publicado", "testado" e "ativo" são os declarados nos próprios README, não confirmados por mim.
