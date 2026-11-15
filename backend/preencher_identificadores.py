"""Preenche o código do cliente/contrato das notas recebidas já gravadas (situações 3 a 5), uma vez.

Para cada nota com PDF ainda sem `identificadoresCliente`: lê o texto pelo serviço OCR (o mesmo do WF-08),
guarda os identificadores na nota (só acrescenta esse campo) e, se a nota já está ASSOCIADA, ensina o código
ao provedor daquele local (mesma regra da associação: código que já está em outro local não é guardado).
Pode rodar de novo sem duplicar nada. Sem --gravar, só mostra o que faria.

Uso, dentro do container da API:  python -m backend.preencher_identificadores [--gravar]
"""
from __future__ import annotations

import json
import sys
import urllib.request

from backend import database, identificadores
from backend.database import aprender_codigos_cliente, get_connection

OCR_URL = "http://ocr:5002/extract"
PASTA = database.DB_PATH.parent / "notas_recebidas"


def texto_do_pdf(caminho) -> str:
    pedido = urllib.request.Request(OCR_URL, data=caminho.read_bytes(), headers={"Content-Type": "application/pdf"})
    with urllib.request.urlopen(pedido, timeout=300) as resposta:  # noqa: S310 (serviço interno fixo)
        return str(json.loads(resposta.read().decode("utf-8")).get("text") or "")


def main(gravar: bool) -> None:
    conn = get_connection()
    try:
        notas = conn.execute(
            "SELECT id, status, entidade_id, arquivo_storage, dados_json FROM notas_recebidas WHERE arquivo_storage LIKE '%.pdf'"
        ).fetchall()
    finally:
        conn.close()
    resumo = {"lidas": 0, "comCodigo": 0, "aprendidos": 0, "emOutroLocal": 0, "falhas": 0}
    for nota in notas:
        dados = json.loads(nota["dados_json"] or "{}")
        if "identificadoresCliente" in dados:
            continue
        caminho = PASTA / nota["arquivo_storage"]
        try:
            ids = identificadores.ler(texto_do_pdf(caminho))
        except (OSError, ValueError) as erro:
            resumo["falhas"] += 1
            print(f"falha {nota['id']}: {str(erro)[:80]}")
            continue
        resumo["lidas"] += 1
        if ids:
            resumo["comCodigo"] += 1
        print(f"{nota['status']:<22} {str(dados.get('emissorNome') or '')[:28]:<28} {', '.join(i['tipo'] + '=' + i['valor'] for i in ids)[:90]}")
        if not gravar:
            continue
        conn = get_connection()
        try:
            atual = json.loads(conn.execute("SELECT dados_json FROM notas_recebidas WHERE id = ?", (nota["id"],)).fetchone()[0] or "{}")
            atual["identificadoresCliente"] = ids
            conn.execute("UPDATE notas_recebidas SET dados_json = ? WHERE id = ?", (json.dumps(atual, ensure_ascii=False), nota["id"]))
            conn.commit()
        finally:
            conn.close()
        if nota["status"] == "ASSOCIADA" and nota["entidade_id"] and ids:
            r = aprender_codigos_cliente(nota["entidade_id"], str(dados.get("emissorNome") or ""), ids)
            resumo["aprendidos"] += len(r["adicionados"])
            resumo["emOutroLocal"] += len(r["emOutroLocal"])
            if r["adicionados"] or r["emOutroLocal"]:
                print(f"   -> provedor do local: guardados {r['adicionados']} · em outro local {r['emOutroLocal']}")
    print(("GRAVADO " if gravar else "SIMULAÇÃO ") + json.dumps(resumo, ensure_ascii=False))


if __name__ == "__main__":
    main("--gravar" in sys.argv)
