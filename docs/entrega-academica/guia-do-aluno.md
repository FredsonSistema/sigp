# Guia do aluno — SIGp: IA, banco de dados e segurança

**Revisão do estado do projeto em 02/11/2026.** Este guia separa evidência executada de trabalho pendente. Não é parecer jurídico nem afirmação de que os requisitos acadêmicos foram todos concluídos.

## Resumo em um minuto

O SIGp operacional continua com SQLite e não foi migrado. Em paralelo, o protótipo acadêmico SQL Server está instalado em Docker com RLS, papéis testados e mais de 100 mil linhas sintéticas. A API acadêmica consulta somente o escopo autorizado, recupera documentos por busca lexical e chama Qwen2.5 0.5B local. Isso não usa embeddings nem Qdrant.

Nos cinco casos sintéticos da API, as regras determinísticas e verificações de segurança passaram **5/5**; o Qwen quantizado concordou em **3/5**. Separadamente, foi executado LoRA CPU do Qwen2.5 0.5B: no teste sintético reservado, a macro-F1 passou de **0,522 para 0,900** (20 casos). É um resultado exploratório, com exemplos de famílias repetidas entre partições, e não mede a API nem comprova generalização. O adaptador não foi integrado ao serviço. A latência da API foi de 4,84 a 32,43 segundos; amostra pequena, não p95. O workflow acadêmico foi importado no n8n, mas está inativo; o teste foi direto na API, não ponta a ponta pelo n8n.

**Limites:** nenhuma análise autoriza pagamento. A classificação final vem de regras com afirmações estruturadas dos documentos; o LLM só retorna uma classificação experimental e não pode alterá-la. Dados e documentos são fictícios. A identidade registrada é do serviço de demonstração, não de uma pessoa autenticada.

## 1. O que existe e o que ainda não foi comprovado

| Item | Estado observado | O que não se deve afirmar |
|---|---|---|
| SIGp operacional | SQLite continua separado; não houve migração. | SQL Server acadêmico não substitui nem sincroniza com o sistema operacional. |
| SQL Server acadêmico | RLS, usuários de teste e permissões executados; script de segurança retorna `PASS`. | Somente dados sintéticos; não é banco de produção. |
| Volume | 100.020 notas, 100.020 itens, 50.010 pagamentos e 100.020 conciliações. | Não há carga de um milhão de eventos de auditoria. |
| RAG | 20 documentos fictícios, busca lexical escopada e IDs de fontes registrados. | Sem embeddings, Qdrant ou busca vetorial. |
| LLM | Qwen2.5 0.5B via Ollama local; classificação experimental medida. | 3/5 de concordância; não usar sua resposta como decisão operacional. |
| n8n | Workflow acadêmico importado. | Inativo; webhook não validado ponta a ponta. |
| Fine-tuning LoRA | Executado em CPU: 80 treino, 20 validação, 20 teste; macro-F1 de 0,522 para 0,900 no teste sintético. | Amostra pequena e cenários repetidos entre divisões; não integrado à API, não prova generalização nem prontidão. |
| Desempenho | Dois planos e uma medição inicial preservados. | Sem baseline sem índices, repetição/p95; não alegar otimização concluída. |
| Testes | 9 testes unitários da API passam; avaliação real 5/5 nas regras/segurança e 3/5 em concordância do LLM. | Testes unitários não certificam qualidade estatística do modelo. |
| Entrega acadêmica | Existem documentos e PDFs das partes, mas grupo/matrículas/link ainda precisam ser conferidos. | Que a aplicação web atende a regra da atividade que exclui web app/site. |

O SIGp pode ser apresentado como **contexto do problema**, mas a demonstração acadêmica deve respeitar a restrição de não entregar um site/aplicação web. Prefiram CLI/API sem tela ou fluxo n8n, se o professor confirmar que essa forma é aceita. Não escondam a existência da interface web; expliquem que ela não será o artefato entregue para a atividade.

## 2. Banco de dados: o que escolher e por quê

