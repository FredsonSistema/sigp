from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from math import isfinite
from pathlib import Path
from typing import Any, Dict
from uuid import uuid4

from flask import Flask, jsonify, render_template_string, request

DB_PATH = Path(__file__).with_name("buscador_nfse.db")
app = Flask(__name__)


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS nfse_oficial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chave TEXT UNIQUE NOT NULL,
            cnpj_emitente TEXT,
            numero TEXT,
            serie TEXT,
            valor REAL,
            data_emissao TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS conciliacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chave TEXT,
            numero TEXT,
            serie TEXT,
            provedor_nome TEXT,
            local_tipo TEXT,
            local_nome TEXT,
            local_cidade TEXT,
            valor_lancado REAL,
            valor_pago REAL,
            data_emissao TEXT,
            data_vencimento TEXT,
            status TEXT DEFAULT 'PENDENTE',
            observacao TEXT,
            fatura_id TEXT DEFAULT '',
            fatura_valor REAL,
            fatura_vencimento TEXT DEFAULT '',
            fatura_emissor TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(chave)
        )
        """
    )
    reconciliation_columns = {row["name"] for row in conn.execute("PRAGMA table_info(conciliacoes)").fetchall()}
    for name, definition in (
        ("fatura_id", "TEXT NOT NULL DEFAULT ''"),
        ("fatura_valor", "REAL"),
        ("fatura_vencimento", "TEXT NOT NULL DEFAULT ''"),
        ("fatura_emissor", "TEXT NOT NULL DEFAULT ''"),
    ):
        if name not in reconciliation_columns:
            conn.execute(f"ALTER TABLE conciliacoes ADD COLUMN {name} {definition}")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sig_decisoes (
            id TEXT PRIMARY KEY,
            chave TEXT NOT NULL,
            decisao TEXT NOT NULL CHECK(decisao IN ('APROVADA', 'REJEITADA')),
            usuario TEXT NOT NULL,
            justificativa TEXT NOT NULL,
            dados_anteriores_json TEXT NOT NULL,
            dados_corrigidos_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sig_decisoes_chave ON sig_decisoes(chave, created_at DESC)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS documentos (
            id TEXT PRIMARY KEY,
            tipo_documento TEXT DEFAULT 'NFSE',
            origem TEXT DEFAULT 'SIGP',
            provedor_nome TEXT,
            chave TEXT,
            numero TEXT,
            serie TEXT,
            valor_total REAL,
            valor_pago REAL,
            data_emissao TEXT,
            data_vencimento TEXT,
            status TEXT DEFAULT 'PENDENTE',
            observacao TEXT,
            arquivo_origem TEXT,
            local_tipo TEXT,
            local_nome TEXT,
            local_cidade TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS documentos_itens (
            id TEXT PRIMARY KEY,
            documento_id TEXT NOT NULL,
            local_tipo TEXT,
            local_id TEXT,
            local_nome TEXT,
            local_cidade TEXT,
            valor REAL,
            status TEXT DEFAULT 'PENDENTE',
            observacao TEXT,
            data_vencimento TEXT,
            data_pagamento TEXT,
            FOREIGN KEY(documento_id) REFERENCES documentos(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sie_eventos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            evento TEXT,
            payload TEXT,
            status TEXT DEFAULT 'RECEBIDO',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def norm_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def from_row(row: sqlite3.Row) -> Dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def latest_decisions_by_key() -> Dict[str, Dict[str, Any]]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM sig_decisoes ORDER BY created_at DESC, rowid DESC"
    ).fetchall()
    conn.close()
    latest: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        item = from_row(row)
        if item["chave"] in latest:
            continue
        item["dados_anteriores"] = json.loads(item.pop("dados_anteriores_json") or "{}")
        item["dados_corrigidos"] = json.loads(item.pop("dados_corrigidos_json") or "{}")
        latest[item["chave"]] = item
    return latest


@app.before_request
def ensure_db_ready():
    init_db()


@app.get("/")
def index():
    return "<meta http-equiv='refresh' content='0; url=/sie' />"


@app.get("/health")
def health():
    conn = get_db()
    nfse_total = conn.execute("SELECT COUNT(*) AS total FROM nfse_oficial").fetchone()["total"]
    conciliacoes_total = conn.execute("SELECT COUNT(*) AS total FROM conciliacoes").fetchone()["total"]
    conn.close()
    return jsonify({
        "status": "ok",
        "service": "buscador_nfse",
        "database": str(DB_PATH),
        "nfse_total": nfse_total,
        "conciliacoes_total": conciliacoes_total,
        "timestamp": utc_now_iso(),
    })


@app.get("/api/health")
def api_health():
    return health()


@app.get("/api/nfse")
def list_nfse():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM nfse_oficial ORDER BY data_emissao DESC, id DESC"
    ).fetchall()
    conn.close()
    return jsonify({"items": [from_row(r) for r in rows]})


@app.post("/api/nfse")
def create_nfse():
    payload = request.get_json(silent=True) or {}
    chave = norm_text(payload.get("chave") or payload.get("id"))
    if not chave:
        return jsonify({"ok": False, "error": "Campo 'chave' obrigatório."}), 400

    cnpj_emitente = norm_text(payload.get("cnpjEmitente") or payload.get("cnpj_emitente"))
    numero = norm_text(payload.get("numero"))
    serie = norm_text(payload.get("serie"))
    valor = payload.get("valor")
    data_emissao = norm_text(payload.get("dataEmissao") or payload.get("data_emissao"))

    conn = get_db()
    conn.execute(
        """
        INSERT INTO nfse_oficial (chave, cnpj_emitente, numero, serie, valor, data_emissao)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(chave) DO UPDATE SET
            cnpj_emitente = excluded.cnpj_emitente,
            numero = excluded.numero,
            serie = excluded.serie,
            valor = excluded.valor,
            data_emissao = excluded.data_emissao
        """,
        (chave, cnpj_emitente, numero, serie, float(valor) if valor not in (None, "") else None, data_emissao or None),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM nfse_oficial WHERE chave = ?", (chave,)).fetchone()
    conn.close()
    return jsonify({"ok": True, "item": from_row(row)})


@app.get("/api/notas")
def list_notas():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM documentos ORDER BY updated_at DESC, created_at DESC"
    ).fetchall()
    conn.close()
    return jsonify({"items": [from_row(r) for r in rows]})


@app.get("/api/notas/pendentes")
def listar_notas_pendentes():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM documentos WHERE status IN ('PENDENTE', 'RECEBIDA') ORDER BY updated_at DESC, created_at DESC"
    ).fetchall()
    conn.close()
    return jsonify({"items": [from_row(r) for r in rows]})


@app.get("/api/notas/pagas")
def listar_notas_pagas():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM documentos WHERE status IN ('PAGA', 'PAGO_COM_ATRASO', 'PAGO_PARCIAL', 'PAGO_COM_VALOR_INFERIOR') ORDER BY updated_at DESC, created_at DESC"
    ).fetchall()
    conn.close()
    return jsonify({"items": [from_row(r) for r in rows]})


@app.get("/api/notas/consulta")
def consultar_nota():
    chave = norm_text(request.args.get("chave"))
    numero = norm_text(request.args.get("numero"))
    serie = norm_text(request.args.get("serie"))
    provedor = norm_text(request.args.get("provedor"))

    conn = get_db()
    if chave:
        row = conn.execute("SELECT * FROM documentos WHERE chave = ?", (chave,)).fetchone()
    elif numero and serie:
        row = conn.execute("SELECT * FROM documentos WHERE numero = ? AND serie = ?", (numero, serie)).fetchone()
    elif numero and provedor:
        row = conn.execute("SELECT * FROM documentos WHERE numero = ? AND provedor_nome = ?", (numero, provedor)).fetchone()
    else:
        row = None
    conn.close()

    if row is None:
        return jsonify({"ok": False, "error": "Nota não encontrada."}), 404
    return jsonify({"ok": True, "item": from_row(row)})


@app.post("/api/notas")
def criar_nota():
    payload = request.get_json(silent=True) or {}
    documento = payload.get("documento") or payload
    itens = payload.get("itens") or [
        {
            "localTipo": documento.get("localTipo") or documento.get("local_tipo") or "agencia",
            "localNome": documento.get("localNome") or documento.get("local_nome") or "",
            "localCidade": documento.get("localCidade") or documento.get("local_cidade") or "",
            "valor": documento.get("valorTotal") or documento.get("valor") or 0,
            "status": documento.get("status") or "PENDENTE",
            "observacao": documento.get("observacao") or "",
            "dataVencimento": documento.get("dataVencimento") or documento.get("data_vencimento") or "",
        }
    ]

    doc_id = str(documento.get("id") or payload.get("id") or f"doc-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{abs(hash(str(request.remote_addr)))}")
    valor_total = float(documento.get("valorTotal") or documento.get("valor") or 0)
    valor_pago = float(documento.get("valorPago") or documento.get("valor_pago") or 0)

    if not documento.get("chave") and not documento.get("numero"):
        return jsonify({"ok": False, "error": "Informe chave ou número do documento."}), 400

    conn = get_db()
    conn.execute(
        """
        INSERT INTO documentos (
            id, tipo_documento, origem, provedor_nome, chave, numero, serie, valor_total, valor_pago,
            data_emissao, data_vencimento, status, observacao, arquivo_origem, local_tipo, local_nome, local_cidade,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            tipo_documento = excluded.tipo_documento,
            origem = excluded.origem,
            provedor_nome = excluded.provedor_nome,
            chave = excluded.chave,
            numero = excluded.numero,
            serie = excluded.serie,
            valor_total = excluded.valor_total,
            valor_pago = excluded.valor_pago,
            data_emissao = excluded.data_emissao,
            data_vencimento = excluded.data_vencimento,
            status = excluded.status,
            observacao = excluded.observacao,
            arquivo_origem = excluded.arquivo_origem,
            local_tipo = excluded.local_tipo,
            local_nome = excluded.local_nome,
            local_cidade = excluded.local_cidade,
            updated_at = excluded.updated_at
        """,
        (
            doc_id,
            str(documento.get("tipoDocumento") or documento.get("tipo_documento") or "NFSE"),
            str(documento.get("origem") or "SIGP"),
            norm_text(documento.get("provedorNome") or documento.get("provedor_nome")),
            norm_text(documento.get("chave") or ""),
            norm_text(documento.get("numero") or ""),
            norm_text(documento.get("serie") or ""),
            valor_total,
            valor_pago,
            norm_text(documento.get("dataEmissao") or documento.get("data_emissao") or ""),
            norm_text(documento.get("dataVencimento") or documento.get("data_vencimento") or ""),
            str(documento.get("status") or "PENDENTE").upper(),
            norm_text(documento.get("observacao") or ""),
            norm_text(documento.get("arquivoOrigem") or documento.get("arquivo_origem") or ""),
            str(documento.get("localTipo") or documento.get("local_tipo") or "agencia"),
            norm_text(documento.get("localNome") or documento.get("local_nome") or ""),
            norm_text(documento.get("localCidade") or documento.get("local_cidade") or ""),
            utc_now_iso(),
        ),
    )

    conn.execute("DELETE FROM documentos_itens WHERE documento_id = ?", (doc_id,))
    for index, item in enumerate(itens, start=1):
        item_id = str(item.get("id") or f"{doc_id}-item-{index}")
        conn.execute(
            """
            INSERT INTO documentos_itens (
                id, documento_id, local_tipo, local_id, local_nome, local_cidade, valor, status, observacao, data_vencimento, data_pagamento
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item_id,
                doc_id,
                str(item.get("localTipo") or item.get("local_tipo") or "agencia"),
                norm_text(item.get("localId") or item.get("local_id") or ""),
                norm_text(item.get("localNome") or item.get("local_nome") or ""),
                norm_text(item.get("localCidade") or item.get("local_cidade") or ""),
                float(item.get("valor") or item.get("total") or 0),
                str(item.get("status") or "PENDENTE").upper(),
                norm_text(item.get("observacao") or ""),
                norm_text(item.get("dataVencimento") or item.get("data_vencimento") or ""),
                norm_text(item.get("dataPagamento") or item.get("data_pagamento") or ""),
            ),
        )

    stored = conn.execute("SELECT * FROM documentos WHERE id = ?", (doc_id,)).fetchone()
    item_rows = conn.execute("SELECT * FROM documentos_itens WHERE documento_id = ? ORDER BY id", (doc_id,)).fetchall()
    conn.commit()
    conn.close()

    response = from_row(stored)
    response["itens"] = [from_row(row) for row in item_rows]
    return jsonify({"ok": True, "documento": response})


