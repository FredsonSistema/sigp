// Código dos nós Code do WF-05 (fase C). Fonte versionada: build_wf05.py copia cada bloco para o nó.
// Os marcadores /*__PROMPT_SIG__*/ etc. são substituídos pelo conteúdo de prompt_*.md e schema_*.json.

// ==== NO: Preparar pedido à LLM (SIG)
// A LLM local analisa os ciclos fechados (MATCH = 3 evidências) e as divergências (D14). Os demais status
// seguem com o texto da regra. A regra do SIGp continua sendo a decisão oficial (D13).
const base = $input.first().json;
const precisaLLM = ['MATCH', 'DIVERGENCIA'].includes(base.status);
const { parecerIA, ...dadosDoCiclo } = base.dados || {};
// Fatos calculados aqui (a LLM pequena erra contas de data e valor): ela só redige a partir deles.
const brl = (v) => 'R$ ' + Number(v || 0).toFixed(2).replace('.', ',');
const dataBR = (iso) => (/^\d{4}-\d{2}-\d{2}/.test(String(iso || '')) ? String(iso).slice(0, 10).split('-').reverse().join('/') : 'não informado');
const dias = (a, b) => Math.round((Date.parse(String(a).slice(0, 10)) - Date.parse(String(b).slice(0, 10))) / 86400000);
const fatos = [];
const lancado = Number(dadosDoCiclo.valorLancado || 0);
const pago = Number(dadosDoCiclo.valorPagoAcumulado || 0);
const valorFatura = Number(dadosDoCiclo.fatura?.valor || 0);
fatos.push(`Valor lançado: ${brl(lancado)}. Valor pago: ${pago ? brl(pago) : 'nenhum pagamento'}.`
  + (pago ? (Math.abs(lancado - pago) < 0.01 ? ' Pago igual ao lançado.' : ` Diferença: ${brl(pago - lancado)} (${pago < lancado ? 'pago a menos' : 'pago a mais'}).`) : ''));
fatos.push(dadosDoCiclo.fatura
  ? `Fatura: ${brl(valorFatura)}, vencimento ${dataBR(dadosDoCiclo.fatura.vencimento)}.` + (Math.abs(valorFatura - lancado) < 0.01 ? ' Fatura igual ao lançado.' : ` Diferença fatura x lançado: ${brl(valorFatura - lancado)}.`)
  : 'Fatura: ainda não disponível.');
if (dadosDoCiclo.dataPagamento && dadosDoCiclo.vencimento) {
  const d = dias(dadosDoCiclo.dataPagamento, dadosDoCiclo.vencimento);
  fatos.push(`Pagamento em ${dataBR(dadosDoCiclo.dataPagamento)}, vencimento em ${dataBR(dadosDoCiclo.vencimento)}: `
    + (d === 0 ? 'pago no dia do vencimento (no prazo).' : d < 0 ? `pago ${-d} dia(s) ANTES do vencimento (no prazo).` : `pago ${d} dia(s) DEPOIS do vencimento (em atraso).`));
} else {
  fatos.push(`Vencimento: ${dataBR(dadosDoCiclo.vencimento)}. Data de pagamento: não informada.`);
}
if (dadosDoCiclo.fatura && dadosDoCiclo.fatura.emissor && dadosDoCiclo.provedor) fatos.push(`Provedor da nota: ${dadosDoCiclo.provedor}. Emissor da fatura: ${dadosDoCiclo.fatura.emissor}.`);
if (dadosDoCiclo.observacao) fatos.push(`Observação da regra: ${dadosDoCiclo.observacao}`);
const usuario = [
  `Status calculado pela regra do sistema (oficial): ${base.status}`,
  `Local: ${dadosDoCiclo.local || dadosDoCiclo.localNome || 'não informado'}. Nota: ${dadosDoCiclo.numero || 'não informada'}.`,
  'FATOS CALCULADOS (corretos; use exatamente estes, não refaça contas):',
  ...fatos.map((f) => `- ${f}`),
].join('\n');
const ollamaBody = {
  model: $env.SIGP_OLLAMA_MODEL || 'qwen2.5:3b',
  stream: false,
  options: { temperature: 0, num_ctx: 4096 },
  format: /*__SCHEMA_SIG__*/,
  messages: [
    { role: 'system', content: /*__PROMPT_SIG__*/ },
    { role: 'user', content: usuario },
  ],
};
return [{ json: { ...base, precisaLLM, ollamaBody } }];
// ==== FIM