- **SQLite:** banco operacional local do SIGp atual; simples, embutido e adequado ao funcionamento de uma instalação local de um usuário/instância.
- **SQL Server:** escolha já preparada pelo script da atividade de Segurança/Otimização. Use uma instância de desenvolvimento separada, com dados fictícios, para provar modelo, permissões e consultas.
- **Qdrant:** banco vetorial proposto para recuperar trechos de documentos no RAG; não substitui o SQL transacional.
- **MongoDB:** não é necessário para esse MVP. Adicionar um segundo banco aumenta trabalho, superfície de segurança e duplicação sem requisito funcional claro.

**Decisão recomendada:** mantenha SQLite para o SIGp atual e SQL Server como protótipo acadêmico isolado. Não faça migração até definir requisitos de instalação, backup, concorrência, suporte e operação. A atividade permite SQL Server, MongoDB ou ambos; um SQL Server executado e testado é mais defensável que dois bancos apenas desenhados.

### Segurança e desempenho SQL observados

- A API usa procedures autorizadas e não lê diretamente as tabelas/views; o contexto respeita `LOC-001` e provedor fixo.
- O teste SQL registra `PASS`: 50 linhas do local autorizado e negação de leitura direta, acesso cruzado, `DELETE` pela role da API e principal sem role.
- A auditoria registra principal SQL, local, provedor, correlation ID, quantidade e fontes; o ator de negócio é um identificador fixo de demonstração, não uma identidade humana autenticada.
- Os planos/estatísticas das duas consultas foram capturados. Medição inicial: aproximadamente 3.277 leituras lógicas em `Notas` por consulta e 528 em `Conciliacoes` para a busca de pendências; uma execução observou cerca de 46 ms e 25 ms.
- Não há baseline antes dos índices, amostras repetidas nem p95. Esses números são uma observação inicial, não prova de otimização ou de que a consulta era lenta.

## 3. XML, PDFs e LGPD

Um XML de NFS-e pode conter CNPJ/CPF, nome, endereço, e-mail, descrição do serviço, valores e identificadores fiscais. A composição varia conforme o município e o provedor. Um CNPJ de pessoa jurídica não é automaticamente dado pessoal, mas dados que identifiquem empresário individual ou pessoa natural podem ser pessoais. Nome, CPF, endereço e contato de uma pessoa natural são exemplos de dados pessoais.

Valor financeiro ou nota fiscal **não é automaticamente “dado pessoal sensível” na definição específica da LGPD**. Ainda assim, o grupo deve classificá-los como internos/restritos porque podem causar dano ou revelar atividade financeira. A LGPD também exige finalidade, necessidade, segurança e prestação de contas; dados publicamente acessíveis não ficam automaticamente fora dessas obrigações.

### Regras práticas para o protótipo

- Use nomes, CNPJs, CPFs, endereços, valores e documentos fictícios; não copie XML real para o repositório, issue, prompt ou PDF.
- Guarde os arquivos de teste em diretório controlado, defina retenção e elimine cópias temporárias e backups de acordo com o plano do grupo.
- Para logs, prefira ID de correlação, tipo de evento, resultado e IDs fictícios; nunca registre chave fiscal completa, senha, token ou payload integral.
- Antes de enviar dados reais a serviço de LLM/OCR externo, o controlador da organização deve avaliar finalidade e base legal, necessidade, contrato com operador, localização/transferência internacional, retenção, acesso e controles de segurança. Consentimento não é a única base legal possível; a decisão é da organização, não do protótipo.
- Se a ferramenta ficar local, isso reduz a saída de dados, mas não elimina risco de malware, acesso local, backup exposto ou credenciais inseguras.
- Não use este guia como aconselhamento jurídico. A organização e seu encarregado/jurídico devem validar o uso de dados reais.

## 4. Segurança: evidências e limites

O serviço acadêmico exige uma chave de API, escopo local configurado no servidor e credencial SQL de privilégio mínimo. O SQL Server aplica RLS e a API consulta contexto por procedure autorizada. Os testes SQL negaram leitura direta, acesso a outro local, `DELETE` pela role da API e execução por principal sem role. O teste de prompt injection também retornou `REVISAR` sem acionar pagamento.

A chave e o SQL Server acadêmicos são separados do sistema operacional. As portas acadêmicas estão ligadas a `127.0.0.1`, mas isso não substitui autenticação adequada se o serviço for exposto a outros usuários ou máquinas. O SIGp operacional mantém seu próprio modelo de autenticação.

