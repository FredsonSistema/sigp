"""Aplica a regra única aos dados já existentes: cada nota lançada associada a um local preenche o
provedor desse local (nome, valor, data/dia de vencimento e fatura atual).

Uso (dentro do container da API, que tem o banco montado):
    docker exec sigp_api python -m backend.retroativo_provedores          # simulação, não grava
    docker exec sigp_api python -m backend.retroativo_provedores --gravar

As notas são aplicadas da mais antiga para a mais recente; assim a fatura atual do provedor fica sendo
a de vencimento mais recente (a regra não deixa uma fatura antiga sobrescrever a atual).
"""
from __future__ import annotations

import json
import sys

from backend.database import aplicar_fatura_no_local, get_connection
from backend.provedores import aplicar_fatura_no_provedor


def main(gravar: bool) -> int:
    conn = get_connection()
    notas = conn.execute(
        """
        SELECT n.id, n.entidade_id, n.provedor_nome, n.valor_total, n.data_vencimento, l.nome AS local_nome,
               (SELECT f.id FROM faturas_locais f WHERE f.nota_lancada_id = n.id ORDER BY f.updated_at DESC LIMIT 1) AS fatura_id
        FROM notas_lancadas n JOIN locais l ON l.id = n.entidade_id AND l.ativo = 1
        WHERE trim(coalesce(n.provedor_nome, '')) <> '' AND coalesce(n.valor_total, 0) > 0
          AND length(coalesce(n.data_vencimento, '')) = 10
        ORDER BY n.data_vencimento, n.updated_at
        """
    ).fetchall()
    simulados: dict[str, list] = {}
    for nota in notas:
        args = dict(nome=nota["provedor_nome"], valor=float(nota["valor_total"]),
                    data_vencimento=nota["data_vencimento"], fatura_id=nota["fatura_id"] or "")
        if gravar:
            resultado = aplicar_fatura_no_local(nota["entidade_id"], **args)
        else:
            if nota["entidade_id"] not in simulados:
                row = conn.execute("SELECT provedores_json FROM locais WHERE id = ?", (nota["entidade_id"],)).fetchone()
                simulados[nota["entidade_id"]] = json.loads(row["provedores_json"] or "[]")
            resultado = aplicar_fatura_no_provedor(simulados[nota["entidade_id"]], **args)
            if resultado["acao"] in ("criado", "atualizado"):
                simulados[nota["entidade_id"]] = resultado["provedores"]
        p = resultado.get("provedor") or {}
        print(f"{resultado['acao']:<10} | {nota['local_nome'][:32]:<32} | {nota['provedor_nome'][:38]:<38} | "
              f"R$ {p.get('valor', '-'):>8} | venc {p.get('dataVencimento', nota['data_vencimento'])} {resultado.get('aviso', '')}")
    conn.close()
    print(f"\n{len(notas)} nota(s) avaliada(s). {'Gravado.' if gravar else 'Simulação: nada foi gravado (use --gravar).'}")
    return 0


if __name__ == "__main__":
    sys.exit(main("--gravar" in sys.argv))
