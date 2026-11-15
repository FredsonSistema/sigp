# Histórico de prompts

| Versão | Estado | Mudanças |
|---|---|---|
| v1.0 | Baseline do WF-05, nó Claude desativado | Resumo livre em até seis linhas a partir de um JSON; sem RAG, esquema de saída ou defesa explícita contra instruções em documentos. |
| v2.0 | Arquivada | Adiciona contexto SQL escopado, trechos RAG não confiáveis, classificação em três estados, retorno JSON validável, citações limitadas aos IDs recebidos e resposta `REVISAR` diante de dúvida. |
| v3.0 | Avaliação com classificação determinística | Regras estruturadas com evidência recuperada calculam classificação e fontes. O LLM produz somente uma classificação experimental; sua concordância é medida, sem autoridade para alterar o resultado. |
| v4.0 | Em produção no SIGp (12/11/2026) | Família de três prompts (triagem do Gmail, análise SIG, resumo SIE) com JSON Schema; fatos calculados no fluxo e copiados pela LLM (sem refazer contas); regras de linguagem por público; regras de domínio (empresas do grupo, endereço, nosso número). A regra continua decidindo. A v3.0 segue como prompt da API acadêmica. |
| v4.1 | Em produção no SIGp (14/11/2026) | Só o prompt de triagem do Gmail muda: nova seção "Exemplos confirmados" com até 4 decisões do operador em documentos parecidos (vindas de `GET /api/llm/exemplos`). O modelo usa os exemplos como referência para tipo de documento e provedor, e nunca copia valor, vencimento ou número deles. A/B com qwen2.5:3b em `sqlserver/evidence/parte2/memoria-exemplos-ab.json`. SHA-256 de `n8n/wf08/prompt_classificacao.md`: `39A763BA6CD662FCD3F6646289A15B452E92F1ED0ADB6DAD3C1C11C7972DC615`. Detalhes em `v4.1.md`. |
| v4.2 | Em produção no SIGp (15/11/2026) | Triagem do Gmail: campo novo `evento` (fatura_nova, segunda_via, lembrete_vencimento, aviso_atraso, pagamento_confirmado), usado quando a regra do SIGp não acha frase clara; "provedorNome vem sempre do documento atual" (antes os exemplos eram a principal referência e a LLM copiou o provedor de um exemplo). O fluxo também descarta provedor sugerido que não aparece no documento. |

O histórico guarda o texto completo em `v1.md` a `v4.md`. Toda alteração futura deve criar nova versão, não sobrescrever a versão testada. Registrar no resultado de cada caso o hash da versão usada.