@app.get("/api/nfse/consulta")
def consulta_nfse():
    chave = norm_text(request.args.get("chave"))
    cnpj = norm_text(request.args.get("cnpj") or request.args.get("cnpj_emitente"))
    numero = norm_text(request.args.get("numero"))
    serie = norm_text(request.args.get("serie"))

    conn = get_db()
    if chave:
        row = conn.execute("SELECT * FROM nfse_oficial WHERE chave = ?", (chave,)).fetchone()
    elif cnpj and numero and serie:
        row = conn.execute(
            "SELECT * FROM nfse_oficial WHERE cnpj_emitente = ? AND numero = ? AND serie = ?",
            (cnpj, numero, serie),
        ).fetchone()
    else:
        row = None
    conn.close()

    if row is None:
        return jsonify({"ok": False, "error": "NFS-e não encontrada."}), 404
    return jsonify({"ok": True, "item": from_row(row)})


@app.get("/api/conciliacoes")
def list_conciliacoes():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM conciliacoes ORDER BY updated_at DESC, id DESC"
    ).fetchall()
    conn.close()
    return jsonify({"items": [from_row(r) for r in rows]})


@app.post("/api/conciliacoes")
def upsert_conciliacao():
    payload = request.get_json(silent=True) or {}
    chave = norm_text(payload.get("chave") or payload.get("id"))

    if not chave:
        return jsonify({"ok": False, "error": "Campo 'chave' obrigatório para reconciliar."}), 400

    row = {
        "chave": chave,
        "numero": norm_text(payload.get("numero")),
        "serie": norm_text(payload.get("serie")),
        "provedor_nome": norm_text(payload.get("provedorNome") or payload.get("provedor_nome")),
        "local_tipo": norm_text(payload.get("localTipo") or payload.get("local_tipo")),
        "local_nome": norm_text(payload.get("localNome") or payload.get("local_nome")),
        "local_cidade": norm_text(payload.get("localCidade") or payload.get("local_cidade")),
        "valor_lancado": payload.get("valor") if payload.get("valor") not in (None, "") else payload.get("valorLancado") if payload.get("valorLancado") not in (None, "") else 0.0,
        "valor_pago": payload.get("valorPago") if payload.get("valorPago") not in (None, "") else 0.0,
        "data_emissao": norm_text(payload.get("dataEmissao") or payload.get("data_emissao")),
        "data_vencimento": norm_text(payload.get("dataVencimento") or payload.get("data_vencimento")),
        "status": norm_text(payload.get("status") or "PENDENTE").upper(),
        "observacao": norm_text(payload.get("observacao")),
        "fatura_id": norm_text(payload.get("faturaId") or payload.get("fatura_id")),
        "fatura_valor": payload.get("faturaValor") if payload.get("faturaValor") not in (None, "") else None,
        "fatura_vencimento": norm_text(payload.get("faturaVencimento") or payload.get("fatura_vencimento")),
        "fatura_emissor": norm_text(payload.get("faturaEmissor") or payload.get("fatura_emissor")),
        "updated_at": utc_now_iso(),
    }

    conn = get_db()
    existing = conn.execute("SELECT * FROM conciliacoes WHERE chave = ?", (chave,)).fetchone()
    if existing:
        conn.execute(
            """
            UPDATE conciliacoes SET
                numero = ?, serie = ?, provedor_nome = ?, local_tipo = ?, local_nome = ?, local_cidade = ?,
                valor_lancado = ?, valor_pago = ?, data_emissao = ?, data_vencimento = ?, status = ?, observacao = ?,
                fatura_id = ?, fatura_valor = ?, fatura_vencimento = ?, fatura_emissor = ?, updated_at = ?
            WHERE chave = ?
            """,
            (
                row["numero"], row["serie"], row["provedor_nome"], row["local_tipo"], row["local_nome"], row["local_cidade"],
                float(row["valor_lancado"]), float(row["valor_pago"]), row["data_emissao"], row["data_vencimento"],
                row["status"], row["observacao"], row["fatura_id"], row["fatura_valor"],
                row["fatura_vencimento"], row["fatura_emissor"], row["updated_at"], chave,
            ),
        )
    else:
        conn.execute(
            """
            INSERT INTO conciliacoes (
                chave, numero, serie, provedor_nome, local_tipo, local_nome, local_cidade,
                valor_lancado, valor_pago, data_emissao, data_vencimento, status, observacao,
                fatura_id, fatura_valor, fatura_vencimento, fatura_emissor, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["chave"], row["numero"], row["serie"], row["provedor_nome"], row["local_tipo"], row["local_nome"], row["local_cidade"],
                float(row["valor_lancado"]), float(row["valor_pago"]), row["data_emissao"], row["data_vencimento"],
                row["status"], row["observacao"], row["fatura_id"], row["fatura_valor"],
                row["fatura_vencimento"], row["fatura_emissor"], row["updated_at"],
            ),
        )
    conn.commit()
    stored = conn.execute("SELECT * FROM conciliacoes WHERE chave = ?", (chave,)).fetchone()
    conn.close()
    return jsonify({"ok": True, "item": from_row(stored)})


@app.get("/api/sie/eventos")
def listar_sie_eventos():
    conn = get_db()
    rows = conn.execute("SELECT * FROM sie_eventos ORDER BY id DESC LIMIT 50").fetchall()
    conn.close()
    return jsonify({"items": [from_row(r) for r in rows]})


@app.post("/api/sie/webhook")
def webhook_sie():
    payload = request.get_json(silent=True) or {}
    evento = norm_text(payload.get("evento") or payload.get("event") or "status_atualizado")
    if not evento:
        return jsonify({"ok": False, "error": "Campo 'evento' obrigatório."}), 400

    conn = get_db()
    conn.execute(
        "INSERT INTO sie_eventos (evento, payload, status) VALUES (?, ?, 'RECEBIDO')",
        (evento, json.dumps(payload, ensure_ascii=False)),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "evento": evento, "recebido": True})


@app.get("/api/sig/decisoes")
def listar_decisoes_sig():
    conn = get_db()
    rows = conn.execute("SELECT * FROM conciliacoes ORDER BY updated_at DESC, id DESC").fetchall()
    conn.close()
    decisions = latest_decisions_by_key()
    items = []
    for row in rows:
        item = from_row(row)
        item["decisao_humana"] = decisions.get(item["chave"])
        items.append(item)
    return jsonify({"items": items})


@app.get("/api/sig/decisoes/<path:chave>")
def historico_decisoes_sig(chave: str):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM sig_decisoes WHERE chave = ? ORDER BY created_at DESC, rowid DESC",
        (chave,),
    ).fetchall()
    conn.close()
    items = []
    for row in rows:
        item = from_row(row)
        item["dados_anteriores"] = json.loads(item.pop("dados_anteriores_json") or "{}")
        item["dados_corrigidos"] = json.loads(item.pop("dados_corrigidos_json") or "{}")
        items.append(item)
    return jsonify({"items": items})


@app.post("/api/sig/decisoes")
def registrar_decisao_sig():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"ok": False, "error": "Envie um objeto JSON com a decisão."}), 400
    chave = norm_text(payload.get("chave"))
    decisao = norm_text(payload.get("decisao")).upper()
    usuario = norm_text(payload.get("usuario"))
    justificativa = norm_text(payload.get("justificativa"))
    decision_id = norm_text(payload.get("id")) or str(uuid4())
    changes = payload.get("dadosCorrigidos")
    if not chave or decisao not in {"APROVADA", "REJEITADA"} or not usuario or not justificativa:
        return jsonify({
            "ok": False,
            "error": "Informe a conciliação, decisão aprovada/rejeitada, usuário e justificativa.",
        }), 400
    if not isinstance(changes, dict):
        return jsonify({"ok": False, "error": "Informe os dados revisados em 'dadosCorrigidos'."}), 400

    columns = {
        "provedorNome": ("provedor_nome", "text"),
        "localNome": ("local_nome", "text"),
        "localCidade": ("local_cidade", "text"),
        "valorLancado": ("valor_lancado", "number"),
        "valorPago": ("valor_pago", "number"),
        "dataEmissao": ("data_emissao", "date"),
        "dataVencimento": ("data_vencimento", "date"),
        "faturaValor": ("fatura_valor", "number"),
        "faturaVencimento": ("fatura_vencimento", "date"),
        "faturaEmissor": ("fatura_emissor", "text"),
        "observacao": ("observacao", "text"),
    }
    unknown = sorted(set(changes) - set(columns))
    if unknown:
        return jsonify({"ok": False, "error": f"Campos não corrigíveis: {', '.join(unknown)}."}), 400

    conn = get_db()
    try:
        existing_decision = conn.execute(
            "SELECT * FROM sig_decisoes WHERE id = ?", (decision_id,)
        ).fetchone()
        if existing_decision:
            item = from_row(existing_decision)
            item["dados_anteriores"] = json.loads(item.pop("dados_anteriores_json") or "{}")
            item["dados_corrigidos"] = json.loads(item.pop("dados_corrigidos_json") or "{}")
            return jsonify({"ok": True, "item": item, "idempotente": True})

        current = conn.execute("SELECT * FROM conciliacoes WHERE chave = ?", (chave,)).fetchone()
        if not current:
            return jsonify({"ok": False, "error": "Conciliação automática não encontrada."}), 404
        current = from_row(current)
        previous_values = {}
        corrected_values = {}
        for field, (column, kind) in columns.items():
            old_value = current.get(column)
            previous_values[field] = old_value
            if field not in changes:
                corrected_values[field] = old_value
                continue
            value = changes[field]
            if kind == "number":
                if value in (None, ""):
                    value = None
                else:
                    try:
                        value = float(value)
                    except (TypeError, ValueError):
                        return jsonify({"ok": False, "error": f"Valor inválido para {field}."}), 400
                    if not isfinite(value) or value < 0:
                        return jsonify({"ok": False, "error": f"Valor inválido para {field}."}), 400
            elif kind == "date":
                value = norm_text(value)
                if value:
                    try:
                        datetime.strptime(value, "%Y-%m-%d")
                    except ValueError:
                        return jsonify({"ok": False, "error": f"Data inválida para {field}; use AAAA-MM-DD."}), 400
            else:
                value = norm_text(value)
            corrected_values[field] = value

        created_at = utc_now_iso()
        conn.execute(
            """
            INSERT INTO sig_decisoes (
                id, chave, decisao, usuario, justificativa, dados_anteriores_json,
                dados_corrigidos_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                decision_id, chave, decisao, usuario, justificativa,
                json.dumps(previous_values, ensure_ascii=False),
                json.dumps(corrected_values, ensure_ascii=False), created_at,
            ),
        )
        conn.commit()
        return jsonify({
            "ok": True,
            "item": {
                "id": decision_id,
                "chave": chave,
                "decisao": decisao,
                "usuario": usuario,
                "justificativa": justificativa,
                "dados_anteriores": previous_values,
                "dados_corrigidos": corrected_values,
                "created_at": created_at,
            },
        }), 201
    finally:
        conn.close()


