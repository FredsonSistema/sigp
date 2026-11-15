# Roteiro — SIGp local, independente e instalável

## Objetivo e decisões confirmadas

- A instalação inicial será **local, completa e para Windows**, incluindo SIGp, API, Docker, SQLite, OCR e n8n.
- O n8n é componente obrigatório da instalação. Os workflows padrão do SIGp devem ser provisionados junto com o sistema.
- Credenciais e URLs de integrações externas (por exemplo, Praxio/Globus, IA e notificações) podem ficar sem configuração; isso não deve impedir o uso dos fluxos locais básicos.
- Persistência de dados de negócio em banco local é obrigatória. SQLite é a opção inicial; não depender de `localStorage` como fonte de dados.
- O banco também é parte do desenvolvimento: algoritmo, SQL, segurança, desempenho e consumo de recursos serão exercitados contra SQLite real em bases de teste isoladas.
- Um instalador Android fica para uma etapa futura, depois da estabilização da API e do modelo de dados. Não faz parte desta entrega.
- Este documento mantém o roteiro da instalação. A API SIGp já usa SQLite como persistência operacional; a criação do instalador Windows e o provisionamento automatizado continuam pendentes.

### SQLite no Docker e nos testes

SQLite não precisa de um servidor ou container separado: a biblioteca SQLite é usada pela API dentro do container `api`. O arquivo `.db` fica em armazenamento persistente montado pelo Docker no host, para sobreviver à recriação/atualização do container e permitir backup. A instalação deve criar e validar esse armazenamento automaticamente; não solicitar ao usuário instalar ou configurar SQLite separadamente.

O desenvolvimento e os testes devem usar o mesmo mecanismo SQLite, mas **nunca o banco operacional**:

- Testes automatizados criam bancos temporários, aplicam o esquema/migrações e removem os arquivos ao final.
- Testes de integração executam API + SQLite em containers, com banco e arquivos de teste separados dos dados locais reais.
- Um gerador de dados sintéticos cria cenários pequenos e grandes, incluindo duplicidades, pagamentos parciais, múltiplos provedores, faturas ausentes e dados inválidos. Não usar dados pessoais/fiscais reais em benchmarks.
- Benchmarks registram consulta/operação, volume e distribuição dos dados, plano (`EXPLAIN QUERY PLAN`), latência (incluindo percentis), throughput, uso de CPU/memória e tamanho do banco. Repetir para comparar algoritmos/índices antes e depois.
- Testes de segurança verificam parametrização das consultas, validação/autorização dos endpoints, isolamento dos arquivos, permissões e exposição de segredos. Os resultados e os comandos devem ser reproduzíveis.
- As metas de latência, volume, concorrência e espaço serão definidas depois de medir uma linha de base representativa; não declarar desempenho aceitável sem essa medição.

O primeiro alvo é SQLite em modo local/monousuário. Se os testes demonstrarem necessidade de escrita concorrente intensa ou acesso multiusuário remoto, registrar os dados medidos e avaliar um banco servidor como decisão arquitetural separada; não adicionar essa dependência por antecipação.

## Estado atual observado

- `backend/data/sigp.db`: SQLite operacional da API para locais sincronizados, notas, pagamentos, conciliações, faturas, auditoria e análises.
- `backend/data/faturas/`: PDFs armazenados pela API, separados do banco.
- `buscador_nfse.db`: segundo SQLite, usado pelo painel legado `/sie` e pela auditoria da tomada de decisão.
- `n8n_data`: volume Docker separado para estado, credenciais, execuções e workflows publicados do n8n.
- Os cadastros e os dados operacionais auxiliares são carregados/persistidos pelo SQLite; o navegador mantém cache e configurações locais de conexão.
- O `docker-compose.yml` já reúne os serviços locais `web`, `api`, `n8n`, `ocr` e `sie`. Os scripts Windows atuais iniciam o Compose, mas ainda não constituem um instalador.
- A implantação depende do Docker Desktop/WSL2. Os workflows versionados podem ser importados, mas segredos, credenciais e URLs externas precisam de configuração própria.

## Arquitetura-alvo proposta

1. **Um banco SQLite canônico para os dados do SIGp**: registros de negócio, auditoria e decisões deixam de depender do navegador ou do banco legado.
2. **Migração auditável dos dados existentes**: inventariar as tabelas e chaves dos dois bancos, importar os dados legados sem sobrescrever silenciosamente conflitos, validar totais e vínculos e manter cópia de segurança antes de arquivar o banco legado.
3. **Arquivos junto com os dados**: PDFs e demais anexos permanecem em diretório persistente da instalação, com referências transacionais no banco e backup coordenado.
4. **Estado próprio do n8n preservado**: `n8n_data` continua separado, pois contém configuração e credenciais da automação, não substituindo o banco do SIGp.
5. **Docker Compose como runtime local**: o instalador administra o conjunto local e seus diagnósticos. O Docker Desktop/WSL2 será validado como pré-requisito; instalação ou atualização automática desse runtime só deve ocorrer com consentimento explícito.
6. **Camada Android posterior**: o cliente móvel consumirá a API; não abrirá nem compartilhará diretamente o arquivo SQLite do computador.

## Fases e critérios de conclusão

### Fase 0 — Bancada de desenvolvimento e validação de banco

