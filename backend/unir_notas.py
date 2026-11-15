"""Regra de recorrência aplicada aos dados existentes: une notas lançadas duplicadas da mesma cobrança.

Mesma cobrança = mesmo local + mesma empresa (``mesma_empresa``) + mesmo mês de vencimento (``competencia``).
Fica a nota mais completa (com fatura, com número/chave real, mais recente); as demais têm as referências
(notas recebidas, faturas, conciliações) passadas para ela e são removidas. Campos vazios da que fica são
completados com os das outras. Nada é feito sem ``--gravar``.

Uso (no container da API):
    docker exec sigp_api python -m backend.unir_notas            # simulação
    docker exec sigp_api python -m backend.unir_notas --gravar
"""
from __future__ import annotations

import sys
from typing import Any, Dict, List

from backend.campos import eh_padrao
from backend.database import get_connection
from backend.provedores import competencia, mesma_empresa

CAMPOS_COMPLETAR = ("chave", "numero", "serie", "data_emissao", "observacao", "local_cidade", "municipio_codigo")


def _pontos(conn, nota) -> tuple:
    tem_fatura = conn.execute("SELECT 1 FROM faturas_locais WHERE nota_lancada_id = ? LIMIT 1", (nota["id"],)).fetchone()
    tem_pagamento = conn.execute("SELECT 1 FROM conciliacoes WHERE nota_lancada_id = ? LIMIT 1", (nota["id"],)).fetchone()
    ids_reais = sum(1 for c in ("numero", "chave") if str(nota[c] or "").strip() and not eh_padrao(nota[c]))
    return (bool(tem_pagamento), bool(tem_fatura), ids_reais, str(nota["updated_at"] or ""))


def grupos_duplicados(conn) -> List[List[Any]]:
    notas = conn.execute("SELECT * FROM notas_lancadas WHERE entidade_id <> '' ORDER BY updated_at").fetchall()
    grupos: List[List[Any]] = []
    for nota in notas:
        mes = competencia(nota["data_vencimento"])
        if not mes or not str(nota["provedor_nome"] or "").strip():
            continue
        for grupo in grupos:
            ref = grupo[0]
            if (ref["entidade_tipo"], ref["entidade_id"]) == (nota["entidade_tipo"], nota["entidade_id"]) \
                    and competencia(ref["data_vencimento"]) == mes and mesma_empresa(ref["provedor_nome"], nota["provedor_nome"]):
                grupo.append(nota)
                break
        else:
            grupos.append([nota])
    return [g for g in grupos if len(g) > 1]


def main(gravar: bool) -> int:
    conn = get_connection()
    grupos = grupos_duplicados(conn)
    if not grupos:
        print("Nenhuma cobrança duplicada encontrada.")
        return 0
    for grupo in grupos:
        grupo = sorted(grupo, key=lambda n: _pontos(conn, n), reverse=True)
        fica, sai = grupo[0], grupo[1:]
        print(f"\n{fica['local_nome']} | {competencia(fica['data_vencimento'])}")
        print(f"  FICA : {fica['id']} | {fica['provedor_nome']} | nº {fica['numero']} | R$ {fica['valor_total']} | venc {fica['data_vencimento']}")
        for n in sai:
            print(f"  UNE  : {n['id']} | {n['provedor_nome']} | nº {n['numero']} | R$ {n['valor_total']} | venc {n['data_vencimento']}")
        if not gravar:
            continue
        conn.execute("BEGIN IMMEDIATE")
        completar: Dict[str, Any] = {}
        for campo in CAMPOS_COMPLETAR:
            atual = str(fica[campo] or "").strip()
            if atual and not eh_padrao(atual):
                continue
            for n in sai:
                valor = str(n[campo] or "").strip()
                if valor and not eh_padrao(valor):
                    completar[campo] = valor
                    break
        for campo, valor in completar.items():
            conn.execute(f"UPDATE notas_lancadas SET {campo} = ? WHERE id = ?", (valor, fica["id"]))
        # Registra o que foi unido (números diferentes não se perdem).
        registro = "; ".join(
            f"unida com {n['provedor_nome']} nº {n['numero'] or '-'}" for n in sai
        )
        observacao = str(conn.execute("SELECT observacao FROM notas_lancadas WHERE id = ?", (fica["id"],)).fetchone()[0] or "")
        conn.execute(
            "UPDATE notas_lancadas SET observacao = ? WHERE id = ?",
            ((observacao + " | " if observacao else "") + registro, fica["id"]),
        )
        for n in sai:
            conn.execute("UPDATE notas_recebidas SET nota_lancada_id = ? WHERE nota_lancada_id = ?", (fica["id"], n["id"]))
            conn.execute("UPDATE faturas_locais SET nota_lancada_id = ? WHERE nota_lancada_id = ?", (fica["id"], n["id"]))
            # Conciliação é recalculada para a nota que fica; a da duplicada deixa de valer.
            conn.execute("DELETE FROM conciliacoes WHERE nota_lancada_id = ?", (n["id"],))
            legado = conn.execute("SELECT 1 FROM faturas_provedores WHERE nota_lancada_id = ?", (fica["id"],)).fetchone()
            if legado:
                conn.execute("DELETE FROM faturas_provedores WHERE nota_lancada_id = ?", (n["id"],))
            else:
                conn.execute("UPDATE faturas_provedores SET nota_lancada_id = ? WHERE nota_lancada_id = ?", (fica["id"], n["id"]))
            conn.execute("DELETE FROM notas_lancadas WHERE id = ?", (n["id"],))
        conn.commit()
        print(f"  unidas: {len(sai)} | campos completados: {', '.join(completar) or 'nenhum'}")
    conn.close()
    if gravar:
        print("\nGravado. Recalcule as conciliações com POST /api/notas/reconciliar.")
    else:
        print("\nSimulação: nada foi gravado (use --gravar).")
    return 0


if __name__ == "__main__":
    sys.exit(main("--gravar" in sys.argv))
