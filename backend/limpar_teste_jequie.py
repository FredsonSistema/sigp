"""Remove os registros criados pelo e-mail de teste de Jequié (confirmado pelo usuário em 15/11/2026: não é real).

Registros: nota recebida associada (FATURA_05_JEQUIE_6001005_JET_FIBRA.pdf), nota recebida "teste",
nota lançada nº 6001005, fatura anexada, conciliações, feedbacks e o provedor "JEQUIE FIBRA NET LTDA"
do cadastro da Rodoviária de Jequié; e os arquivos guardados desses registros.
Sem --apagar, só lista o que seria removido. Faça backup antes (Painel da IA ou /api/saude/banco/backup).
Uso, dentro do container da API:  python -m backend.limpar_teste_jequie [--apagar]
"""
from __future__ import annotations

import json
import sys

from backend import database

NOTAS_RECEBIDAS = ("nrec-4a8c41c0a8304da9acfec1aba23c88bb", "nrec-52d2d6241d5640708dd8ab2aa8d4a10b")
NOTA_LANCADA = "gmail-19107713c59545d880b7a6f73d717a77"
FATURA = "gmail-gmail-19107713c59545d880b7a6f73d717a77"
PROVEDOR = "JEQUIE FIBRA NET LTDA"
IDS = (*NOTAS_RECEBIDAS, NOTA_LANCADA, FATURA)


def main(apagar: bool) -> None:
    conn = database.get_connection()
    data = database.DB_PATH.parent
    try:
        conn.execute("BEGIN IMMEDIATE")
        # Referências em qualquer tabela (para não deixar nada solto).
        tabelas = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
        for tabela in tabelas:
            for coluna in [r[1] for r in conn.execute(f"PRAGMA table_info({tabela})")]:
                for i in IDS:
                    n = conn.execute(f"SELECT COUNT(*) FROM {tabela} WHERE CAST({coluna} AS TEXT) LIKE ?", (f"%{i}%",)).fetchone()[0]  # noqa: S608
                    if n:
                        print(f"referência: {tabela}.{coluna} -> {i[:28]} ({n})")
        arquivos = [data / "notas_recebidas" / r[0] for r in conn.execute(
            f"SELECT arquivo_storage FROM notas_recebidas WHERE id IN ({','.join('?' * len(NOTAS_RECEBIDAS))}) AND arquivo_storage != ''",
            NOTAS_RECEBIDAS)]
        arquivos += [data / "faturas" / r[0] for r in conn.execute(
            "SELECT arquivo_storage FROM faturas_locais WHERE id = ? AND arquivo_storage != ''", (FATURA,))]
        locais = conn.execute("SELECT id, nome, provedores_json FROM locais WHERE provedores_json LIKE ?", (f"%{PROVEDOR}%",)).fetchall()
        print("arquivos:", [a.name for a in arquivos])
        print("locais com o provedor:", [r["nome"] for r in locais])
        if not apagar:
            conn.rollback()
            print("SIMULAÇÃO: nada foi apagado.")
            return
        apagados = {}
        apagados["conciliacoes"] = conn.execute("DELETE FROM conciliacoes WHERE nota_lancada_id = ?", (NOTA_LANCADA,)).rowcount
        apagados["extracao_feedback"] = conn.execute(
            f"DELETE FROM extracao_feedback WHERE nota_recebida_id IN ({','.join('?' * len(NOTAS_RECEBIDAS))})", NOTAS_RECEBIDAS).rowcount
        apagados["faturas_locais"] = conn.execute("DELETE FROM faturas_locais WHERE id = ? OR nota_lancada_id = ?", (FATURA, NOTA_LANCADA)).rowcount
        apagados["notas_lancadas"] = conn.execute("DELETE FROM notas_lancadas WHERE id = ?", (NOTA_LANCADA,)).rowcount
        apagados["notas_recebidas"] = conn.execute(
            f"DELETE FROM notas_recebidas WHERE id IN ({','.join('?' * len(NOTAS_RECEBIDAS))})", NOTAS_RECEBIDAS).rowcount
        apagados["analises"] = conn.execute("DELETE FROM analises WHERE referencia = ?", (NOTA_LANCADA,)).rowcount
        apagados["provedores"] = 0
        apagados["notasNoLocal"] = 0
        for local in conn.execute("SELECT id, provedores_json, dados_json FROM locais WHERE provedores_json LIKE ? OR dados_json LIKE ?",
                                  (f"%{PROVEDOR}%", f"%{NOTA_LANCADA}%")).fetchall():
            provedores = json.loads(local["provedores_json"] or "[]")
            restantes = [p for p in provedores if not (isinstance(p, dict) and str(p.get("nome") or "").strip().upper() == PROVEDOR)]
            apagados["provedores"] += len(provedores) - len(restantes)
            dados = json.loads(local["dados_json"] or "{}")
            notas = dados.get("notasFiscais") or []
            dados["notasFiscais"] = [n for n in notas if NOTA_LANCADA not in json.dumps(n, ensure_ascii=False)]
            apagados["notasNoLocal"] += len(notas) - len(dados["notasFiscais"])
            conn.execute("UPDATE locais SET provedores_json = ?, dados_json = ?, updated_at = ? WHERE id = ?",
                         (json.dumps(restantes, ensure_ascii=False), json.dumps(dados, ensure_ascii=False), database._now(), local["id"]))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    for arquivo in arquivos:
        arquivo.unlink(missing_ok=True)
    print("APAGADO", json.dumps({**apagados, "arquivos": len(arquivos)}, ensure_ascii=False))


if __name__ == "__main__":
    main("--apagar" in sys.argv)