**Limite importante de auditoria:** `n8n-demo` é um identificador fixo de serviço. Ainda não há autenticação humana integrada; não alegar que a trilha identifica qual colaborador pediu a análise. A chamada SQL usa identidade técnica e registra principal, escopo e correlation ID.

| Prova executada | Resultado |
|---|---|
| Leitura de contexto autorizado | 50 linhas do `LOC-001` permitidas. |
| Leitura direta de tabela/view protegida | Negada. |
| Solicitação de contexto para `LOC-002` | Negada. |
| `DELETE` pela identidade da API e execução por principal sem role | Negadas. |
| Prompt injection sintético | `REVISAR`, nenhum pagamento automático. |
| Cinco casos reais | 5/5 decisões de regra e verificações de segurança corretas; o LLM concordou em 3/5. |

O relatório detalhado é `sqlserver/evidence/security-tests.txt`; o resultado de modelo é `sqlserver/evidence/ai-test-results.json`. Ambos usam dados fictícios.

## 5. LLM: escolha, custo e resultado observado

O endpoint usa **Qwen2.5 0.5B quantizado via Ollama em CPU local**. O experimento LoRA foi feito separadamente sobre o checkpoint Hugging Face não quantizado em float32. Não há tarifa por token de API; isso não significa custo total zero. Ainda não medimos consumo elétrico, então não há estimativa honesta de reais por 1.000 usos. A latência observada nos cinco casos da API foi de 4,84 a 32,43 segundos; a amostra é pequena e não é um p95 confiável.

O sistema calcula a decisão por regras estruturadas e compara a classificação do LLM, sem deixar o modelo substituir o resultado. O Qwen concordou em 3 dos 5 casos, falhando nos dois casos que exigiam reconhecer um contrato válido ou uma exclusão explícita. É resultado preliminar negativo de qualidade, não motivo para afirmar que o modelo está pronto. Resumo livre foi removido após o modelo inventar uma afirmação numérica.

Para estimar custo local por 1.000 usos, medir potência média durante a inferência e aplicar: `potência em kW × segundos por uso × 1.000 / 3.600 × tarifa por kWh`. Somar custo de hardware, manutenção e operação separadamente. API externa não foi usada nem comparada; consultar preços oficiais na data da apresentação e usar somente dados sintéticos nesse teste.

## 6. RAG, testes e fine-tuning

**RAG implementado:** 20 documentos fictícios em JSON e busca lexical/BM25 com filtro por local/provedor, retornando até cinco fontes. Não há chunking semântico, embeddings ou Qdrant. Os documentos têm campos estruturados de serviço, valor e exclusões para permitir regras auditáveis. A busca foi testada para não devolver textos de outra localidade.

**Fine-tuning LoRA executado:** 120 exemplos sintéticos (80/20/20), Qwen2.5-0.5B-Instruct em CPU, 1 época; adaptador e resultados em `ia/finetuning/`. Na partição teste de 20 exemplos, acurácia/macro-F1 passaram de 65%/0,522 para 90%/0,900. Contudo, famílias de serviço e templates repetem-se entre treino, validação e teste; essa métrica é exploratória e precisa de validação com novos serviços/casos independentes. O adaptador não foi plugado na API. Fine-tuning não atualiza fatos contratuais, que devem vir de fontes atuais do SQL/RAG.

### Avaliação já executada e próximos ensaios

1. Há cinco casos rotulados com contratado, divergente, revisão, injection e provedor desconhecido.
2. As regras produziram as cinco classes esperadas e passaram as verificações de escopo/fontes/pagamento (5/5); o LLM concordou em 3/5. Uma amostra de cinco não permite alegações estatísticas amplas.
3. O runner registra classificação esperada/obtida, IDs recuperados, modelo, hash/versão de prompt e latência. O LLM não controla fontes nem decisão final.
4. OCR não foi avaliado como parte desses cinco casos: entrada foi JSON sintético manual, portanto não afirmar acurácia de extração.
5. Próximo teste: melhorar/selecionar modelo, ampliar conjunto separado e medir matriz de confusão; avaliar recuperação top-5 e testar pelo webhook n8n.
6. Repetir a avaliação do adaptador com exemplos independentes por serviço/provedor, medir latência/energia e só então decidir se vale integrar; não usar as métricas sintéticas como alegação de prontidão.
7. Segurança: nenhuma decisão paga ou grava por ação do modelo; dúvida/injection segue para revisão.

