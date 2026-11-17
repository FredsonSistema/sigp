// Aba Assistente: pergunta por sugestão e digitada, resposta com os números do sistema, 👍 ensina, relatório em
// PDF e CSV baixa com a sessão, termo novo ensinado (API de TESTE).
const fs = require('fs');
const { launch, shot, check, loginFresh } = require('./lib');
(async () => {
  const results = [];
  const { browser, context } = await launch();
  const page = await context.newPage();
  page.on('dialog', (d) => d.accept(''));
  const ultima = () => page.locator('#assConversa .ass-ia').last();
  const esperarResposta = async (n) => page.waitForFunction((qtd) => document.querySelectorAll('#assConversa .ass-ia').length >= qtd
    && !document.querySelector('#assConversa [aria-busy="true"]'), n, { timeout: 180000 });
  try {
    await loginFresh(page);
    await page.evaluate(() => document.querySelector('.tab[data-view="assistente"]').click());
    await page.waitForSelector('#assPergunta', { timeout: 20000 });
    check(results, 'aba Assistente com sugestões', (await page.locator('.ass-sugestoes [data-sugestao]').count()) >= 4);
    await page.locator('[data-sugestao="Quantas agências estão em atraso?"]').click();
    await esperarResposta(1);
    const r1 = await ultima().innerText();
    check(results, 'responde quantas agências estão em atraso, entendido por regra', /Hoje, \d{2}\/\d{2}\/\d{4}, (nenhuma|\d+ agência)/.test(r1) && /entendido por regra/.test(r1), r1.split('\n')[0]);
    await ultima().locator('[data-util="1"]').click();
    await page.waitForFunction(() => /Vou lembrar/.test(document.querySelector('#assConversa .ass-ia:last-child')?.textContent || ''), null, { timeout: 15000 });
    check(results, '👍 ensina o assistente', true);
    await page.fill('#assPergunta', 'crie um relatório com a lista de agências');
    await page.press('#assPergunta', 'Enter');
    await esperarResposta(2);
    const r2 = await ultima().innerText();
    check(results, 'relatório pronto com PDF e Excel', /Pronto: relatório/.test(r2) && /PDF/.test(r2) && /Excel/.test(r2), r2.split('\n')[0]);
    const [download] = await Promise.all([page.waitForEvent('download', { timeout: 20000 }), ultima().locator('a', { hasText: 'Excel' }).click()]);
    const conteudo = fs.readFileSync(await download.path(), 'utf8');
    check(results, 'CSV baixa com a sessão, com cabeçalho e acentos', conteudo.startsWith('\ufeffTipo;Nome;Cidade;Endereço'), conteudo.split('\n')[0]);
    await shot(page, 'assistente-01');
    // Termo ensinado
    await page.locator('details', { hasText: 'Ensinar um termo' }).locator(':scope > summary').click();
    await page.fill('#assTermo', 'em débito');
    await page.fill('#assSignifica', 'vencida');
    await page.locator('#assTermoForm button[type=submit]').click();
    await page.waitForFunction(() => /Aprendido/.test(document.getElementById('assTermoStatus').textContent), null, { timeout: 15000 });
    await page.fill('#assPergunta', 'quantas contas estão em débito?');
    await page.press('#assPergunta', 'Enter');
    await esperarResposta(3);
    const r3 = await ultima().innerText();
    check(results, 'termo ensinado passa a valer na próxima pergunta', /(contas? vencidas?|nenhuma)/.test(r3) && /entendido por regra/.test(r3), r3.split('\n')[0]);
  } catch (error) {
    check(results, 'execução do teste', false, error.message.split('\n')[0]);
    await shot(page, 'assistente-erro').catch(() => {});
  } finally {
    await browser.close();
  }
  const falhas = results.filter((x) => !x.ok).length;
  console.log(`\n${results.length - falhas}/${results.length} verificações passaram.`);
  process.exit(falhas ? 1 : 0);
})();