- Criar uma configuração de teste isolada que use SQLite real em arquivo temporário ou em volume de teste dedicado, sem apontar para `backend/data/sigp.db`, `buscador_nfse.db` ou `n8n_data`.
- Padronizar testes unitários e de integração de schema/migrações, algoritmos de conciliação, consistência transacional, consultas e índices.
- Criar dados sintéticos determinísticos em volumes escalonados, com cenários representativos e casos de borda.
- Adicionar uma rotina reproduzível de benchmark SQL e algoritmos que guarde resultados comparáveis e planos de consulta.
- Definir revisão de segurança para queries parametrizadas, validação de entrada, autenticação/autorização da API, isolamento de testes e retenção de logs.
- Medir e publicar uma linha de base de latência, CPU, memória, tamanho e throughput; estabelecer metas somente com os resultados e o volume esperado de uso local.

**Concluída quando:** os testes nunca alteram dados operacionais; uma única rotina reproduz cenários funcionais, de segurança e desempenho; as consultas críticas têm plano de execução revisado; resultados de referência podem ser comparados entre versões.

### Fase 1 — Tornar a persistência em banco obrigatória

- Inventariar todas as chaves de `localStorage`, cookies e arquivos que guardam dados de negócio, configurações e referências.
- Definir o modelo SQLite canônico, constraints, índices, transações, política de migração de esquema e tratamento de concorrência.
- Usar a bancada da Fase 0 para validar migrações, constraints, índices e alterações na lógica de conciliação antes de aplicá-las aos dados locais.
- Mover a leitura/escrita dos dados de negócio para endpoints da API. Manter no navegador somente estado temporário de interface ou cache reconstruível.
- Especificar a importação de `buscador_nfse.db`, preservando decisões, histórico, IDs, anexos e conflitos para revisão.
- Definir exportação, backup e restauração consistentes entre banco e PDFs; documentar como o volume do n8n é copiado separadamente.

**Concluída quando:** uma instalação limpa persiste todos os cadastros e operações no SQLite; trocar de navegador ou perfil não perde dados; a migração e a restauração passam por testes sem duplicar nem descartar registros.

### Fase 2 — Instalação local completa e reprodutível

- Manter `docker compose` como definição única dos serviços e documentar portas, volumes, dependências e ordem de saúde.
- Provisionar workflows padrão de forma repetível e segura, sem criar cópias duplicadas e sem sobrescrever credenciais existentes.
- Separar configuração obrigatória do ambiente local da configuração opcional de integrações externas; nunca embutir segredos nos JSONs ou no instalador.
- Disponibilizar telas/diagnósticos para estado do Docker, containers, SQLite, diretório de anexos, n8n, workflows ativos e webhooks.
- Garantir que o sistema funcione localmente sem credenciais externas: recursos que dependem delas devem informar indisponibilidade/configuração pendente, não falhar silenciosamente.

**Concluída quando:** iniciar ou reiniciar o conjunto preserva dados; os workflows padrão estão disponíveis; serviços básicos e webhooks locais passam nos testes sem internet ou credenciais de terceiros, exceto para baixar imagens na primeira instalação.

### Fase 3 — Instalador Windows

- Escolher a tecnologia do instalador após validar atualização, assinatura, permissões, caminhos com espaços e recuperação de falhas.
- Fazer pré-verificação de Windows, Docker Desktop/WSL2, espaço em disco e portas; mostrar instruções claras quando um pré-requisito faltar.
- Instalar os arquivos do SIGp e criar diretórios persistentes fora da área temporária do instalador.
- Criar atalhos para iniciar, abrir, parar, verificar saúde, consultar logs e abrir a configuração n8n.
- Oferecer atualização sem apagar banco, anexos, credenciais ou workflows customizados; desinstalação deve preservar dados por padrão e explicar remoção opcional.

**Concluída quando:** uma pessoa sem ferramentas de desenvolvimento instala, inicia e atualiza o SIGp em Windows suportado, e uma desinstalação/reinstalação mantém os dados se essa opção for escolhida.

### Fase 4 — Preparar o cliente Android (futuro)

- Estabilizar e versionar os contratos da API.
- Definir autenticação, permissões, uso em rede local, sincronização, conflitos e comportamento quando o computador/servidor estiver desligado.
- Só então escolher entre aplicação móvel nativa, PWA ou outra tecnologia e implementar o cliente Android.

**Fora do escopo atual:** publicar o app móvel, expor o servidor à internet ou habilitar acesso multiusuário sem decisão de segurança e autenticação.

## Testes de aceitação para instalação e migração

- SQLite inicializado pela API no container, com persistência após recriar o container e sem instalação/configuração manual de um servidor SQLite.
- Testes e benchmarks executados em base isolada; nenhum comando de teste aponta para os dados operacionais.
- Relatório reproduzível de consultas, planos, latência, throughput e recursos para volumes sintéticos documentados.
- Verificações de segurança de banco/API aprovadas e sem dados sensíveis nos artefatos de teste.
- Instalação limpa, primeiro início, parada e reinício do Windows.
- Migração dos bancos e cadastros atuais com relatório de contagens, conflitos e itens sem vínculo.
- Persistência após trocar de perfil do navegador e reiniciar os containers.
- Backup e restauração de SQLite + PDFs; recuperação separada do estado n8n.
- Workflows padrão importados uma única vez e endpoints/webhooks validados.
- Modo sem credenciais externas e mensagens claras de recursos opcionais indisponíveis.
- Atualização do instalador preservando dados e configuração local.
- Remoção/reinstalação com escolha explícita de manter ou apagar os dados.
