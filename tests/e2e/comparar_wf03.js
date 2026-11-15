// Executa o código atual do nó "Identificar dados da fatura" (WF-03) sobre os textos OCR salvos.
// Saída: out/wf03_antigo.json  { arquivo: campos }
const fs = require('fs');
const path = require('path');

const wf = JSON.parse(fs.readFileSync(path.join(__dirname, '..', '..', process.argv[2] || 'n8n_workflow_extrair_fatura_pdf.json'), 'utf8'));
const node = wf.nodes.find((n) => n.name === 'Identificar dados da fatura');
if (!node) throw new Error('nó do WF-03 não encontrado');
const pasta = path.join(__dirname, '.data-test', 'ocr_textos');
const saida = {};
for (const nome of fs.readdirSync(pasta)) {
  const ocr = JSON.parse(fs.readFileSync(path.join(pasta, nome), 'utf8'));
  const $json = { text: ocr.text || '', ocrUsado: ocr.ocrUsado };
  const $ = () => ({ first: () => ({ json: { query: {} } }) });
  // eslint-disable-next-line no-new-func
  const fn = new Function('$json', '$', node.parameters.jsCode);
  try { saida[nome] = fn($json, $).json; } catch (e) { saida[nome] = { erro: e.message }; }
}
fs.writeFileSync(path.join(__dirname, 'out', 'wf03_antigo.json'), JSON.stringify(saida, null, 1));
console.log(`WF-03 antigo: ${Object.keys(saida).length} textos processados`);
