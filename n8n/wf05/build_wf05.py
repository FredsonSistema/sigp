"""Gera o WF-05 da fase C (análise pela LLM local → SIG → decisão do gerente → SIE).

Base: n8n_workflow_wf05_eventos.legado.json (a versão anterior; criada na primeira execução).
Fonte do código dos nós: n8n/wf05/nos.js; prompts e schemas: n8n/wf05/prompt_*.md e schema_*.json.
Uso, na raiz do projeto:  python n8n/wf05/build_wf05.py
"""
import json
import re
import shutil
import uuid
from pathlib import Path

PASTA = Path(__file__).resolve().parent
RAIZ = PASTA.parents[1]
ATUAL = RAIZ / "n8n_workflow_wf05_eventos.json"
LEGADO = RAIZ / "n8n_workflow_wf05_eventos.legado.json"

if not LEGADO.exists():
    shutil.copyfile(ATUAL, LEGADO)
wf = json.loads(LEGADO.read_text(encoding="utf-8"))

# --- código dos nós (blocos em nos.js) ---
fonte = (PASTA / "nos.js").read_text(encoding="utf-8")
substituicoes = {
    "/*__PROMPT_SIG__*/": json.dumps((PASTA / "prompt_sig.md").read_text(encoding="utf-8").strip(), ensure_ascii=False),
    "/*__PROMPT_SIE__*/": json.dumps((PASTA / "prompt_sie.md").read_text(encoding="utf-8").strip(), ensure_ascii=False),
    "/*__SCHEMA_SIG__*/": json.dumps(json.loads((PASTA / "schema_sig.json").read_text(encoding="utf-8")), ensure_ascii=False),
    "/*__SCHEMA_SIE__*/": json.dumps(json.loads((PASTA / "schema_sie.json").read_text(encoding="utf-8")), ensure_ascii=False),
}
codigo = {}
for nome, corpo in re.findall(r"// ==== NO: (.+?)\n(.*?)// ==== FIM", fonte, flags=re.S):
    for marcador, valor in substituicoes.items():
        corpo = corpo.replace(marcador, valor)
    codigo[nome.strip()] = corpo.strip() + "\n"


def no(nome):
    return next(n for n in wf["nodes"] if n["name"] == nome)


def code_node(nome, posicao, nota=""):
    return {"parameters": {"jsCode": codigo[nome]}, "id": str(uuid.uuid4()), "name": nome,
            "type": "n8n-nodes-base.code", "typeVersion": 2, "position": posicao, **({"notes": nota} if nota else {})}


def ollama_node(nome, posicao):
    return {
        "parameters": {
            "method": "POST",
            "url": "={{ ($env.SIGP_OLLAMA_URL || 'http://ollama:11434') + '/api/chat' }}",
            "sendBody": True, "specifyBody": "json", "contentType": "json",
            "jsonBody": "={{ JSON.stringify($json.ollamaBody) }}",
            "options": {"timeout": 300000},
        },
        "id": str(uuid.uuid4()), "name": nome, "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
        "position": posicao, "onError": "continueRegularOutput",
        "notes": "LLM local (Ollama na rede Docker). Nenhum dado sai da rede. Falha ou demora: segue com o texto da regra.",
    }


def gravar_node(nome, posicao):
    modelo = no("Gravar análise na API (SIG)")
    novo = json.loads(json.dumps(modelo))
    novo.update({"id": str(uuid.uuid4()), "name": nome, "position": posicao})
    return novo


# --- 1) Montar análise: tudo vai para o SIG; ciclo fechado e divergência aguardam o gerente ---
montar = no("Montar análise")
js = montar["parameters"]["jsCode"]
js = js.replace("const escopo = status === 'MATCH' ? 'SIE' : 'SIG';",
                "// Fase C: toda análise vai primeiro ao SIG (gerente); a SIE recebe só o que o gerente validar.\nconst escopo = 'SIG';")