@app.get("/sig")
def decisao_dashboard():
    return render_template_string(
        """
        <!doctype html>
        <html lang="pt-BR"><head>
          <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
          <title>SIG — Tomada de decisão</title>
          <style>
            :root { color-scheme: light; font-family: Arial, sans-serif; color: #15212d; background: #f5f7fb; }
            * { box-sizing: border-box; }
            body { margin: 0; padding: 24px; }
            main { max-width: 1180px; margin: 0 auto; }
            h1 { margin: 0 0 8px; }
            .sub, .hint { color: #5f6d7a; }
            .toolbar, .card { background: white; border: 1px solid #dce3eb; border-radius: 12px; padding: 14px; margin: 14px 0; }
            .toolbar { display: flex; gap: 10px; align-items: end; flex-wrap: wrap; }
            label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 5px; }
            input, select, textarea { width: 100%; border: 1px solid #c8d2de; border-radius: 7px; padding: 9px; font: inherit; }
            .toolbar .webhook { flex: 1; min-width: 260px; }
            button { border: 0; border-radius: 7px; padding: 9px 12px; cursor: pointer; background: #1769aa; color: white; font-weight: 600; }
            button.secondary { background: #e8eef5; color: #203346; }
            button:disabled { opacity: .6; cursor: wait; }
            .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; }
            .card-head { display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; align-items: start; }
            .badge { display: inline-block; padding: 5px 8px; border-radius: 20px; background: #edf2f7; font-size: 12px; font-weight: 700; }
            .automatic { color: #165d96; }
            .decision { color: #573b91; }
            .actions { display: flex; gap: 8px; margin-top: 12px; flex-wrap: wrap; }
            dialog { width: min(880px, calc(100% - 24px)); max-height: 90vh; border: 0; border-radius: 12px; padding: 20px; box-shadow: 0 18px 60px #0004; overflow: auto; }
            dialog::backdrop { background: #14233388; }
            .modal-actions { display: flex; gap: 8px; justify-content: end; margin-top: 16px; }
            #message { min-height: 20px; margin: 8px 0; color: #165d96; }
            pre { white-space: pre-wrap; overflow-wrap: anywhere; background: #f2f5f9; padding: 12px; border-radius: 8px; }
          </style>
        </head><body><main>
          <h1>SIG — Tomada de decisão</h1>
          <p class="sub">Revise os dados e registre aprovação ou rejeição com responsável e justificativa. A decisão e as correções ficam auditadas à parte e não alteram a conciliação automática nem liberam o ciclo para o SIE.</p>
          <div class="toolbar">
            <div class="webhook"><label for="webhook">Webhook n8n para decisões</label><input id="webhook" type="url"></div>
            <button class="secondary" id="saveWebhook" type="button">Salvar webhook</button>
            <button class="secondary" id="refresh" type="button">Atualizar lista</button>
          </div>
          <div id="message" role="status"></div>
          <section id="records" aria-live="polite"></section>
          <dialog id="editor">
            <form id="decisionForm">
              <h2>Revisar conciliação</h2>
              <p id="automaticInfo" class="hint"></p>
              <input type="hidden" name="chave">
              <div class="grid" id="editFields"></div>
              <div class="grid" style="margin-top:10px">
                <div><label for="decision">Decisão humana</label><select id="decision" required><option value="APROVADA">Aprovar</option><option value="REJEITADA">Rejeitar</option></select></div>
                <div><label for="user">Usuário responsável</label><input id="user" required autocomplete="name"></div>
                <div style="grid-column:1/-1"><label for="reason">Justificativa</label><textarea id="reason" rows="3" required></textarea></div>
              </div>
              <p class="hint">Os campos corrigidos serão salvos como uma versão auditável; os valores automáticos originais e o status da conciliação serão preservados.</p>
              <div class="modal-actions"><button class="secondary" type="button" id="cancel">Cancelar</button><button id="submit" type="submit">Salvar decisão via n8n</button></div>
            </form>
          </dialog>
          <dialog id="history">
            <h2>Histórico de decisões</h2><div id="historyBody"></div>
            <div class="modal-actions"><button class="secondary" type="button" id="closeHistory">Fechar</button></div>
          </dialog>
          <script>
            (() => {
              const fields = [
                ['provedorNome', 'Provedor', 'text'], ['localNome', 'Local', 'text'],
                ['localCidade', 'Cidade', 'text'], ['valorLancado', 'Valor da nota lançada', 'number'],
                ['valorPago', 'Valor pago', 'number'], ['dataEmissao', 'Emissão', 'date'],
                ['dataVencimento', 'Vencimento da nota', 'date'], ['faturaEmissor', 'Emissor do PDF', 'text'],
                ['faturaValor', 'Valor de referência do PDF', 'number'],
                ['faturaVencimento', 'Vencimento de referência do PDF', 'date'],
                ['observacao', 'Observação automática', 'text'],
              ];
              const form = document.getElementById('decisionForm');
              const editor = document.getElementById('editor');
              const message = document.getElementById('message');
              const n8nUrl = document.getElementById('webhook');
              const endpointKey = 'sigp_decisao_webhook_url';
              n8nUrl.value = localStorage.getItem(endpointKey) || 'http://127.0.0.1:5678/webhook/sigp-tomada-decisao';
              document.getElementById('saveWebhook').onclick = () => {
                try { new URL(n8nUrl.value); } catch { message.textContent = 'Informe uma URL válida do webhook n8n.'; return; }
                localStorage.setItem(endpointKey, n8nUrl.value.trim());
                message.textContent = 'Webhook salvo neste navegador.';
              };
              document.getElementById('refresh').onclick = load;
              document.getElementById('cancel').onclick = () => editor.close();
              document.getElementById('closeHistory').onclick = () => document.getElementById('history').close();
              const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
              const money = (value) => value == null || value === '' ? '—' : Number(value).toLocaleString('pt-BR', {style:'currency',currency:'BRL'});
              function fieldValue(item, field) {
                const decision = item.decisao_humana?.dados_corrigidos;
                if (decision && decision[field] !== undefined) return decision[field];
                const map = {
                  provedorNome:'provedor_nome', localNome:'local_nome', localCidade:'local_cidade',
                  valorLancado:'valor_lancado', valorPago:'valor_pago', dataEmissao:'data_emissao',
                  dataVencimento:'data_vencimento', faturaValor:'fatura_valor',
                  faturaVencimento:'fatura_vencimento', faturaEmissor:'fatura_emissor', observacao:'observacao',
                };
                return item[map[field]];
              }
              function openEditor(item) {
                form.elements.chave.value = item.chave;
                document.getElementById('automaticInfo').textContent =
                  `Status automático: ${item.status || 'PENDENTE'} · Fatura PDF: ${money(item.fatura_valor)} · vencimento ${item.fatura_vencimento || '—'} · emissor ${item.fatura_emissor || '—'}`;
                document.getElementById('decision').value = 'APROVADA';
                document.getElementById('user').value = '';
                document.getElementById('reason').value = '';
                const box = document.getElementById('editFields');
                box.replaceChildren();
                for (const [key, label, type] of fields) {
                  const wrap = document.createElement('div');
                  const caption = document.createElement('label');
                  caption.textContent = label;
                  const input = document.createElement('input');
                  input.type = type;
                  input.dataset.field = key;
                  if (type === 'number') input.step = '0.01';
                  input.value = fieldValue(item, key) ?? '';
                  wrap.append(caption, input);
                  box.appendChild(wrap);
                }
                editor.showModal();
              }
              async function showHistory(key) {
                const target = document.getElementById('historyBody');
                target.textContent = 'Carregando…';
                document.getElementById('history').showModal();
                const response = await fetch(`/api/sig/decisoes/${encodeURIComponent(key)}`);
                const result = await response.json();
                if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
                target.replaceChildren();
                if (!result.items.length) { target.textContent = 'Nenhuma decisão registrada.'; return; }
                for (const decision of result.items) {
                  const block = document.createElement('article');
                  const title = document.createElement('strong');
                  title.textContent = `${decision.decisao} · ${decision.usuario} · ${decision.created_at}`;
                  const reason = document.createElement('p');
                  reason.textContent = decision.justificativa;
                  const snapshot = document.createElement('pre');
                  snapshot.textContent = JSON.stringify({
                    anteriores: decision.dados_anteriores,
                    corrigidos: decision.dados_corrigidos,
                  }, null, 2);
                  block.append(title, reason, snapshot);
                  target.appendChild(block);
                }
              }
              function render(items) {
                const target = document.getElementById('records');
                target.replaceChildren();
                if (!items.length) { target.textContent = 'Nenhuma conciliação recebida do n8n ainda.'; return; }
                for (const item of items) {
                  const card = document.createElement('article');
                  card.className = 'card';
                  const head = document.createElement('div');
                  head.className = 'card-head';
                  const title = document.createElement('strong');
                  title.textContent = `${item.local_nome || 'Local'} · ${item.provedor_nome || 'Provedor'} · NF ${item.numero || item.chave}`;
                  const automatic = document.createElement('span');
                  automatic.className = 'badge automatic';
                  automatic.textContent = `Conciliação automática: ${item.status || 'PENDENTE'}`;
                  head.append(title, automatic);
                  const pdf = document.createElement('p');
                  pdf.className = 'hint';
                  pdf.textContent = `Referência PDF: ${money(item.fatura_valor)} · vencimento ${item.fatura_vencimento || '—'} · ${item.fatura_emissor || 'sem emissor informado'}`;
                  const human = document.createElement('p');
                  human.className = 'badge decision';
                  human.textContent = item.decisao_humana
                    ? `Decisão humana separada: ${item.decisao_humana.decisao} · ${item.decisao_humana.usuario} · ${item.decisao_humana.justificativa}`
                    : 'Decisão humana: ainda não registrada';
                  const details = document.createElement('p');
                  details.textContent = `Lançado ${money(item.valor_lancado)} · pago ${money(item.valor_pago)} · vencimento ${item.data_vencimento || '—'} · chave ${item.chave}`;
                  const actions = document.createElement('div');
                  actions.className = 'actions';
                  const review = document.createElement('button');
                  review.type = 'button';
                  review.textContent = 'Revisar e decidir';
                  review.onclick = () => openEditor(item);
                  const historyButton = document.createElement('button');
                  historyButton.type = 'button';
                  historyButton.className = 'secondary';
                  historyButton.textContent = 'Histórico';
                  historyButton.onclick = () => showHistory(item.chave).catch((error) => { message.textContent = error.message; });
                  actions.append(review, historyButton);
                  card.append(head, pdf, human, details, actions);
                  target.appendChild(card);
                }
              }
              async function load() {
                message.textContent = '';
                try {
                  const response = await fetch('/api/sig/decisoes');
                  const result = await response.json();
                  if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
                  render(result.items || []);
                } catch (error) { message.textContent = `Falha ao carregar conciliações: ${error.message}`; }
              }
              form.addEventListener('submit', async (event) => {
                event.preventDefault();
                const submit = document.getElementById('submit');
                submit.disabled = true;
                message.textContent = 'Enviando decisão ao n8n…';
                const changes = {};
                document.querySelectorAll('#editFields [data-field]').forEach((input) => { changes[input.dataset.field] = input.value; });
                const payload = {
                  id: crypto.randomUUID(),
                  chave: form.elements.chave.value,
                  decisao: document.getElementById('decision').value,
                  usuario: document.getElementById('user').value.trim(),
                  justificativa: document.getElementById('reason').value.trim(),
                  dadosCorrigidos: changes,
                };
                try {
                  const response = await fetch(n8nUrl.value.trim(), {
                    method: 'POST',
                    headers: {'Content-Type':'application/json'},
                    body: JSON.stringify(payload),
                  });
                  const result = await response.json().catch(() => ({}));
                  if (!response.ok || result.ok === false) throw new Error(result.error || `Webhook n8n respondeu HTTP ${response.status}`);
                  message.textContent = 'Decisão auditada. O status automático foi mantido sem alterações.';
                  editor.close();
                  await load();
                } catch (error) {
                  message.textContent = `A decisão não foi confirmada pelo n8n: ${error.message}`;
                } finally { submit.disabled = false; }
              });
              load();
            })();
          </script>
        </main></body></html>
        """
    )


