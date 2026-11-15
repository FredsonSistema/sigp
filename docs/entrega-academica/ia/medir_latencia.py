"""Parte 2 — latência e custo iniciais medidos (CPU, sem GPU).

Mede, com 1 aquecimento + N chamadas:
  1. Ollama direto (dentro do container sigp_ollama): qwen2.5:0.5b e qwen2.5:3b, mesmo prompt de classificação,
     temperatura 0. Usa os tempos do próprio Ollama (carga, prompt, geração) e tokens por segundo.
  2. API acadêmica de ponta a ponta (API -> SQL Server/RLS -> RAG -> Qwen 0.5B): tempo total por requisição.
Custo: o modelo é local, sem cobrança por token. O custo por 1.000 usos é expresso em tempo de CPU; a energia
só é calculada se SIGP_WATTS (potência média medida da máquina) e SIGP_TARIFA_KWH forem informados.
Saída: docs/entrega-academica/sqlserver/evidence/parte2/latencia-custo.json

Uso, na raiz:  SIGP_ACADEMIC_AI_KEY=... python docs/entrega-academica/ia/medir_latencia.py
"""
from __future__ import annotations

import json
import os
import platform
import statistics
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

RAIZ = Path(__file__).resolve().parents[3]
SAIDA = RAIZ / "docs" / "entrega-academica" / "sqlserver" / "evidence" / "parte2" / "latencia-custo.json"
N = int(os.environ.get("SIGP_N", "10"))
PROMPT = (
    "Classifique a cobrança como CONTRATADO, DIVERGENTE ou REVISAR. Responda só JSON {\"classification\": \"...\"}.\n"
    "Cobrança: link principal fibra 300 Mbps, R$ 450,00. Provedor: Conecta Alfa Fictícia. "
    "Evidência: contrato vigente inclui link principal fibra por R$ 450,00 ao mês."
)


def resumo(valores: list[float]) -> dict:
    ordenados = sorted(valores)
    p95 = ordenados[min(len(ordenados) - 1, round(0.95 * (len(ordenados) - 1)))]
    return {"n": len(valores), "mediana": round(statistics.median(valores), 1), "p95": round(p95, 1),
            "media": round(statistics.mean(valores), 1), "min": round(min(valores), 1), "max": round(max(valores), 1)}


def ollama(modelo: str) -> dict:
    corpo = json.dumps({"model": modelo, "prompt": PROMPT, "stream": False, "options": {"temperature": 0, "num_predict": 40}})
    total, geracao_tps, prompt_ms, carga_ms = [], [], [], []
    for i in range(N + 1):
        inicio = time.perf_counter()
        # O Ollama não expõe porta no Windows: a chamada sai do container da IA acadêmica (mesma rede Docker).
        r = subprocess.run(
            ["docker", "exec", "-i", "sigp_academic_ai", "python", "-c",
             "import sys,urllib.request as u;r=u.Request('http://ollama:11434/api/generate',data=sys.stdin.buffer.read(),"
             "headers={'Content-Type':'application/json'});print(u.urlopen(r,timeout=600).read().decode())"],
            input=corpo, capture_output=True, text=True, encoding="utf-8", timeout=600,
        )
        decorrido = (time.perf_counter() - inicio) * 1000
        dados = json.loads(r.stdout)
        if i == 0:
            primeira_carga = round(dados.get("load_duration", 0) / 1e6, 1)
            continue  # aquecimento (inclui carregar o modelo na memória)
        total.append(dados["total_duration"] / 1e6)
        carga_ms.append(dados.get("load_duration", 0) / 1e6)
        prompt_ms.append(dados.get("prompt_eval_duration", 0) / 1e6)
        geracao_tps.append(dados["eval_count"] / (dados["eval_duration"] / 1e9))
    return {"modelo": modelo, "carga_na_primeira_chamada_ms": primeira_carga, "total_ms": resumo(total),
            "prompt_ms": resumo(prompt_ms), "geracao_tokens_por_s": resumo(geracao_tps)}


def api_academica() -> dict:
    chave = os.environ.get("SIGP_ACADEMIC_AI_KEY", "")
    if not chave:
        return {"erro": "SIGP_ACADEMIC_AI_KEY não informado; não medido."}
    corpo = json.dumps({"invoice": {"provider": "Conecta Alfa Fictícia", "description": "link principal fibra 300 Mbps",
                                    "amount": "450.00", "due_date": "2026-11-10"}}).encode("utf-8")
    tempos = []
    for i in range(N + 1):
        req = Request("http://127.0.0.1:5010/api/analyze", data=corpo, method="POST",
                      headers={"Content-Type": "application/json", "X-API-Key": chave})
        inicio = time.perf_counter()
        with urlopen(req, timeout=600) as resp:
            json.loads(resp.read())
        if i:
            tempos.append((time.perf_counter() - inicio) * 1000)
    return {"descricao": "API -> SQL Server (RLS) -> RAG lexical -> qwen2.5:0.5b; decisão por regra", "total_ms": resumo(tempos)}


def main() -> None:
    resultado = {
        "executado_em_utc": datetime.now(timezone.utc).isoformat(),
        "maquina": {"sistema": platform.platform(), "cpus_logicas": os.cpu_count(), "gpu": "nenhuma (CPU)"},
        "metodo": f"1 aquecimento + {N} chamadas medidas por alvo; temperatura 0; mesmo prompt",
        "ollama": [ollama("qwen2.5:0.5b"), ollama("qwen2.5:3b")],
        "api_academica_ponta_a_ponta": api_academica(),
    }
    custo = {"cobranca_por_token": 0, "observacao": "Modelo local (Ollama/CPU); não há API paga."}
    for alvo in resultado["ollama"]:
        segundos = alvo["total_ms"]["mediana"] / 1000
        custo[f"tempo_cpu_por_1000_usos_{alvo['modelo']}"] = f"{round(segundos * 1000 / 60, 1)} min"
    watts, tarifa = os.environ.get("SIGP_WATTS"), os.environ.get("SIGP_TARIFA_KWH")
    if watts and tarifa:
        for alvo in resultado["ollama"]:
            kwh = float(watts) * (alvo["total_ms"]["mediana"] / 1000) * 1000 / 3_600_000
            custo[f"energia_por_1000_usos_{alvo['modelo']}"] = {"kwh": round(kwh, 4), "reais": round(kwh * float(tarifa), 4)}
    else:
        custo["energia"] = "Não calculada: informe SIGP_WATTS (medido) e SIGP_TARIFA_KWH para estimar."
    resultado["custo"] = custo
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
