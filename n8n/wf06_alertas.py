"""Atualiza o resumo diário do WF-06 para incluir as faturas pagas (C-05).

Os alertas vêm de GET /api/alertas (agora com o tipo "pagamento": PAGO e PAGO_COM_ATRASO).
Uso, na raiz do projeto:  python n8n/wf06_alertas.py   (idempotente)
"""
import json
import shutil
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ATUAL = RAIZ / "n8n_workflow_wf06_vencimentos.json"
LEGADO = RAIZ / "n8n_workflow_wf06_vencimentos.legado.json"
if not LEGADO.exists():
    shutil.copyfile(ATUAL, LEGADO)
wf = json.loads(LEGADO.read_text(encoding="utf-8"))
no = next(n for n in wf["nodes"] if n["name"] == "Montar resumo diário")
js = no["parameters"]["jsCode"]
antigo_nomes = "DIVERGENCIA: 'Divergências', AGUARDANDO_FATURA: 'Aguardando fatura', FATURA_AUSENTE: 'Fatura não disponível' };"
antiga_ordem = "const ordem = ['VENCIDO', 'VENCE_HOJE', 'VENCE_EM_BREVE', 'DIVERGENCIA', 'AGUARDANDO_FATURA', 'FATURA_AUSENTE'];"
if antigo_nomes not in js or antiga_ordem not in js:
    raise SystemExit("O código do nó 'Montar resumo diário' mudou; revise o script.")
js = js.replace(antigo_nomes,
                "DIVERGENCIA: 'Divergências', AGUARDANDO_FATURA: 'Aguardando fatura', FATURA_AUSENTE: 'Fatura não disponível',\n"
                "  PAGO_COM_ATRASO: 'Pagas com atraso', PAGO: 'Pagas no prazo',\n"
                "  LEITURA_GMAIL_PARADA: 'Leitura do Gmail parada', FATURA_NAO_RECEBIDA: 'Faturas que não chegaram',\n"
                "  FATURA_NA_CAIXA: 'Faturas na caixa sem associar' };")
js = js.replace(antiga_ordem,
                "const ordem = ['LEITURA_GMAIL_PARADA', 'VENCIDO', 'VENCE_HOJE', 'FATURA_NAO_RECEBIDA', 'VENCE_EM_BREVE', 'DIVERGENCIA',"
                " 'FATURA_NA_CAIXA', 'PAGO_COM_ATRASO', 'AGUARDANDO_FATURA', 'FATURA_AUSENTE', 'PAGO'];")
no["parameters"]["jsCode"] = js
ATUAL.write_text(json.dumps(wf, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"WF-06 atualizado: {ATUAL.name} (anterior em {LEGADO.name})")
