# Arquitetura do SIGp, n8n e visão do SIG

## Estado atual

O projeto é um protótipo local composto por aplicações que ainda não estão todas integradas:

1. **Frontend SIGp** — `agencias.html` e `frontend/modules/`, servido localmente na porta `8000`. Implementado em HTML, CSS e JavaScript sem build/npm. O armazenamento do navegador mantém cache/migração de dados operacionais e as configurações locais de conexão; não é a fonte persistente.
2. **API SIGp** — `backend/app.py`, Flask + waitress no container `sigp_api` (porta `5001`, só em `127.0.0.1`; `http://api:5001` na rede Compose), com SQLite em `backend/data/sigp.db`. Fonte única de locais, estado operacional auxiliar, notas, pagamentos, faturas, conciliação 3 vias, correções auditadas, alertas e análises; envia eventos de conciliação ao n8n (`sigp-eventos`) com fila e reenvio.
3. **n8n** — container na porta `5678`, persistido no volume `n8n_data`. Recebe webhooks do SIGp e orquestra workflows; a aprovação operacional da conciliação não deve ser substituída por uma regra informal do workflow.
4. **OCR local** — container interno `ocr:5002`, baseado em Poppler e Tesseract (português/inglês). Processa PDFs enviados ao workflow e não publica a porta OCR no host.
5. **Painel legado de conciliação** — aplicação `buscador_nfse.py`, executada no container `sie` na porta `5000`, com banco separado `buscador_nfse.db`. Recebe eventos do workflow e oferece a interface `/sie`. Foi criado com o nome trocado: é um painel de conciliação, **não** o SIE (Sistema de Informação Executiva).

Abas gerenciais do SIGp:

- **SIG — Sistema de Informação Gerencial:** existe (primeira versão), lê `GET /api/sig/resumo`.
- **SIE — Sistema de Informação Executiva:** aba dedicada, com ciclos fechados (lançada + paga + fatura com `MATCH`) e análises gravadas pelo n8n.

O fluxo alvo de produção (API + webhook, Praxio/Globus) e o plano de ação estão em [`guia-fluxo-n8n.md`](guia-fluxo-n8n.md).

O contrato de eventos e documentos normalizados está em [`contrato-documentos.md`](contrato-documentos.md).

O roteiro de consolidação do SQLite, migração dos dados locais e futura instalação completa para Windows está em [`roteiro-instalacao-local.md`](roteiro-instalacao-local.md). Android permanece para uma fase posterior.

## Conceitos de domínio

- Agência, rodoviária e garagem são tipos de **local** e cada nota/fatura deve pertencer ao local correto.
- **Nota lançada** descreve a obrigação fiscal recebida; **nota paga** registra pagamento separadamente. Um teste simulado não representa confirmação bancária.
- **Conciliação** compara identidade fiscal, tipo/ID do local, valores pagos acumulados e serviços classificados tanto na nota lançada quanto na paga. Parcial é `PAGO_PARCIAL`; apenas igualdade integral e serviços revisados liberam `MATCH`. A condição não atesta confirmação bancária.
- **Fatura PDF** é um anexo opcional do local, possivelmente associado a uma nota lançada. Extração OCR sugere dados; revisão humana é necessária e o PDF não prova pagamento.
- **n8n** recebe/orquestra eventos e integrações. A validação e a persistência operacional pertencem ao SIGp/backend.

## Comunicação e persistência

O navegador acessa o backend SIGp por HTTP na porta `5001`. Os webhooks n8n são acessados no host por `127.0.0.1:5678`. Dentro da rede Docker, n8n chama o OCR por `http://ocr:5002` e o painel legado por `http://sie:5000`. A resolução `sie` é interna ao Compose; a página `/sie` é publicada no host em `127.0.0.1:5000`.

Há duas bases SQLite distintas:

- `backend/data/sigp.db`: fonte persistente dos cadastros, dados operacionais auxiliares, notas, pagamentos, conciliações e metadados de anexos no backend SIGp. PDFs ficam em `backend/data/faturas/`.
- `buscador_nfse.db`: estado do painel legado; o container `sie` monta esse arquivo do workspace.

O volume `n8n_data` mantém o estado do n8n. A interface carrega o estado operacional do SQLite antes de abrir e migra os cadastros/dados que só existam no navegador. URLs, chave de API e outras configurações de conexão não são copiadas para o banco. O conjunto ainda não tem uma estratégia automatizada de backup/restore nem sincronização universal entre os dois bancos.

O banco SIGp usa o journal rollback padrão do SQLite (`DELETE`), evitando arquivos WAL compartilhados ao montar o diretório de dados no host. Para abrir `sigp.db` diretamente em um editor SQLite, pare a API antes e feche o editor antes de iniciar o SIGp novamente; não mantenha dois processos escrevendo no mesmo arquivo.

O endpoint `/api/health` consulta o catálogo SQLite e retorna HTTP 503 se a consulta falhar; portanto, o estado saudável do container também confirma acesso efetivo ao banco.

## Aba SIG integrada ao SIGp

Foi implementada uma primeira aba **SIG — Sistema de Informação Gerencial** dentro da navegação do próprio SIGp. O endpoint `GET /api/sig/resumo` lê as tabelas operacionais do banco `sigp.db`; não depende da cópia no banco legado.

A versão inicial apresenta valor lançado, pagamentos no período, saldo pendente, vencidas, conciliações `MATCH`, divergências, evolução mensal e valores por provedor/local, com filtros por período, tipo de local, provedor e status. Grupos com chave fiscal duplicada são excluídos dos valores para evitar dupla contagem e sinalizados para revisão; os registros fonte não são alterados.

Melhorias seguintes: validar definições financeiras com o usuário, incluir drill-down dos indicadores até seus documentos e expandir testes de datas ausentes, filtros e pagamentos em múltiplos períodos.

A tela `/sie` continua como painel legado; “SIE” permanece em nomes técnicos e eventos existentes até uma migração coordenada. Não remover o serviço/banco legado antes de definir migração e retenção dos dados.

## Segurança e implantação

As portas web publicadas no Compose estão limitadas a `127.0.0.1`; o OCR permanece apenas na rede interna. O backend e o painel legado ainda usam o servidor de desenvolvimento Flask (`debug=True`), e há CORS amplo no backend. Não expor os serviços à rede pública sem autenticação, configuração de CORS, servidor de produção, tratamento de segredos e backups.

## Evolução recomendada

1. Reconciliar o vínculo do PDF de teste com o local e a nota corretos; melhorar parser/OCR, mantendo revisão humana.
2. Adicionar testes automatizados para API, normalização, faturas, conciliação e contratos de workflows.
3. Consolidar a fonte gerencial e implementar a aba SIG dentro do SIGp com definições de métricas aprovadas.
4. Tratar idempotência, duplicidades, pagamentos parciais, cancelamentos, falhas/reenvios e observabilidade.
5. Definir backup/restore dos bancos, anexos e volume n8n; preparar segurança e implantação antes de sair do ambiente local.
