// Fatura PDF + XML da nota (como o WF-08 envia): cartão mostra o XML, associa e o XML aparece na nota do local.
// Usa a API de TESTE. O XML é lido aqui pela mesma lib do n8n (n8n/lib/xml_fiscal.js).
const fs = require('fs');
const path = require('path');
const { API_TEST_URL, launch, shot, check, loginFresh, abrirNota } = require('./lib');
const XF = require('../../n8n/lib/xml_fiscal.js');

const ARQUIVO = path.join(__dirname, '..', '..', 'docs', 'XML para testes', '01-ITABUNA-7001001-CONNECT-FIBRA.xml');

(async () => {
  const results = [];
  const { browser, context } = await launch();
  const page = await context.newPage();
  page.on('dialog', (d) => d.accept());
  try {
    await loginFresh(page);
    // Chave única por execução: a mesma nota paga duas vezes (mesma chave, valor e data) é duplicidade real.
    const original = fs.readFileSync(ARQUIVO, 'utf8');
    const chaveBase = XF.lerXmlFiscal(original).chave;
    const xmlTexto = original.split(chaveBase).join(chaveBase.slice(0, -13) + String(Date.now()).slice(-13));
    const lido = XF.lerXmlFiscal(xmlTexto);
    // Leitura do PDF com valor diferente (100) e sem número: o XML deve prevalecer e a divergência aparecer.
    const dados = { ...XF.aplicarPrioridadeXml({ emissorNome: 'CONNECT', numero: '999999999', valorTotal: 100, dataVencimento: lido.dataVencimento }, lido), xmlFiscal: lido };
    const sufixo = Date.now();
    const { local, item } = await page.evaluate(async ({ api, xmlTexto, dados, sufixo }) => {
      const local = (await (await fetch(`${api}/api/locais/agencia/item`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nome: `Agência XML ${sufixo}`, cidade: 'Itabuna' }),
      })).json()).item;
      const form = new FormData();
      form.append('gmailMessageId', `msg-xml-ui-${sufixo}`);
      form.append('gmailAttachmentId', 'a1');
      form.append('assunto', 'Fatura CONNECT FIBRA + NFS-e');
      form.append('dadosExtracao', JSON.stringify(dados));
      form.append('xml', new Blob([xmlTexto], { type: 'application/xml' }), 'nfse-7001001.xml');
      form.append('arquivo', new Blob(['%PDF-1.4 fatura de teste'], { type: 'application/pdf' }), 'fatura-7001001.pdf');
      const item = (await (await fetch(`${api}/api/notas-recebidas`, { method: 'POST', body: form })).json()).item;
      return { local, item };
    }, { api: API_TEST_URL, xmlTexto, dados, sufixo });
    check(results, 'API recebeu PDF + XML', Boolean(item && item.xmlUrl), item && item.xmlUrl);
    await page.evaluate((l) => {
      const list = JSON.parse(localStorage.getItem('ti_agencias_v1') || '[]');
      list.push({ ...l, notasFiscais: [] });
      localStorage.setItem('ti_agencias_v1', JSON.stringify(list));
    }, local);

    await page.evaluate(() => document.querySelector('[data-view="notas-recebidas"]').click());
    const card = await abrirNota(page, item.id);
    const info = await card.locator('[data-role="xml-info"]').innerText();
    check(results, 'cartão mostra o XML (tipo, número, emissor, valor)', /NFS-e/.test(info) && /7001001/.test(info) && /CONNECT FIBRA TELECOM LTDA/.test(info) && /89,90/.test(info), info.split('\n')[1]);
    check(results, 'cartão avisa a divergência PDF × XML (vale o XML)', /Valor:.*PDF.*100,00.*XML.*89,90/.test(info.replace(/\s+/g, ' ')), info.replace(/\s+/g, ' ').slice(-140));
    check(results, 'campos já vêm com os valores do XML', await card.locator('[data-role="number"]').inputValue() === '7001001'
      && Number(String(await card.locator('[data-role="amount"]').inputValue()).replace(',', '.')) === 89.9);
    const href = await card.locator('[data-role="xml-info"] a', { hasText: 'Baixar XML' }).getAttribute('href');
    const baixado = await page.evaluate(async (u) => (await fetch(u)).text(), href);
    check(results, '"Baixar XML" devolve o arquivo original', baixado === xmlTexto);
    check(results, 'PDF continua disponível', await card.locator('a', { hasText: 'Abrir / imprimir PDF' }).count() === 1);
    await card.scrollIntoViewIfNeeded();
    await shot(page, 'xml-01-cartao');

    await card.locator('[data-role="type"]').selectOption('agencia');
    await card.locator('[data-role="location"]').selectOption(local.id);
    await card.locator('[data-action="compare"]').click();
    await card.locator('[data-action="commit"]').waitFor({ timeout: 15000 });
    await card.locator('[data-action="commit"]').click();
    await page.waitForFunction((id) => {
      const l = JSON.parse(localStorage.getItem('ti_agencias_v1') || '[]').find((x) => x.id === id);
      return l && (l.notasFiscais || []).length > 0;
    }, local.id, { timeout: 20000 });
    const nota = await page.evaluate((id) => JSON.parse(localStorage.getItem('ti_agencias_v1')).find((x) => x.id === id).notasFiscais[0].notaLancada, local.id);
    check(results, 'nota do local com número e valor do XML', nota.numero === '7001001' && Number(nota.valorTotal) === 89.9, JSON.stringify([nota.numero, nota.valorTotal]));
    check(results, 'nota do local tem os itens de serviço do XML', (nota.servicos || []).some((s) => /FIBRA OPTICA/.test(s.descricao)));
    const xmlDaNota = await page.evaluate(async ({ api, u }) => (await fetch(`${api}${u}`)).text(), { api: API_TEST_URL, u: nota.xmlUrl || '/x' });
    check(results, 'XML guardado na nota lançada do local', xmlDaNota === xmlTexto);

    check(results, 'cópia no navegador usa o que a API gravou (chave lida tem prioridade)', nota.chave === lido.chave, nota.chave);

    // Bug 14/11/2026: cópia antiga no navegador (gravada antes da correção) com a chave do XML e emissão com
    // horário. "Enviar para análise" regravava a nota e a API respondia "Documento duplicado".
    await page.evaluate(({ id, chave }) => {
      const list = JSON.parse(localStorage.getItem('ti_agencias_v1'));
      const l = list.find((x) => x.id === id);
      l.notasFiscais[0].notaLancada = { ...l.notasFiscais[0].notaLancada, chave, serie: '', dataEmissao: '2026-11-10T09:30:00-03:00' };
      localStorage.setItem('ti_agencias_v1', JSON.stringify(list));
    }, { id: local.id, chave: lido.chave });
    let enviado = null;
    await page.route(/:5678\/webhook\/sigp-eventos$/, async (route) => {
      enviado = JSON.parse(route.request().postData() || '{}');
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, status: 'recebido' }) });
    });

    await page.evaluate(() => document.querySelector('.tab[data-view="agencias"]').click());
    await page.evaluate((id) => openModal(id), local.id);
    await page.waitForSelector('#overlay.open');
    const link = page.locator('#overlay a', { hasText: 'XML da nota fiscal' });
    await link.first().waitFor({ timeout: 10000 });
    check(results, '"Notas fiscais do local" mostra o link do XML', await link.count() >= 1);
    await link.first().scrollIntoViewIfNeeded();
    await shot(page, 'xml-02-notas-do-local');

    await page.locator('#overlay button', { hasText: 'Enviar para análise' }).first().click();
    await page.waitForFunction(() => /Análise enviada|Não foi possível enviar|Envio cancelado/.test(document.body.innerText), null, { timeout: 30000 });
    const aviso = await page.evaluate(() => (document.body.innerText.match(/(Análise enviada[^\n]*|Não foi possível enviar[^\n]*|Envio cancelado[^\n]*)/) || [''])[0]);
    check(results, '"Enviar para análise" funciona (sem "Documento duplicado")', /Análise enviada/.test(aviso) && !/duplicado/i.test(aviso), aviso);
    check(results, 'n8n recebe a nota com número e valor do XML', enviado?.evento === 'analise_manual'
      && enviado.dados?.notaLancada?.numero === '7001001' && Number(enviado.dados.notaLancada.valor_total) === 89.9,
    JSON.stringify(enviado?.dados?.notaLancada || {}).slice(0, 160));
    const gravada = await page.evaluate(async ({ api, u }) => (await (await fetch(`${api}${u}`)).json()), { api: API_TEST_URL, u: '/api/notas/lancadas' });
    const g = (gravada.items || []).find((x) => x.id === nota.id) || {};
    check(results, 'API manteve a chave lida e a emissão sem horário', g.chave === lido.chave && g.data_emissao === '2026-11-10', JSON.stringify([g.chave, g.data_emissao]));
    await shot(page, 'xml-03-enviado-para-analise');

    // Bug 14/11/2026 (2): "Marcar como pago" + salvar o local dava 409 (série vazia na cópia antiga).
    await page.locator('#overlay button', { hasText: 'Marcar como pago' }).first().click();
    await page.waitForSelector('#nfLocalEditorOverlay.open');
    const pre = await page.evaluate(() => ({
      numero: document.querySelector('#nfLocalEditorFields [data-nf-field="numero"]').value,
      valorPago: document.querySelector('#nfLocalEditorFields [data-nf-field="valorPago"]').value,
      servicos: document.querySelectorAll('#nfLocalServiceItems .nf-local-service-item').length,
    }));
    check(results, 'pagamento já vem com número, valor e serviço da nota lançada', pre.numero === '7001001' && Number(pre.valorPago) === 89.9 && pre.servicos === 1, JSON.stringify(pre));
    await page.selectOption('#nfLocalServiceItems [data-service-field="classificacao"]', 'CONTRATADO');
    await shot(page, 'xml-04-pagamento');
    await page.locator('#nfLocalEditorForm button[type=submit]').click();
    await page.waitForFunction(() => !document.getElementById('nfLocalEditorOverlay').classList.contains('open'), null, { timeout: 10000 });
    await page.click('#form button[type=submit]');
    await page.waitForFunction(() => !document.getElementById('overlay').classList.contains('open'), null, { timeout: 20000 });
    await page.waitForTimeout(2500);
    const toast = await page.evaluate(() => document.body.innerText);
    const erroLinha = await page.evaluate((id) => (JSON.parse(localStorage.getItem('ti_agencias_v1')).find((x) => x.id === id).notasFiscais || []).map((n) => n.erroSincronizacao || '').join(' | '), local.id);
    check(results, 'salvar o local não avisa falha de sincronização', !/não foram sincronizadas/.test(toast) && !erroLinha.trim(), erroLinha);
    const conc = await page.evaluate(async ({ api, id }) => {
      const r = await (await fetch(`${api}/api/notas/conciliacoes`)).json();
      return (r.items || []).filter((c) => c.nota_lancada_id === id).map((c) => c.status);
    }, { api: API_TEST_URL, id: nota.id });
    check(results, 'conciliação fecha em MATCH (nota + pagamento + fatura PDF)', conc.includes('MATCH'), JSON.stringify(conc));
  } catch (error) {
    check(results, 'execução do teste', false, error.message.split('\n')[0]);
    await shot(page, 'xml-erro').catch(() => {});
  } finally {
    await browser.close();
  }
  const falhas = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - falhas}/${results.length} verificações passaram.`);
  process.exit(falhas ? 1 : 0);
})();
