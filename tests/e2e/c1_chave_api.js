// C1 — a chave da API não deve ser pedida a cada login.
// Uso: node c1_chave_api.js   (API de teste na porta 5011 precisa estar no ar)
const { APP_URL, API_TEST_KEY, launch, shot, visible, check } = require('./lib');

(async () => {
  const results = [];
  const { browser, context } = await launch();
  try {
    let page = await context.newPage();
    await page.goto(APP_URL);
    await page.waitForSelector('#authScreen');
    check(results, 'primeiro acesso: tela de criação de acesso', await visible(page, '#setupForm'));
    await page.waitForTimeout(1500);
    check(results, 'primeiro acesso: bloco de chave visível (esperado: sim, não há chave salva)', await visible(page, '#apiKeySetup'));
    await shot(page, 'c1-01-primeiro-acesso');

    // cria o acesso do usuário de teste
    await page.fill('#su_user', 'teste');
    await page.fill('#su_pass', 'senha1234');
    await page.fill('#su_pass2', 'senha1234');
    await page.click('#setupForm button[type=submit]');
    await page.waitForFunction(() => /recusou/i.test(document.getElementById('apiKeySetupStatus').textContent), null, { timeout: 15000 });
    const msg401 = await page.textContent('#apiKeySetupStatus');
    check(results, 'sem chave salva: a API recusa (401) e pede a chave', /recusou a chave|401/i.test(msg401), msg401.slice(0, 80));
    await shot(page, 'c1-02-pede-chave');

    // informa a chave uma vez
    await page.fill('#apiKeySetupInput', API_TEST_KEY);
    await page.click('#apiKeySetupForm button[type=submit]');
    await page.waitForFunction(() => getComputedStyle(document.querySelector('#appRoot')).display !== 'none', null, { timeout: 20000 });
    check(results, 'após informar a chave, o app abre', true);
    const salva = await page.evaluate(() => Boolean(localStorage.getItem('sigp_api_key')));
    check(results, 'a chave ficou salva no navegador (localStorage)', salva);
    await shot(page, 'c1-03-app-aberto');

    // sair e entrar de novo (mesma aba): não deve pedir a chave
    await page.evaluate(() => document.getElementById('btnLogout').click());
    await page.waitForSelector('#authScreen', { state: 'visible' });
    await page.waitForSelector('#loginForm', { state: 'visible' });
    await page.waitForTimeout(1500);
    const blocoNoLogin = await visible(page, '#apiKeySetup');
    check(results, 'LOGIN COM CHAVE JÁ SALVA: o bloco da chave NÃO deve aparecer', !blocoNoLogin,
      blocoNoLogin ? 'o bloco continua visível na tela de login' : '');
    await shot(page, 'c1-04-login-com-chave-salva');

    await page.fill('#li_user', 'teste');
    await page.fill('#li_pass', 'senha1234');
    await page.click('#loginForm button[type=submit]');
    await page.waitForFunction(() => getComputedStyle(document.querySelector('#appRoot')).display !== 'none', null, { timeout: 20000 });
    check(results, 'login sem digitar a chave abre o app', true);

    // fecha tudo e reabre (nova aba, mesmo perfil): a chave persiste?
    await page.close();
    page = await context.newPage();
    await page.goto(APP_URL);
    await page.waitForSelector('#authScreen');
    await page.waitForTimeout(1500);
    const persistiu = await page.evaluate(() => Boolean(localStorage.getItem('sigp_api_key')));
    check(results, 'nova aba: a chave continua salva', persistiu);
    check(results, 'nova aba: tela de login sem bloco de chave', !(await visible(page, '#apiKeySetup')));

    // chave salva deixa de valer (ex.: .env mudou): deve voltar a pedir, com mensagem clara
    await page.evaluate(() => localStorage.setItem('sigp_api_key', 'chave-antiga-invalida'));
    await page.reload();
    await page.waitForSelector('#loginForm', { state: 'visible' });
    await page.waitForTimeout(1500);
    check(results, 'chave salva inválida: o bloco já aparece na tela de login, com aviso', await visible(page, '#apiKeySetup') && /não é mais aceita/i.test(await page.textContent('#apiKeySetupStatus')));
    await page.fill('#li_user', 'teste');
    await page.fill('#li_pass', 'senha1234');
    await page.click('#loginForm button[type=submit]');
    await page.waitForFunction(() => /recusou|não é mais aceita/i.test(document.getElementById('apiKeySetupStatus').textContent), null, { timeout: 15000 });
    check(results, 'chave salva inválida: mostra o pedido da chave com mensagem', await visible(page, '#apiKeySetup'));
    await shot(page, 'c1-05-chave-invalida');
  } catch (error) {
    check(results, 'execução do teste', false, error.message.split('\n')[0]);
  } finally {
    await browser.close();
  }
  const falhas = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - falhas}/${results.length} verificações passaram.`);
  process.exit(falhas ? 1 : 0);
})();


