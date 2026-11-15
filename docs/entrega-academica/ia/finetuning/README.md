# Experimento LoRA — classificação acadêmica

Experimento preliminar, com dados inteiramente sintéticos. O classificador determinístico da API continua sendo a autoridade. O adaptador pode ser carregado no Ollama local para avaliação, mas permanece não autoritativo e não pode autorizar pagamentos.

## Reproduzir

No ambiente Python configurado na raiz do repositório:

```powershell
python -m pip install torch transformers peft accelerate
python docs\entrega-academica\ia\finetuning\generate_dataset.py
python docs\entrega-academica\ia\finetuning\train_lora.py
```

O conjunto contém 120 registros sintéticos, aproximadamente balanceados entre `CONTRATADO`, `DIVERGENTE` e `REVISAR`: 80 treino, 20 validação e 20 teste. As cinco amostras de aceitação da API ficam fora dele. O dataset gerado e seu SHA-256 são registrados junto aos resultados. Os exemplos usam famílias de cenários repetidas entre partições; por isso, as métricas são exploratórias e não comprovam generalização para documentos ou serviços novos.

## Configuração

- Base: `Qwen/Qwen2.5-0.5B-Instruct`, revisão `7ae557604adf67be50417f59c2c2f167def9a775`.
- Execução: CPU, pesos float32, um ciclo, LoRA rank 4 nos módulos `q_proj` e `v_proj`.
- Comparação: mesma base e mesmo conjunto reservado, antes e depois do ajuste; acurácia, macro-F1 e matriz de confusão.
- Saídas locais: `dataset.jsonl`, `training-results.json` e `output/qwen2.5-0.5b-lora/`.

O primeiro download do modelo requer acesso ao Hugging Face. A execução pode ser lenta em CPU. Não confundir o modelo Ollama quantizado original com o checkpoint treinável; o adaptador foi treinado sobre a revisão Hugging Face fixada e precisa ser mesclado à mesma base antes da importação no Ollama.

## Integrar ao serviço acadêmico

A importação direta de Safetensors no Ollama não é compatível com a arquitetura do checkpoint Qwen utilizado. A integração experimental executa o checkpoint e o adaptador PEFT em um serviço Transformers isolado na rede Docker; a API acadêmica chama esse serviço e continua retornando a decisão determinística como autoridade.

Com Docker em execução, o arquivo local `docs\entrega-academica\sqlserver\.env.academic` configurado e o adaptador presente, execute na raiz do repositório:

```powershell
powershell -ExecutionPolicy Bypass -File docs\entrega-academica\ia\finetuning\integrate-lora.ps1
```

O primeiro build baixa as dependências Python e o checkpoint Hugging Face fixado, portanto pode demorar e requer acesso à internet. O script valida a configuração Compose, constrói o serviço `academic-lora`, recria a API com o override `compose.lora.yml` e aguarda os health checks dos dois serviços. Ele não altera o arquivo `.env.academic` nem o modelo baseline no Ollama. Em caso de falha após a ativação do Compose, tenta restaurar a API para o backend Ollama e interrompe o serviço LoRA.

Para voltar manualmente ao baseline, recrie a API usando apenas o Compose principal:

```powershell
docker compose --env-file docs\entrega-academica\sqlserver\.env.academic `
  -f docs\entrega-academica\sqlserver\compose.academic.yml `
  up -d --force-recreate academic-ai
```

O perfil informado pela API passa a ser `experimental-lora`; o runner também registra esse campo por caso. Confirme a inferência real com os casos sintéticos e, então, o fluxo no n8n. O LLM e o adaptador continuam experimentais, e a classificação determinística continua sendo a decisão retornada pela API.

Para guardar uma nova rodada sem substituir evidências anteriores, defina `SIGP_AI_TEST_OUTPUT` com o caminho do novo arquivo antes de executar `run_cases.py`.

O workflow n8n publicado `SIGp Acadêmico - RAG e Análise` chama a mesma API em `http://academic-ai:5010/api/analyze`, pelo webhook `POST /webhook/sigp-academic-ai`. O WF-05 do SIGp também chama diretamente essa API para anexar um parecer experimental às análises, desde que os dados da fatura estejam completos. O cabeçalho `X-API-Key` deve usar a expressão `{{ $env.SIGP_ACADEMIC_AI_KEY }}`; a variável do n8n precisa corresponder a `SIGP_AI_API_KEY` no `.env.academic`, sem registrar nenhum dos valores no repositório. O arquivo `../n8n_workflow_academic_ai.json` continua como modelo de importação inativo; ao importá-lo em outra instância, revise a variável e publique o workflow antes de usar o webhook.

A validação sintética pelo webhook está registrada em `../../sqlserver/evidence/n8n-webhook-smoke.json`. A bateria de cinco casos da API está em `../../sqlserver/evidence/ai-test-results-lora.json`; nela, as regras determinísticas passaram nos cinco casos e o modelo experimental concordou em três.

## Limitações

O conjunto sintético é pequeno e construído por regras, portanto a métrica é apenas preliminar. Não representa generalização para faturas reais, não substitui avaliação humana e não deve ser apresentada como evidência de redução de erros sem validação externa e maior volume de dados.