// ==== NO: Juntar análise da LLM
const base = $('Preparar pedido à LLM (SIG)').first().json;
const resposta = $input.first().json || {};
const ROTULO = { confere: 'confere', diverge: 'diverge', revisar: 'precisa de revisão' };
let llm = null;
let erro = '';
try {
  const conteudo = JSON.parse(resposta.message?.content || '');
  if (!ROTULO[conteudo.conclusao] || !String(conteudo.resumo || '').trim()) throw new Error('resposta fora do formato');
  llm = conteudo;
} catch (e) {
  erro = String(resposta.error?.message || resposta.error || e.message || 'sem resposta do Ollama').slice(0, 300);
}
const { ollamaBody, precisaLLM, ...resto } = base;
if (!llm) {
  // Sem LLM (fora do ar, lenta ou resposta inválida): grava a análise da regra e registra o motivo.
  return [{ json: { ...resto, dados: { ...resto.dados, analiseLLM: { status: 'nao_gerada', motivo: erro } } } }];
}
const discorda = (base.status === 'MATCH' && llm.conclusao !== 'confere')
  || (base.status === 'DIVERGENCIA' && llm.conclusao === 'confere');
const linhas = [
  `Análise da LLM local: ${ROTULO[llm.conclusao]}.`,
  String(llm.resumo).trim(),
  ...(Array.isArray(llm.pontosDeAtencao) ? llm.pontosDeAtencao : []).slice(0, 4).map((p) => `• ${String(p).trim()}`),
  llm.acaoSugerida ? `Ação sugerida: ${String(llm.acaoSugerida).trim()}` : null,
  discorda ? `Atenção: a LLM discorda da regra do sistema (${base.status}). O status oficial é o da regra; confira antes de validar.` : null,
  '',
  'Dados do sistema:',
  String(resto.conteudo || ''),
].filter((linha) => linha !== null);
return [{ json: {
  ...resto,
  conteudo: linhas.join('\n'),
  modelo: `LLM local ${ollamaBody.model} + regra do SIGp`,
  dados: { ...resto.dados, analiseLLM: { status: 'gerada', ...llm, discordaDaRegra: discorda, modelo: ollamaBody.model } },
} }];
// ==== FIM

// ==== NO: Montar mensagem
// Notifica ciclos fechados e divergências a partir do que foi gravado (já com a análise da LLM).
const r = $input.first().json || {};
const item = (r.body || r).item || {};
if (!['MATCH', 'DIVERGENCIA'].includes((item.dados || {}).status)) return [];
return [{ json: { assunto: `SIGp · ${item.titulo}`, texto: `${item.titulo}\n\n${item.conteudo}` } }];
// ==== FIM

// ==== NO: Montar etapa executiva
// Decisão do gerente (evento "decisao_gerente" enviado pelo SIGp). Só VALIDADA ou CORRIGIDA seguem para a SIE.
const evento = $input.first().json.body || {};
if (evento.evento !== 'decisao_gerente') return [];
const dados = evento.dados || {};
const decisao = dados.decisao || {};
const analise = dados.analise || {};
if (!['VALIDADA', 'CORRIGIDA'].includes(decisao.status)) return [];
const textoValidado = decisao.status === 'CORRIGIDA' && decisao.conteudo_corrigido ? decisao.conteudo_corrigido : analise.conteudo;
const { analiseLLM, parecerIA, ...resumo } = dados.resumo || {};
const brl = (v) => 'R$ ' + Number(v || 0).toFixed(2).replace('.', ',');
const dataBR = (iso) => (/^\d{4}-\d{2}-\d{2}/.test(String(iso || '')) ? String(iso).slice(0, 10).split('-').reverse().join('/') : 'não informado');
const diasPag = resumo.dataPagamento && resumo.vencimento
  ? Math.round((Date.parse(String(resumo.dataPagamento).slice(0, 10)) - Date.parse(String(resumo.vencimento).slice(0, 10))) / 86400000)
  : null;