js = js.replace("dados: resumo } }];",
                "dados: { ...resumo, status, requerValidacao: ['MATCH', 'DIVERGENCIA'].includes(status), etapa: 'gerente' } } }];")
if "const escopo = 'SIG';" not in js or "requerValidacao" not in js:
    raise SystemExit("Não foi possível ajustar o nó 'Montar análise' (o código mudou).")
montar["parameters"]["jsCode"] = js

# --- 2) Novos nós entre "Escolher texto" e "Gravar análise" ---
for nome in ("Gravar análise na API (SIG/SIE)", "Montar mensagem", "Gmail - relatório", "Telegram - alerta",
             "WhatsApp - alerta (Evolution API)"):
    no(nome)["position"][0] += 880
no("Montar mensagem")["parameters"]["jsCode"] = codigo["Montar mensagem"]
no("Gravar análise na API (SIG/SIE)")["name"] = "Gravar análise na API (SIG)"
se_llm = json.loads(json.dumps(no("Fatura pronta para parecer?")))
se_llm.update({"id": str(uuid.uuid4()), "name": "Analisar com a LLM local?", "position": [1300, 300]})
se_llm["parameters"]["conditions"]["conditions"][0]["leftValue"] = "={{ $json.precisaLLM }}"
wf["nodes"] += [
    code_node("Preparar pedido à LLM (SIG)", [1080, 300], "MATCH (3 evidências) e DIVERGENCIA vão à LLM; os demais seguem com a regra."),
    se_llm,
    ollama_node("LLM local — análise gerencial (Ollama)", [1520, 180]),
    code_node("Juntar análise da LLM", [1740, 180]),
    # --- 3) Etapa executiva: decisão do gerente → LLM → SIE ---
    code_node("Montar etapa executiva", [420, 760], "Evento decisao_gerente do SIGp. Só VALIDADA/CORRIGIDA seguem para a SIE."),
    ollama_node("LLM local — resumo executivo (Ollama)", [640, 760]),
    code_node("Juntar resumo executivo", [860, 760]),
    gravar_node("Gravar análise executiva (SIE)", [1080, 760]),
]

# --- conexões ---
c = wf["connections"]
c["Gravar análise na API (SIG)"] = c.pop("Gravar análise na API (SIG/SIE)")
c["Escolher texto"] = {"main": [[{"node": "Preparar pedido à LLM (SIG)", "type": "main", "index": 0}]]}
c["Preparar pedido à LLM (SIG)"] = {"main": [[{"node": "Analisar com a LLM local?", "type": "main", "index": 0}]]}
c["Analisar com a LLM local?"] = {"main": [
    [{"node": "LLM local — análise gerencial (Ollama)", "type": "main", "index": 0}],
    [{"node": "Gravar análise na API (SIG)", "type": "main", "index": 0}],
]}
c["LLM local — análise gerencial (Ollama)"] = {"main": [[{"node": "Juntar análise da LLM", "type": "main", "index": 0}]]}
c["Juntar análise da LLM"] = {"main": [[{"node": "Gravar análise na API (SIG)", "type": "main", "index": 0}]]}
c["Eventos da API SIGp"]["main"][0].append({"node": "Montar etapa executiva", "type": "main", "index": 0})
c["Montar etapa executiva"] = {"main": [[{"node": "LLM local — resumo executivo (Ollama)", "type": "main", "index": 0}]]}
c["LLM local — resumo executivo (Ollama)"] = {"main": [[{"node": "Juntar resumo executivo", "type": "main", "index": 0}]]}
c["Juntar resumo executivo"] = {"main": [[{"node": "Gravar análise executiva (SIE)", "type": "main", "index": 0}]]}

wf["name"] = "SIGp - WF-05 Eventos: análise LLM local, SIG (gerente) e SIE (executivo)"
ATUAL.write_text(json.dumps(wf, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"WF-05 gerado: {ATUAL.name} ({len(wf['nodes'])} nós). Base: {LEGADO.name}")
