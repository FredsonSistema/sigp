// Utilitários dos testes de navegador (Playwright + Edge instalado; sem baixar navegador).
// Os testes usam a interface real (porta 8000) apontando para uma API de TESTE (porta 5011,
// com cópia dos dados). Nunca apontam para a API real (porta 5001).
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright-core');

const APP_URL = process.env.SIGP_E2E_APP || 'http://127.0.0.1:8000/agencias.html';
const API_TEST_URL = process.env.SIGP_E2E_API || 'http://127.0.0.1:5011';
const API_TEST_KEY = 'chave-de-teste-e2e';
const OUT_DIR = path.join(__dirname, 'out');
fs.mkdirSync(OUT_DIR, { recursive: true });

async function launch({ headless = true } = {}) {
  if (API_TEST_URL.includes(':5001')) throw new Error('Os testes não podem apontar para a API real (5001).');
  const browser = await chromium.launch({ channel: 'msedge', headless });
  const context = await browser.newContext({ viewport: { width: 1360, height: 900 } });
  // Só define a URL da API de teste se ainda não houver valor (não sobrescreve ao recarregar).
  // Entrada de notas SEMPRE direto na API de teste: pelo n8n, o WF-01/02 gravaria na API REAL.
  await context.addInitScript((url) => {
    try {
      if (!localStorage.getItem('sigp_nfse_backend_url')) localStorage.setItem('sigp_nfse_backend_url', url);
      localStorage.setItem('sigp_modo_entrada', 'api');
    } catch (e) { /* ignora */ }
  }, API_TEST_URL);
  // Trava de segurança: bloqueia a API real e todo webhook do n8n que não seja só de extração.
  const bloqueados = [];
  await context.route(/^https?:\/\/(127\.0\.0\.1|localhost):(5001|5678)\//, (route) => {
    const url = route.request().url();
    if (/:5678\/webhook\/sigp-faturas-pdf(\?|$)/.test(url)) return route.continue();
    bloqueados.push(url);
    console.log(`BLOQUEADO (protege dados reais): ${route.request().method()} ${url}`);
    return route.abort();
  });
  context.bloqueados = bloqueados;
  return { browser, context };
}

async function shot(page, name) {
  const file = path.join(OUT_DIR, `${name}.png`);
  await page.screenshot({ path: file, fullPage: false });
  return file;
}

const visible = (page, selector) => page.evaluate((sel) => {
  const el = document.querySelector(sel);
  if (!el) return false;
  const st = getComputedStyle(el);
  const r = el.getBoundingClientRect();
  return st.display !== 'none' && st.visibility !== 'hidden' && r.width > 0 && r.height > 0;
}, selector);

function check(results, name, ok, detail = '') {
  results.push({ name, ok: Boolean(ok), detail });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? '  — ' + detail : ''}`);
}

// Cria o acesso de teste (navegador novo), informa a chave da API de teste e espera o app abrir.
async function loginFresh(page) {
  await page.goto(APP_URL);
  await page.waitForSelector('#authScreen');
  await page.fill('#su_user', 'teste');
  await page.fill('#su_pass', 'senha1234');
  await page.fill('#su_pass2', 'senha1234');
  await page.click('#setupForm button[type=submit]');
  await page.waitForFunction(() => /recusou/i.test(document.getElementById('apiKeySetupStatus').textContent), null, { timeout: 15000 });
  await page.fill('#apiKeySetupInput', API_TEST_KEY);
  await page.click('#apiKeySetupForm button[type=submit]');
  await page.waitForFunction(() => getComputedStyle(document.querySelector('#appRoot')).display !== 'none', null, { timeout: 20000 });
}

// PDF mínimo com texto (dados FICTÍCIOS), sem dependências externas.
// Notas recebidas: a nota pode estar numa lista recolhida (accordion). Espera ela existir e abre lista, e-mail e partes.
async function abrirNota(page, id, timeout = 20000) {
  await page.waitForFunction((i) => window.SIGP_NOTAS_RECEBIDAS?.abrir
    && [...document.querySelectorAll('#notasRecebidasLista [data-note-id]')].some((el) => el.dataset.noteId === i), id, { timeout });
  await page.evaluate((i) => window.SIGP_NOTAS_RECEBIDAS.abrir(i), id);
  const card = page.locator(`#notasRecebidasLista [data-note-id="${id}"]`);
  await card.locator('[data-action="toggle-note"]').waitFor({ timeout });
  return card;
}

function makePdf(lines, file) {
  const esc = (s) => s.replace(/\\/g, '\\\\').replace(/\(/g, '\\(').replace(/\)/g, '\\)');
  const body = ['BT', '/F1 12 Tf', '50 780 Td', '16 TL', ...lines.map((l) => `(${esc(l)}) Tj T*`), 'ET'].join('\n');
  const objs = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>',
    `<< /Length ${Buffer.byteLength(body, 'latin1')} >>\nstream\n${body}\nendstream`,
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>',
  ];
  let out = '%PDF-1.4\n';
  const offsets = [];
  objs.forEach((o, i) => { offsets.push(Buffer.byteLength(out, 'latin1')); out += `${i + 1} 0 obj\n${o}\nendobj\n`; });
  const xref = Buffer.byteLength(out, 'latin1');
  out += `xref\n0 ${objs.length + 1}\n0000000000 65535 f \n${offsets.map((o) => String(o).padStart(10, '0') + ' 00000 n \n').join('')}`;
  out += `trailer\n<< /Size ${objs.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, Buffer.from(out, 'latin1'));
  return file;
}

module.exports = { APP_URL, API_TEST_URL, API_TEST_KEY, OUT_DIR, launch, shot, visible, check, loginFresh, makePdf, abrirNota };