@app.get("/sie")
def dashboard():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) AS total FROM conciliacoes").fetchone()["total"]
    pendentes = conn.execute("SELECT COUNT(*) AS total FROM conciliacoes WHERE status = 'PENDENTE'").fetchone()["total"]
    pagas = conn.execute("SELECT COUNT(*) AS total FROM conciliacoes WHERE status IN ('PAGA', 'PAGO_COM_ATRASO', 'PAGO_COM_ACRESCIMO', 'PAGO_COM_VALOR_INFERIOR', 'PAGO_PARCIAL')").fetchone()["total"]
    divergencias = conn.execute("SELECT COUNT(*) AS total FROM conciliacoes WHERE status = 'DIVERGENCIA_CADASTRAL'").fetchone()["total"]
    expiradas = conn.execute("SELECT COUNT(*) AS total FROM conciliacoes WHERE status = 'EXPIRADA'").fetchone()["total"]
    rows = conn.execute("SELECT * FROM conciliacoes ORDER BY updated_at DESC, id DESC").fetchall()
    statuses = [
        row["status"]
        for row in conn.execute("SELECT DISTINCT status FROM conciliacoes WHERE status != '' ORDER BY status").fetchall()
    ]
    conn.close()

    status_palette = {
        "PENDENTE": "#bdbdbd",
        "RECEBIDA": "#7bc6ff",
        "DIVERGENCIA_CADASTRAL": "#ffb4a2",
        "NAO_ENCONTRADA": "#f7cb68",
        "PAGA": "#7ad38a",
        "PAGO_COM_ATRASO": "#f5b700",
        "PAGO_COM_ACRESCIMO": "#a78bfa",
        "PAGO_COM_VALOR_INFERIOR": "#f59e0b",
        "PAGO_PARCIAL": "#fb7185",
        "EXPIRADA": "#f87171",
    }
    paid_statuses = {"PAGA", "PAGO_COM_ATRASO", "PAGO_COM_ACRESCIMO", "PAGO_COM_VALOR_INFERIOR", "PAGO_PARCIAL"}
    divergence_statuses = {"DIVERGENCIA_CADASTRAL", "NAO_ENCONTRADA"}
    rows = [dict(row) for row in rows]
    decisions = latest_decisions_by_key()
    for item in rows:
        item["valor_diferenca"] = round(float(item["valor_pago"] or 0) - float(item["valor_lancado"] or 0), 2)
        item["decisao_humana"] = decisions.get(item["chave"])
        if item["status"] in paid_statuses:
            item["categoria"] = "paid"
        elif item["status"] in divergence_statuses:
            item["categoria"] = "divergence"
        elif item["status"] == "EXPIRADA":
            item["categoria"] = "expired"
        elif item["status"] in {"PENDENTE", "RECEBIDA"}:
            item["categoria"] = "pending"
        else:
            item["categoria"] = "other"

    return render_template_string(
        """
        <!doctype html>
        <html lang="pt-BR">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <title>SIE — Conciliação NFS-e</title>
          <style>
            :root { color-scheme: light; font-family: Arial, sans-serif; color: #15212d; background: #f5f7fb; }
            * { box-sizing: border-box; }
            body { margin: 0; padding: 24px; }
            .container { max-width: 1280px; margin: 0 auto; }
            h1 { margin: 0 0 8px; }
            .intro { margin: 0 0 22px; color: #5f6d7a; }
            .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 20px; }
            .card { min-height: 96px; padding: 16px; border: 1px solid transparent; border-radius: 12px; background: white; color: inherit; text-align: left; box-shadow: 0 4px 12px rgba(0,0,0,.06); cursor: pointer; }
            .card:hover, .card[aria-pressed="true"] { border-color: #3975c6; box-shadow: 0 0 0 2px rgba(57,117,198,.14); }
            .card .label { color: #5f6d7a; font-size: 12px; text-transform: uppercase; }
            .card .value { display: block; font-size: 1.8rem; font-weight: 700; margin-top: 8px; }
            .filters { display: grid; grid-template-columns: minmax(220px, 1fr) minmax(190px, 260px) auto; align-items: end; gap: 12px; margin-bottom: 12px; padding: 16px; border-radius: 12px; background: white; box-shadow: 0 4px 12px rgba(0,0,0,.04); }
            label { display: grid; gap: 6px; color: #475569; font-size: 13px; font-weight: 700; }
            input, select, .reset { min-height: 42px; padding: 9px 11px; border: 1px solid #cbd5e1; border-radius: 8px; background: white; color: #15212d; font: inherit; }
            .reset { cursor: pointer; font-weight: 700; }
            .result-count { margin: 12px 2px; color: #5f6d7a; font-size: 13px; }
            .table-wrap { overflow-x: auto; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,.05); }
            table { width: 100%; min-width: 820px; border-collapse: collapse; background: white; }
            th, td { padding: 12px; border-bottom: 1px solid #e7edf5; text-align: left; vertical-align: top; }
            th { background: #eef3fa; font-size: 12px; white-space: nowrap; }
            .badge { display: inline-block; padding: 6px 10px; border-radius: 999px; font-size: 11px; font-weight: 700; color: #10243b; }
            .key { max-width: 210px; overflow-wrap: anywhere; font-family: ui-monospace, monospace; font-size: 12px; }
            .detail-toggle { padding: 6px 9px; border: 1px solid #cbd5e1; border-radius: 7px; background: white; color: #1d4ed8; cursor: pointer; font-weight: 700; }
            .details-row[hidden], .record-row[hidden] { display: none; }
            .details-cell { padding: 16px; background: #f8fafc; }
            .details-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; }
            .detail-item { padding: 12px; border: 1px solid #e2e8f0; border-radius: 8px; background: white; }
            .detail-label { display: block; margin-bottom: 5px; color: #64748b; font-size: 11px; font-weight: 700; text-transform: uppercase; }
            .detail-value { overflow-wrap: anywhere; }
            .observation { grid-column: 1 / -1; }
            .empty { padding: 28px; background: white; color: #64748b; text-align: center; }
            a { color: #1d4ed8; }
            @media (max-width: 700px) { body { padding: 14px; } .filters { grid-template-columns: 1fr; } .reset { width: 100%; } }
          </style>
        </head>
        <body>
          <div class="container">
            <h1>SIE — Conciliação NFS-e</h1>
            <p class="intro">Acompanhe documentos recebidos do SIGp, confira os dados conciliados e filtre por status.</p>
            <p><a href="/sig">Abrir SIG — Tomada de decisão</a></p>
            <div class="cards">
              <button class="card filter-card" type="button" data-category="" aria-pressed="true"><span class="label">Total</span><span class="value">{{ total }}</span></button>
              <button class="card filter-card" type="button" data-category="paid" aria-pressed="false"><span class="label">Pagas</span><span class="value">{{ pagas }}</span></button>
              <button class="card filter-card" type="button" data-category="pending" aria-pressed="false"><span class="label">Pendentes</span><span class="value">{{ pendentes }}</span></button>
              <button class="card filter-card" type="button" data-category="divergence" aria-pressed="false"><span class="label">Divergências</span><span class="value">{{ divergencias }}</span></button>
              <button class="card filter-card" type="button" data-category="expired" aria-pressed="false"><span class="label">Expiradas</span><span class="value">{{ expiradas }}</span></button>
            </div>
            <section class="filters" aria-label="Filtros de conciliação">
              <label for="search">Buscar por chave, número, fornecedor, local ou cidade
                <input id="search" type="search" placeholder="Digite para filtrar…" autocomplete="off">
              </label>
              <label for="status-filter">Status
                <select id="status-filter">
                  <option value="">Todos os status</option>
                  {% for status in statuses %}<option value="{{ status }}">{{ status }}</option>{% endfor %}
                </select>
              </label>
              <button class="reset" id="reset-filters" type="button">Limpar filtros</button>
            </section>
            <p class="result-count" id="result-count" aria-live="polite"></p>
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Chave / número</th>
                    <th>Fornecedor</th>
                    <th>Local</th>
                    <th>Valor</th>
                    <th>Status</th>
                    <th>Atualizado</th>
                    <th>Ações</th>
                  </tr>
                </thead>
                <tbody id="records">
                {% for item in rows %}
                <tr class="record-row" data-category="{{ item['categoria'] }}" data-status="{{ item['status'] }}" data-search="{{ [item['chave'], item['numero'], item['serie'], item['provedor_nome'], item['local_tipo'], item['local_nome'], item['local_cidade']] | join(' ') }}">
                  <td><span class="key">{{ item['chave'] or '—' }}</span><br>Nº {{ item['numero'] or '—' }}{% if item['serie'] %} · Série {{ item['serie'] }}{% endif %}</td>
                  <td>{{ item['provedor_nome'] or '—' }}</td>
                  <td>{{ item['local_nome'] or '—' }} / {{ item['local_cidade'] or '—' }}</td>
                  <td>R$ {{ '%.2f' % (item['valor_lancado'] or 0) }}</td>
                  <td>
                    <span class="badge" style="background: {{ status_palette.get(item['status'], '#e5e7eb') }};">{{ item['status'] }}</span>
                  </td>
                  <td>{{ item['updated_at'] }}</td>
                  <td><button class="detail-toggle" type="button" aria-expanded="false" aria-controls="details-{{ loop.index }}">Detalhes</button></td>
                </tr>
                <tr class="details-row" id="details-{{ loop.index }}" hidden>
                  <td class="details-cell" colspan="7">
                    <div class="details-grid">
                      <div class="detail-item"><span class="detail-label">Chave</span><span class="detail-value">{{ item['chave'] or '—' }}</span></div>
                      <div class="detail-item"><span class="detail-label">Número / série</span><span class="detail-value">{{ item['numero'] or '—' }} / {{ item['serie'] or '—' }}</span></div>
                      <div class="detail-item"><span class="detail-label">Tipo de local</span><span class="detail-value">{{ item['local_tipo'] or '—' }}</span></div>
                      <div class="detail-item"><span class="detail-label">Valor lançado</span><span class="detail-value">R$ {{ '%.2f' % (item['valor_lancado'] or 0) }}</span></div>
                      <div class="detail-item"><span class="detail-label">Valor pago</span><span class="detail-value">R$ {{ '%.2f' % (item['valor_pago'] or 0) }}</span></div>
                      <div class="detail-item"><span class="detail-label">Diferença (pago − lançado)</span><span class="detail-value">R$ {{ '%.2f' % item['valor_diferenca'] }}</span></div>
                      <div class="detail-item"><span class="detail-label">Data de emissão</span><span class="detail-value">{{ item['data_emissao'] or 'Não informada' }}</span></div>
                      <div class="detail-item"><span class="detail-label">Vencimento</span><span class="detail-value">{{ item['data_vencimento'] or 'Não informado' }}</span></div>
                      <div class="detail-item"><span class="detail-label">Status da conciliação</span><span class="detail-value">{{ item['status'] }}</span></div>
                      <div class="detail-item"><span class="detail-label">Fatura PDF (referência)</span><span class="detail-value">R$ {{ '%.2f' % (item['fatura_valor'] or 0) }} · {{ item['fatura_emissor'] or 'sem emissor' }} · venc. {{ item['fatura_vencimento'] or '—' }}</span></div>
                      <div class="detail-item"><span class="detail-label">Decisão humana (separada)</span><span class="detail-value">{% if item['decisao_humana'] %}{{ item['decisao_humana']['decisao'] }} · {{ item['decisao_humana']['usuario'] }} · {{ item['decisao_humana']['justificativa'] }}{% else %}Não registrada{% endif %}</span></div>
                      <div class="detail-item"><span class="detail-label">Última atualização</span><span class="detail-value">{{ item['updated_at'] or '—' }}</span></div>
                      <div class="detail-item observation"><span class="detail-label">Observação</span><span class="detail-value">{{ item['observacao'] or 'Nenhuma observação registrada.' }}</span></div>
                    </div>
                  </td>
                </tr>
                {% endfor %}
                <tr id="empty-state" hidden><td class="empty" colspan="7">Nenhuma conciliação corresponde aos filtros aplicados.</td></tr>
                </tbody>
              </table>
            </div>
          </div>
          <script>
            (() => {
              const search = document.getElementById('search');
              const status = document.getElementById('status-filter');
              const reset = document.getElementById('reset-filters');
              const resultCount = document.getElementById('result-count');
              const emptyState = document.getElementById('empty-state');
              const rows = [...document.querySelectorAll('.record-row')];
              const cards = [...document.querySelectorAll('.filter-card')];
              let category = '';

              function applyFilters() {
                const query = search.value.trim().toLocaleLowerCase('pt-BR');
                let visible = 0;
                rows.forEach((row) => {
                  const matchesQuery = row.dataset.search.toLocaleLowerCase('pt-BR').includes(query);
                  const matchesStatus = !status.value || row.dataset.status === status.value;
                  const matchesCategory = !category || row.dataset.category === category;
                  const show = matchesQuery && matchesStatus && matchesCategory;
                  row.hidden = !show;
                  const detailsRow = document.getElementById(row.querySelector('.detail-toggle').getAttribute('aria-controls'));
                  if (!show) {
                    detailsRow.hidden = true;
                    const button = row.querySelector('.detail-toggle');
                    button.setAttribute('aria-expanded', 'false');
                    button.textContent = 'Detalhes';
                  }
                  if (show) visible += 1;
                });
                emptyState.hidden = visible > 0;
                resultCount.textContent = `Exibindo ${visible} de ${rows.length} conciliação(ões).`;
              }

              cards.forEach((card) => card.addEventListener('click', () => {
                category = card.dataset.category;
                status.value = '';
                cards.forEach((item) => item.setAttribute('aria-pressed', String(item === card)));
                applyFilters();
              }));
              search.addEventListener('input', applyFilters);
              status.addEventListener('change', () => {
                category = '';
                cards.forEach((card) => card.setAttribute('aria-pressed', String(card.dataset.category === '')));
                applyFilters();
              });
              reset.addEventListener('click', () => {
                search.value = '';
                status.value = '';
                category = '';
                cards.forEach((card) => card.setAttribute('aria-pressed', String(card.dataset.category === '')));
                applyFilters();
              });
              document.querySelectorAll('.detail-toggle').forEach((button) => button.addEventListener('click', () => {
                const detailsRow = document.getElementById(button.getAttribute('aria-controls'));
                const expanded = button.getAttribute('aria-expanded') === 'true';
                button.setAttribute('aria-expanded', String(!expanded));
                button.textContent = expanded ? 'Detalhes' : 'Fechar';
                detailsRow.hidden = expanded;
              }));
              applyFilters();
            })();
          </script>
        </body>
        </html>
        """,
        total=total,
        pagas=pagas,
        pendentes=pendentes,
        divergencias=divergencias,
        expiradas=expiradas,
        rows=rows,
        statuses=statuses,
        status_palette=status_palette,
    )


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