## 7. O que falta fazer — ordem recomendada

### O que falta para a próxima entrega

- [ ] Completar grupo, nomes completos, matrículas e link público do repositório; confirmar que não há segredos ou documentos reais no histórico Git.
- [ ] Resolver a regra “não vale web app/site”: alinhar com docente a demonstração via CLI/API/n8n; não apresentar o site como produto entregue.
- [x] Executar SQL Server local com dados sintéticos e preservar evidência de segurança.
- [x] Criar RLS e testar permissões mínimas, bloqueio de acesso cruzado e `DENY`.
- [x] Criar corpus de 20 documentos e busca lexical local com filtro de local/provedor.
- [x] Executar cinco casos reais no serviço; documentar decisão 5/5, concordância LLM 3/5 e latência.
- [ ] Ativar workflow n8n após autenticar na interface e validar webhook ponta a ponta.
- [ ] Melhorar ou substituir o modelo local e repetir avaliação; manter a regra determinística como autoridade.
- [ ] Comparar desempenho antes/depois de índices com várias repetições, mediana/p95 e volume registrado.
- [ ] Medir energia/custo local; não inventar custo por mil usos.
- [x] Executar experimento LoRA preliminar em CPU e preservar dataset, adaptador e métricas; manter integração e validação independente pendentes.
- [ ] Completar grupo, nomes completos, matrículas e link público; confirmar com docente se demonstração API/n8n atende à regra da disciplina.

### Apresentação curta (5 minutos)

1. **0:00–0:45:** problema, usuário, entrada e saída.
2. **0:45–1:30:** arquitetura real demonstrada, banco, fluxo n8n e fronteiras de segurança.
3. **1:30–2:30:** importar um conjunto fictício e mostrar registro/conciliação.
4. **2:30–3:30:** evidência de consulta ou teste de permissão/ataque bloqueado.
5. **3:30–4:30:** métricas medidas, custo estimado e limitações.
6. **4:30–5:00:** próximos passos e distinção entre feito, em andamento e futuro.

## 8. Perguntas que cada integrante deve saber responder

- **Por que SQL Server e SQLite?** SQLite continua no SIGp operacional; SQL Server é um protótipo acadêmico isolado para atender e testar a parte de banco. Não são duas bases sincronizadas.
- **Por que não MongoDB?** Não há necessidade demonstrada de banco documental; SQL Server atende modelo relacional e requisito de segurança/consulta com menor escopo.
- **O que faz o RAG?** Recupera trechos citáveis de documentos atuais; não substitui banco transacional nem fine-tuning.
- **Por que a IA não pode pagar?** Pode errar ou ser manipulada; decisão financeira precisa de regra auditável e pessoa autorizada.
- **Qual é o custo?** API é cobrança por tokens e o exemplo usa 2.000 de entrada/500 de saída; local troca tarifa por consumo de recursos e equipamento. Recalcular com o volume e preços atuais.
- **O que é dado pessoal sensível?** Categoria legal específica da LGPD; dados financeiros não entram automaticamente nela, mas o projeto os restringe por risco.
- **O que prova segurança?** Usuários reais de laboratório, permissões testadas, nenhum dado fora do escopo, nenhum efeito indevido e evidência registrada — não apenas uma matriz desenhada.
- **O sistema já está pronto para NSDocs?** Não. A integração automática com NSDocs/Globus é uma etapa futura, fora do MVP atual.

## Fontes para conferir

- Lei Geral de Proteção de Dados — Lei nº 13.709/2018: <https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm>
- Preços OpenAI API: <https://developers.openai.com/api/docs/pricing/>
- Preços Anthropic API: <https://platform.claude.com/docs/en/about-claude/pricing>
- Catálogo de modelos Ollama/Qwen2.5: <https://ollama.com/library/qwen2.5>
- Documentação SQL Server sobre permissões e segurança: <https://learn.microsoft.com/sql/relational-databases/security/permissions-database-engine>

Preços, modelos e licenças mudam. Consulte as fontes oficiais antes da apresentação. Este material é orientação acadêmica e não aconselhamento jurídico.
