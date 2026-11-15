// Teste do Ollama a partir do container do n8n (mesma rota que os workflows usam).
// Uso: Get-Content tests/e2e/ollama_teste.js -Raw | docker exec -i sigp_n8n node
const url = (process.env.SIGP_OLLAMA_URL || 'http://ollama:11434') + '/api/chat';
const model = process.env.SIGP_OLLAMA_MODEL || 'qwen2.5:3b';
const body = {
  model,
  stream: false,
  options: { temperature: 0 },
  format: {
    type: 'object',
    properties: { tipoDocumento: { type: 'string', enum: ['boleto_fatura', 'nota_fiscal', 'outro'] }, valor: { type: ['number', 'null'] } },
    required: ['tipoDocumento', 'valor'],
  },
  messages: [
    { role: 'system', content: 'Classifique o documento e extraia o valor. Responda só com o JSON do schema.' },
    { role: 'user', content: 'FATURA FICTÍCIA - BENEFICIÁRIO: FIBRANET TELECOM LTDA - VENCIMENTO 12/12/2026 - TOTAL A PAGAR R$ 289,90' },
  ],
};
(async () => {
  for (const rodada of ['1ª (carrega o modelo)', '2ª (modelo carregado)']) {
    const inicio = Date.now();
    const resposta = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const json = await resposta.json();
    console.log(`${rodada}: HTTP ${resposta.status} em ${((Date.now() - inicio) / 1000).toFixed(1)} s -> ${json.message?.content || JSON.stringify(json).slice(0, 200)}`);
  }
  console.log(`url=${url} modelo=${model}`);
})().catch((e) => { console.log('ERRO', e.message); process.exit(1); });