const fatos = [
  `Local: ${resumo.local || resumo.localNome || 'não informado'}. Provedor: ${resumo.provedor || 'não informado'}.`,
  `Custo do ciclo (valor lançado): ${brl(resumo.valorLancado)}. Pago: ${brl(resumo.valorPagoAcumulado)}.`,
  diasPag === null ? 'Prazo: não informado.'
    : diasPag <= 0 ? `Prazo: pago no prazo (${diasPag === 0 ? 'no dia do vencimento' : `${-diasPag} dia(s) antes`}, vencimento ${dataBR(resumo.vencimento)}).`
      : `Prazo: pago com ${diasPag} dia(s) de atraso (vencimento ${dataBR(resumo.vencimento)}).`,
];
const usuario = [
  'FATOS CALCULADOS (corretos; use exatamente estes, não refaça contas):',
  ...fatos.map((f) => `- ${f}`),
  '',
  `Decisão do gerente: ${decisao.status === 'CORRIGIDA' ? 'validada com correção' : 'validada'} por ${decisao.usuario || 'gerente'}`
    + (decisao.justificativa ? ` (motivo: ${decisao.justificativa})` : ''),
  '',
  'Análise validada pelo gerente:',
  String(textoValidado || '').split('\nDados do sistema:')[0].trim(),
].join('\n');
const ollamaBody = {
  model: $env.SIGP_OLLAMA_MODEL || 'qwen2.5:3b',
  stream: false,
  options: { temperature: 0, num_ctx: 4096 },
  format: /*__SCHEMA_SIE__*/,
  messages: [
    { role: 'system', content: /*__PROMPT_SIE__*/ },
    { role: 'user', content: usuario },
  ],
};
return [{ json: {
  titulo: String(analise.titulo || 'Ciclo').replace(/^Análise manual · /, ''),
  referencia: analise.referencia || '',
  analiseOrigemId: analise.id || '',
  decisao,
  resumo,
  textoValidado,
  ollamaBody,
} }];
// ==== FIM

// ==== NO: Juntar resumo executivo
const base = $('Montar etapa executiva').first().json;
const resposta = $input.first().json || {};
let llm = null;
let erro = '';
try {
  const conteudo = JSON.parse(resposta.message?.content || '');
  if (!String(conteudo.resumoExecutivo || '').trim()) throw new Error('resposta fora do formato');
  llm = conteudo;
} catch (e) {
  erro = String(resposta.error?.message || resposta.error || e.message || 'sem resposta do Ollama').slice(0, 300);
}
const IMPACTO = { nenhum: 'nenhum', baixo: 'baixo', medio: 'médio', alto: 'alto' };
const validacao = `Validado por ${base.decisao.usuario || 'gerente'} em ${new Date(base.decisao.created_at || Date.now()).toLocaleString('pt-BR', { timeZone: 'America/Sao_Paulo' })}`
  + (base.decisao.status === 'CORRIGIDA' ? ' (com correção)' : '') + '.';
const conteudo = llm
  ? [String(llm.resumoExecutivo).trim(), `Impacto: ${IMPACTO[llm.impacto] || 'não informado'}.`,
     llm.recomendacao ? `Recomendação: ${String(llm.recomendacao).trim()}` : '', validacao].filter(Boolean).join('\n')
  : [String(base.textoValidado || '').trim(), validacao].join('\n\n');
return [{ json: {
  escopo: 'SIE',
  titulo: base.titulo,
  referencia: base.referencia,
  conteudo,
  modelo: llm ? `LLM local ${base.ollamaBody.model}` : 'Análise validada pelo gerente (LLM indisponível)',
  dados: {
    ...base.resumo,
    analiseOrigemId: base.analiseOrigemId,
    decisaoGerente: base.decisao,
    resumoExecutivoLLM: llm ? { status: 'gerado', ...llm } : { status: 'nao_gerado', motivo: erro },
  },
} }];
// ==== FIM
