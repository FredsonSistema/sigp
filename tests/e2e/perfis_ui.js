// Perfis e permissões: o administrador cria um usuário do grupo Leitura; esse usuário entra com a própria chave,
// vê o nome e o grupo, não vê abas sem permissão e a API recusa as gravações dele (API de TESTE).
const { API_TEST_URL, launch, shot, check, loginFresh } = require('./lib');
(async () => {
  const results = [];
  const { browser, context } = await launch();
  const page = await context.newPage();
  page.on('dialog', (d) => d.accept());
  try {
    await loginFresh(page);
    await page.evaluate(() => document.querySelector('.tab[data-view="config"]').click());
    await page.waitForSelector('#cfgPermissoes details.cfg-grupo', { timeout: 20000 });
    const secoes = await page.locator('#cfgPermissoes details.cfg-grupo > summary .nr-list-title').allInnerTexts();
    check(results, 'quatro seções: usuários, grupos, funcionalidades e auditoria', secoes.join('|') === 'Usuários|Grupos de permissão|Funcionalidades do sistema|Auditoria de acesso', secoes.join(' | '));
    check(results, 'administrador fixo (chave do .env)', /Administrador · todas as permissões · fixo/.test(await page.locator('#cfgPermissoes .perm-fixo').innerText()));
    check(results, 'chip mostra "Administrador"', (await page.locator('#perfilAtivo').innerText()) === 'Administrador');
    // Catálogo: todas as funcionalidades com a matriz por grupo
    await page.locator('#cfgPermissoes details.cfg-grupo').nth(2).locator(':scope > summary').click();
    const linhas = await page.locator('#cfgPermissoes .perm-tabela tbody tr').count();
    check(results, 'catálogo lista as funcionalidades do sistema (25+)', linhas >= 25, `${linhas} funcionalidades`);
    // Novo usuário do grupo Leitura
    const nome = `Auditoria ${Date.now()}`;
    await page.fill('#permNovoNome', nome);
    await page.selectOption('#permNovoGrupo', 'grp-leitura');
    await page.locator('#cfgPermissoes [data-acao="criar-usuario"]').click();
    await page.waitForSelector('#cfgPermissoes [data-chave]', { timeout: 15000 });
    const chave = await page.locator('#cfgPermissoes [data-chave]').innerText();
    check(results, 'chave nova aparece uma vez para entregar', /^sigp_/.test(chave));
    await shot(page, 'perm-01-admin');
    // Ajuste individual: permitir "Ordens de serviço" só para este usuário
    const usuario = page.locator('#cfgPermissoes [data-usuario]', { hasText: nome });
    await usuario.locator(':scope > summary').click();
    await usuario.locator('details.nr-disc', { hasText: 'Operação do dia a dia' }).locator(':scope > summary').click();
    await usuario.locator('[data-ajuste="os.usar"]').selectOption('permitir');
    await usuario.locator('[data-acao="salvar-usuario"]').click();
    await page.waitForFunction(() => /Usuário salvo/.test(document.querySelector('#cfgPermissoes [data-perm-status]')?.textContent || ''), null, { timeout: 15000 });
    check(results, 'ajuste individual salvo', true);

    // O usuário entra com a própria chave num navegador novo
    const ctx2 = (await launch()).context;
    const p2 = await ctx2.newPage();
    await loginFresh(p2, chave);
    await p2.waitForFunction(() => document.getElementById('perfilAtivo')?.textContent, null, { timeout: 15000 });
    check(results, 'chip mostra o nome e o grupo do usuário', (await p2.locator('#perfilAtivo').innerText()) === `${nome} · Leitura`);
    const abas = await p2.evaluate(() => Object.fromEntries([...document.querySelectorAll('.tab[data-view]')].map((t) => [t.dataset.view, !t.hidden])));
    check(results, 'abas: vê notas e OS (ajuste), não vê agenda pessoal', abas.notas && abas.os && !abas['agenda-pessoal'], JSON.stringify(abas));
    const gravar = await p2.evaluate(async (api) => {
      const r = await fetch(`${api}/api/locais/agencia/item`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ nome: 'X', cidade: 'Y' }) });
      return [r.status, (await r.json()).error];
    }, API_TEST_URL);
    check(results, 'API recusa gravação do perfil Leitura com mensagem clara', gravar[0] === 403 && /Leitura/.test(gravar[1]), gravar.join(' · '));
    await p2.evaluate(() => document.querySelector('.tab[data-view="config"]').click());
    await p2.waitForSelector('#cfgPermissoes [data-trocar-chave]', { timeout: 15000 });
    check(results, 'usuário vê o próprio perfil, sem poder editar', /Só o administrador altera/.test(await p2.locator('#cfgPermissoes').innerText()));
    await shot(p2, 'perm-02-usuario');
    await ctx2.browser().close();

    // Auditoria registra a recusa
    await page.reload();
    await page.waitForFunction(() => getComputedStyle(document.querySelector('#appRoot')).display !== 'none', null, { timeout: 20000 });
    await page.evaluate(() => document.querySelector('.tab[data-view="config"]').click());
    await page.waitForSelector('#cfgPermissoes details.cfg-grupo', { timeout: 20000 });
    await page.locator('#cfgPermissoes details.cfg-grupo').nth(3).locator(':scope > summary').click();
    const aud = await page.locator('#cfgPermissoes details.cfg-grupo').nth(3).innerText();
    check(results, 'auditoria mostra a recusa do usuário', aud.includes(nome) && /negado \(403\)/.test(aud));
  } catch (error) {
    check(results, 'execução do teste', false, error.message.split('\n')[0]);
    await shot(page, 'perm-erro').catch(() => {});
  } finally {
    await browser.close();
  }
  const falhas = results.filter((x) => !x.ok).length;
  console.log(`\n${results.length - falhas}/${results.length} verificações passaram.`);
  process.exit(falhas ? 1 : 0);
})();
