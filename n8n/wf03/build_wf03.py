"""Gera o WF-03 (B-02): a extração dos campos roda no n8n, com o extrator de n8n/lib/extrator.js.

Fluxo:  Receber PDF → OCR local → Identificar dados da fatura (extrator do n8n, nó Code)
                                   ├─ ok   → Devolver campos extraídos
                                   └─ erro → Contingência: extrator do SIGp (POST /api/extracao/texto) → Devolver
A resposta é a mesma nos dois caminhos (paridade em tests/n8n/paridade_extrator.py); o campo "extrator"
diz qual respondeu. Versão anterior, com regex próprias, em n8n_workflow_extrair_fatura_pdf.legado.json.
Rode de novo sempre que n8n/lib/extrator.js mudar (o código da lib é colado no nó).

Uso, na raiz do projeto:  python n8n/wf03/build_wf03.py
"""
import json
import shutil
import uuid
from pathlib import Path

PASTA = Path(__file__).resolve().parent
RAIZ = PASTA.parents[1]
ATUAL = RAIZ / "n8n_workflow_extrair_fatura_pdf.json"
LEGADO = RAIZ / "n8n_workflow_extrair_fatura_pdf.legado.json"
LIB = RAIZ / "n8n" / "lib" / "extrator.js"

OCR = "Extrair texto e aplicar OCR local"
RESPOSTA = "Devolver campos extraídos"
CODIGO = "Identificar dados da fatura (extrator do n8n)"
CONTINGENCIA = "Contingência: extrator do SIGp"
ANTIGOS = {"Identificar dados da fatura", "Identificar dados da fatura (extrator unificado do SIGp)", CODIGO, CONTINGENCIA}

if not LEGADO.exists():
    shutil.copyfile(ATUAL, LEGADO)
wf = json.loads(ATUAL.read_text(encoding="utf-8"))
posicao = next((n.get("position") for n in wf["nodes"] if n["name"] in ANTIGOS), [700, 300])
wf["nodes"] = [n for n in wf["nodes"] if n["name"] not in ANTIGOS]

codigo = LIB.read_text(encoding="utf-8") + """
// ---- nó: Identificar dados da fatura (WF-03) ----
const query = $('Receber PDF').first().json.query || {};
return $input.all().map((item) => ({
  json: ExtratorSIGp.extrairDoTexto({
    texto: String(item.json.text || ''),
    ocrUsado: Boolean(item.json.ocrUsado),
    provedorEsperado: query.provedorEsperado || '',
    valorEsperado: Number(query.valorEsperado || 0),
    vencimentoEsperado: query.vencimentoEsperado || '',
  }),
}));
"""
query = "($('Receber PDF').first().json.query || {})"
ocr = f"$('{OCR}').first().json"
corpo = (
    f"={{{{ JSON.stringify({{ texto: String({ocr}.text || ''), ocrUsado: Boolean({ocr}.ocrUsado), "
    f"provedorEsperado: {query}.provedorEsperado || '', valorEsperado: Number({query}.valorEsperado || 0), "
    f"vencimentoEsperado: {query}.vencimentoEsperado || '' }}) }}}}"
)
wf["nodes"] += [
    {
        "parameters": {"jsCode": codigo},
        "id": str(uuid.uuid4()), "name": CODIGO, "type": "n8n-nodes-base.code", "typeVersion": 2,
        "position": posicao, "onError": "continueErrorOutput",
        "notes": "Extrator do n8n (n8n/lib/extrator.js, gerado por n8n/wf03/build_wf03.py; não edite aqui). "
                 "Linha digitável, padrão 999999999 para número vazio/inválido, emissor, CNPJ e datas. Não grava nada.",
    },
    {
        "parameters": {
            "method": "POST",
            "url": "={{ $env.SIGP_API_URL }}/api/extracao/texto",
            "sendHeaders": True,
            "headerParameters": {"parameters": [{"name": "X-API-Key", "value": "={{ $env.SIGP_API_KEY || '' }}"}]},
            "sendBody": True, "specifyBody": "json", "jsonBody": corpo,
            "options": {"timeout": 60000},
        },
        "id": str(uuid.uuid4()), "name": CONTINGENCIA, "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
        "position": [posicao[0] + 20, posicao[1] + 200],
        "notes": "Só roda se o extrator do n8n falhar. Mesmas regras, no backend do SIGp.",
    },
]
conexoes = {k: v for k, v in wf["connections"].items() if k not in ANTIGOS}
conexoes[OCR] = {"main": [[{"node": CODIGO, "type": "main", "index": 0}]]}
conexoes[CODIGO] = {"main": [[{"node": RESPOSTA, "type": "main", "index": 0}],
                             [{"node": CONTINGENCIA, "type": "main", "index": 0}]]}
conexoes[CONTINGENCIA] = {"main": [[{"node": RESPOSTA, "type": "main", "index": 0}]]}
wf["connections"] = conexoes
ATUAL.write_text(json.dumps(wf, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"WF-03 gerado: {ATUAL.name} (extrator do n8n + contingência no SIGp)")
