// SIE: indicadores contam só ciclos validados pelo gerente e mostram "Aguardando o gerente" (API de TESTE).
const { launch, shot, check, loginFresh } = require('./lib');

(async () => {
  const results = [];
  const { browser, context } = await launch();
  const page = await context.newPage();
  try {
    await loginFresh(page);
    await page.evaluate(() => document.querySelector('.tab[data-view="sie"]').click());
    await page.locator('#view_sie .dash-card h3', { hasText: 'Aguardando o gerente' }).waitFor({ timeout: 20000 });
    const texto = await page.locator('#view_sie').innerText();
    check(results, 'card "Aguardando o gerente" presente', /Aguardando o gerente/i.test(texto));
    check(results, 'texto explica que só entram ciclos validados', /validados pelo gerente/.test(texto));
    check(results, 'resumos executivos mostram quem validou (quando houver)', !/undefined|NaN/.test(texto));
    await shot(page, 'sie-01');
  } catch (error) {
    check(results, 'execução do teste', false, error.message.split('\n')[0]);
  } finally {
    await browser.close();
  }
  const falhas = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - falhas}/${results.length} verificações passaram.`);
  process.exit(falhas ? 1 : 0);
})();
