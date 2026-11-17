// Aba Assistente (estilo chat): conversas à esquerda, conversa no centro, artefatos à direita; continuação da
// conversa; relatório PDF e Excel no painel; histórico reabre; treino com 👍 e termo novo (API de TESTE).
const fs = require('fs');
const { launch, shot, check, loginFresh } = require('./lib');
(async () => {
  const results = [];
  const { browser, context } = await launch();
  const page = await context.newPage();
  page.on('dialog', (d) => d.accept(''));
  const respostas = () => page.locator('#view_assistente .chat-ia .chat-texto');
  const esperar = async (n) => page.waitForFunction((qtd) => document.querySelectorAll('#view_assistente .chat-ia .chat-texto').length >= qtd
    && !document.querySelector('#view_assistente [aria-busy="true"]'), n, { timeout: 180000 });
  const perguntar = async (texto) => { await page.fill('#chatPergunta', texto); await page.press('#chatPergunta', 'Enter'); };
  try {
    await loginFresh(page);
    await page.evaluate(() => document.querySelector('.tab[data-view="assistente"]').click());
    await page.waitForSelector('#view_assistente .chat-boas-vindas', { timeout: 20000 });
    check(results, 'três colunas: conversas, conversa e artefatos', await page.locator('#view_assistente .chat-lateral').isVisible()
      && await page.locator('#view_assistente .chat-centro').isVisible() && await page.locator('#view_assistente .chat-painel').isVisible());
    check(results, 'tela inicial com "Como posso ajudar?" e sugestões', (await page.locator('.chat-sugestao').count()) >= 4);
    await page.locator('.chat-sugestao', { hasText: 'Quantas agências estão em atraso?' }).click();
    await esperar(1);
    check(results, 'resposta com os números do sistema', /Hoje, \d{2}\/\d{2}\/\d{4}, (nenhuma|\d+ agência)/.test(await respostas().last().innerText()));
    check(results, 'conversa nova aparece na lista com o título da pergunta',
      (await page.locator('.chat-conv.ativa .chat-conv-abrir').innerText()).startsWith('Quantas agências estão em atraso?'));
    const temTabela = await page.locator('.chat-art-tabela tbody tr').count();
    check(results, 'tabela vai para o painel de artefatos, fora da conversa', temTabela > 1, `${temTabela} linhas`);
    await page.locator('.chat-ia [data-util="1"]').last().click();
    await page.waitForSelector('text=👍 aprovado', { timeout: 15000 });
    check(results, '👍 marca como aprovado', true);
    await perguntar('e as rodoviárias?');
    await esperar(2);
    check(results, 'continuação da conversa ("e as rodoviárias?")', /continuação da conversa/.test(await page.locator('.chat-ia .chat-rodape').last().innerText())
      && /rodoviária|nenhuma/.test(await respostas().last().innerText()));
    await perguntar('crie um relatório com a lista de agências');
    await esperar(3);
    check(results, 'relatório abre no painel com PDF e Excel', await page.locator('.chat-art-acoes a', { hasText: 'PDF' }).isVisible()
      && await page.locator('.chat-art-acoes a', { hasText: 'Excel' }).isVisible());
    check(results, 'painel com abas dos artefatos da conversa', (await page.locator('.chat-art-abas [role="tab"]').count()) >= 2);
    const [download] = await Promise.all([page.waitForEvent('download', { timeout: 20000 }), page.locator('.chat-art-acoes a', { hasText: 'Excel' }).click()]);
    check(results, 'Excel (CSV) baixa com a sessão', fs.readFileSync(await download.path(), 'utf8').startsWith('\ufeffTipo;Nome;Cidade;Endereço'));
    await shot(page, 'assistente-01-conversa');
    // Nova conversa e histórico
    const primeira = await page.locator('.chat-conv.ativa .chat-conv-abrir').getAttribute('data-abrir');
    await page.locator('[data-nova]').click();
    await page.waitForSelector('#view_assistente .chat-boas-vindas', { timeout: 10000 });
    await page.locator(`[data-abrir="${primeira}"]`).click();
    await page.waitForFunction(() => document.querySelectorAll('#view_assistente .chat-ia .chat-texto').length === 3, null, { timeout: 15000 });
    check(results, 'histórico: reabre a conversa com as 3 respostas', true);
    // Treinar
    await page.locator('[data-treinar]').click();
    await page.waitForSelector('.chat-treino .chat-numeros', { timeout: 15000 });
    check(results, 'treino mostra números do histórico e exportação do dataset', /aprovadas/.test(await page.locator('.chat-numeros').innerText())
      && await page.locator('.chat-treino a', { hasText: 'dataset' }).isVisible());
    await page.fill('#chatTermo', 'em débito');
    await page.fill('#chatSignifica', 'vencida');
    await page.locator('#chatTermoForm button[type=submit]').click();
    await page.waitForFunction(() => /Aprendido/.test(document.getElementById('chatTermoStatus')?.textContent || ''), null, { timeout: 15000 });
    check(results, 'ensinar termo pelo painel de treino', true);
    await shot(page, 'assistente-02-treino');
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
