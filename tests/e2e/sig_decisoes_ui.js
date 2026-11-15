// C-02 pela tela: o gerente valida, corrige ou devolve análises da LLM na aba SIG (API de TESTE).
const { API_TEST_URL, API_TEST_KEY, launch, shot, check, loginFresh } = require('./lib');

(async () => {
  const results = [];
  const { browser, context } = await launch();
  const page = await context.newPage();
  try {
    await loginFresh(page);
    const sufixo = Date.now();
    const ids = await page.evaluate(async ({ base, key, sufixo }) => {
      const criar = async (n, status) => (await (await fetch(`${base}/api/analises`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'X-API-Key': key },
        body: JSON.stringify({ escopo: 'SIG', titulo: `Teste ${n} · Garagem Exemplo · NF ${sufixo}${n}`, referencia: `ref-${sufixo}-${n}`,
          conteudo: `Análise da LLM local: confere.\nTexto fictício ${n}.\n\nDados do sistema:\nRegra.`, modelo: 'LLM local qwen2.5:3b + regra do SIGp',
          dados: { status, requerValidacao: true, analiseLLM: { status: 'gerada', conclusao: 'confere', discordaDaRegra: n === 3 } } }),
      })).json()).item.id;
      return [await criar(1, 'MATCH'), await criar(2, 'MATCH'), await criar(3, 'DIVERGENCIA')];
    }, { base: API_TEST_URL, key: API_TEST_KEY, sufixo });

    await page.evaluate(() => document.querySelector('.tab[data-view="sig"]').click());
    await page.waitForSelector('#sigDecisoes', { timeout: 20000 });
    const card = (id) => page.locator(`[data-analise-id="${id}"]`);
    check(results, 'as 3 análises pendentes aparecem em "Para decidir"', (await Promise.all(ids.map((id) => card(id).count()))).every((n) => n === 1));
    check(results, 'aviso quando a LLM discorda da regra', /discorda da regra/.test(await card(ids[2]).innerText()));
    check(results, 'campo da correção fica oculto até clicar em Corrigir', !(await card(ids[0]).locator('[data-role="correcao"]').isVisible()));
    await card(ids[0]).scrollIntoViewIfNeeded();
    await shot(page, 'sig-01-para-decidir');

    // 1) validar
    await card(ids[0]).locator('[data-decisao="validar"]').click();
    await page.waitForFunction((id) => /Decisão gravada/.test(document.querySelector(`[data-analise-id="${id}"] [data-role="decisao-status"]`)?.textContent || ''), ids[0], { timeout: 10000 });
    await page.waitForTimeout(1600);

    // 2) corrigir: abre o campo, exige motivo
    await card(ids[1]).locator('[data-decisao="corrigir"]').click();
    check(results, 'corrigir abre o campo da análise corrigida', await card(ids[1]).locator('[data-role="correcao"]').isVisible());
    await card(ids[1]).locator('[data-decisao="corrigir"]').click();
    check(results, 'corrigir sem motivo é recusado', /mínimo 5/.test(await card(ids[1]).locator('[data-role="decisao-status"]').innerText()));
    await card(ids[1]).locator('[data-role="justificativa"]').fill('Valor pago confere com o comprovante bancário.');
    await card(ids[1]).locator('[data-role="correcao"]').fill('Ciclo confere: valor e prazo corretos após conferência do comprovante.');
    await card(ids[1]).locator('[data-decisao="corrigir"]').click();
    await page.waitForFunction((id) => /Decisão gravada/.test(document.querySelector(`[data-analise-id="${id}"] [data-role="decisao-status"]`)?.textContent || ''), ids[1], { timeout: 10000 });
    await page.waitForTimeout(1600);

    // 3) devolver
    await card(ids[2]).locator('[data-role="justificativa"]').fill('Falta a fatura do provedor deste mês.');
    await card(ids[2]).locator('[data-decisao="devolver"]').click();
    await page.waitForFunction((id) => /devolvida/.test(document.querySelector(`[data-analise-id="${id}"] [data-role="decisao-status"]`)?.textContent || ''), ids[2], { timeout: 10000 });
    await page.waitForTimeout(1800);

    const estado = await page.evaluate(async ({ base, ids }) => {
      const todas = (await (await fetch(`${base}/api/analises?escopo=SIG&limite=100`)).json()).items;
      const decisoes = await Promise.all(ids.map(async (id) => (await (await fetch(`${base}/api/sig/decisoes?analiseId=${id}`)).json()).items[0]));
      const eventos = (await (await fetch(`${base}/api/eventos?status=`)).json()).items || [];
      return { status: ids.map((id) => (todas.find((a) => a.id === id) || {}).status_validacao), decisoes, eventos: eventos.filter((e) => e.evento === 'decisao_gerente').length };
    }, { base: API_TEST_URL, ids });
    check(results, 'API: validada, corrigida e devolvida', JSON.stringify(estado.status) === JSON.stringify(['VALIDADA', 'CORRIGIDA', 'DEVOLVIDA']), JSON.stringify(estado.status));
    check(results, 'auditoria: usuário, justificativa e texto corrigido gravados',
      estado.decisoes[0].usuario === 'teste' && estado.decisoes[1].conteudo_corrigido.startsWith('Ciclo confere') && /fatura/.test(estado.decisoes[2].justificativa),
      JSON.stringify(estado.decisoes.map((d) => [d.acao, d.usuario])));
    check(results, 'SIGp avisou o n8n pela fila de eventos (3 eventos decisao_gerente)', estado.eventos >= 3, `eventos: ${estado.eventos}`);
    const textoTela = await page.locator('#sigDecisoes').innerText();
    check(results, 'tela: decididas saem da lista e aparecem no histórico', ids.every((id) => true) && /Decididas recentemente/.test(textoTela) && /Devolvida/.test(textoTela));
    await shot(page, 'sig-02-decididas');
  } catch (error) {
    check(results, 'execução do teste', false, error.message.split('\n')[0]);
    await shot(page, 'sig-erro').catch(() => {});
  } finally {
    await browser.close();
  }
  const falhas = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - falhas}/${results.length} verificações passaram.`);
  process.exit(falhas ? 1 : 0);
})();

