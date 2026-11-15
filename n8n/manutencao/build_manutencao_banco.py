"""Gera o workflow "SIGp - Backup e manutenção do banco" (n8n_workflow_manutencao_banco.json).

Todo dia às 03:00 (e manualmente): backup consistente do SQLite com teste de restauração e rodízio
(7 diários + 4 semanais, em backend/data/backups), depois manutenção leve (optimize, analyze, checkpoint
do WAL; VACUUM só se mais de 20% do arquivo estiver livre). O n8n só chama a API; a regra fica no SIGp.
Falha no backup aparece no Painel da IA (cartão "Saúde do banco") e no log de eventos da API.

Uso, na raiz do projeto:  python n8n/manutencao/build_manutencao_banco.py
"""
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SAIDA = RAIZ / "n8n_workflow_manutencao_banco.json"
CHAVE = {"parameters": [{"name": "X-API-Key", "value": "={{ $env.SIGP_API_KEY || '' }}"}]}

codigo_resumo = r"""const backup = $('Backup do banco').first().json || {};
const manut = $json || {};
return [{ json: {
  backupOk: Boolean(backup.ok), arquivo: backup.arquivo || '', bytes: backup.bytes || 0,
  removidos: (backup.removidos || []).length, erroBackup: backup.error || '',
  manutencaoOk: Boolean(manut.ok), vacuum: Boolean(manut.vacuum), saude: manut.saude?.status || '',
  avisos: manut.saude?.avisos || [],
} }];
"""

def post(id_, nome, caminho, x):
    return {"parameters": {"method": "POST", "url": f"={{{{ $env.SIGP_API_URL + '{caminho}' }}}}", "sendHeaders": True,
                           "headerParameters": CHAVE, "options": {"timeout": 300000}},
            "id": id_, "name": nome, "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
            "position": [x, 300], "onError": "continueRegularOutput"}

nos = [
    {"parameters": {}, "id": "mb_manual", "name": "Executar manualmente", "type": "n8n-nodes-base.manualTrigger",
     "typeVersion": 1, "position": [0, 200]},
    {"parameters": {"rule": {"interval": [{"field": "days", "triggerAtHour": 3}]}}, "id": "mb_diario",
     "name": "Todo dia às 03:00", "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2, "position": [0, 400]},
    post("mb_backup", "Backup do banco", "/api/saude/banco/backup", 260),
    post("mb_manut", "Manutenção do banco", "/api/saude/banco/manutencao", 520),
    {"parameters": {"mode": "runOnceForAllItems", "jsCode": codigo_resumo}, "id": "mb_resumo", "name": "Resumo",
     "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [780, 300]},
]
liga = lambda destino: {"main": [[{"node": destino, "type": "main", "index": 0}]]}  # noqa: E731
wf = {
    "id": "sigpManutencaoBanco",
    "name": "SIGp - Backup e manutenção do banco",
    "nodes": nos,
    "connections": {
        "Executar manualmente": liga("Backup do banco"),
        "Todo dia às 03:00": liga("Backup do banco"),
        "Backup do banco": liga("Manutenção do banco"),
        "Manutenção do banco": liga("Resumo"),
    },
    "settings": {"executionOrder": "v1"},
    "active": False,
    "pinData": {},
}
SAIDA.write_text(json.dumps(wf, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Gerado: {SAIDA} ({len(nos)} nós)")
