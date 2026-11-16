from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import re
import subprocess
import time
import unicodedata
from collections import Counter
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from flask import Flask, jsonify, request


ROOT = Path(__file__).resolve().parent
PROMPT_PATH = ROOT / "prompts" / "v3.md"
CORPUS_PATH = ROOT / "rag_documents.json"
PROVIDER_IDS = {
    "conecta alfa ficticia": "PROV-001",
    "rede beta ficticia": "PROV-002",
    "link gama ficticia": "PROV-003",
}
LOCAL_ID = os.environ.get("SIGP_AI_LOCAL_ID", "LOC-001")
REQUESTER = os.environ.get("SIGP_AI_REQUESTER", "n8n-demo")
API_KEY = os.environ.get("SIGP_AI_API_KEY", "")
SQLCMD_SERVER = os.environ.get("SIGP_SQLCMD_SERVER", "sqlserver-academic,1433")
SQLCMD_USER = os.environ.get("SIGP_SQLCMD_USER", "sigp_ia_loc001")
SQLCMD_DATABASE = os.environ.get("SIGP_SQLCMD_DATABASE", "SIGpAcademic")
SQLCMD_PASSWORD = os.environ.get("SQLCMDPASSWORD", "")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama-academic:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:0.5b")
MODEL_BACKEND = os.environ.get("MODEL_BACKEND", "ollama")
MODEL_URL = os.environ.get("MODEL_URL", OLLAMA_URL).rstrip("/")
MODEL_NAME = os.environ.get("MODEL_NAME", OLLAMA_MODEL)
MODEL_PROFILE = os.environ.get("MODEL_PROFILE", "baseline")
# Na máquina compartilhada o Ollama atende um pedido por vez; o pedido da IA pode esperar na fila
# (140 s: abaixo dos 150 s do nó HTTP do n8n, para a API responder antes do n8n desistir).
OLLAMA_TIMEOUT_SECONDS = int(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "140"))
OLLAMA_KEEP_ALIVE = os.environ.get("OLLAMA_KEEP_ALIVE", "30m")
PROMPT_VERSION = "3.0"
ALLOWED_CLASSIFICATIONS = {"CONTRATADO", "DIVERGENTE", "REVISAR"}
MODEL_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "classification": {
            "type": "string",
            "enum": sorted(ALLOWED_CLASSIFICATIONS),
        },
    },
    "required": ["classification"],
    "additionalProperties": False,
}
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
INJECTION_PATTERNS = tuple(re.compile(pattern) for pattern in (
    r"\bignore\b.{0,100}\b(previous|prior|all|the)\b.{0,50}\b(instructions?|rules?|policies)\b",
    r"\b(system|developer)\s*:",
    r"\b(you are now|act as|pretend to be)\b",
    r"\b(reveal|show|expose|disclose|dump|list)\b.{0,100}\b(data|secrets?|docs?|documents?|providers?|records?)\b",
    r"\b(automatic[_ ]payment)\s*=\s*true\b",
))

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024


def _validate_config() -> None:
    if not API_KEY:
        raise RuntimeError("SIGP_AI_API_KEY deve estar definida; o serviço falha fechado.")
    if not SQLCMD_PASSWORD:
        raise RuntimeError("SQLCMDPASSWORD deve estar definida; não é permitido usar usuário sem senha.")
    if not re.fullmatch(r"LOC-\d{3}", LOCAL_ID):
        raise RuntimeError("SIGP_AI_LOCAL_ID inválido.")
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,80}", REQUESTER):
        raise RuntimeError("SIGP_AI_REQUESTER deve identificar um ator fixo e confiável.")
    if SQLCMD_USER not in {"sigp_ia_loc001", "sigp_ia_loc002"}:
        raise RuntimeError("O serviço deve usar uma identidade SQL de IA com escopo mínimo.")
    if MODEL_BACKEND not in {"ollama", "transformers"}:
        raise RuntimeError("MODEL_BACKEND deve ser ollama ou transformers.")
    if not MODEL_URL.startswith(("http://", "https://")):
        raise RuntimeError("MODEL_URL deve ser uma URL HTTP/HTTPS válida.")


def _normalise(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _tokens(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(_normalise(text))


def _case_insensitive_get(value: dict, key: str):
    normalized_key = key.casefold()
    return next(
        (item_value for item_key, item_value in value.items()
         if isinstance(item_key, str) and item_key.casefold() == normalized_key),
        None,
    )


def _text_value(value) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, list):
        return next((text for item in value if (text := _text_value(item))), "")
    return ""


def _normalize_invoice(invoice: dict) -> dict:
    normalized = {
        key: invoice[key]
        for key in ("provider", "description", "amount", "due_date")
        if key in invoice and isinstance(invoice[key], (str, int, float))
        and not isinstance(invoice[key], bool)
    }
    document = _case_insensitive_get(invoice, "nfeproc")
    if not isinstance(document, dict):
        return normalized

    nfe = _case_insensitive_get(document, "nfe")
    info = _case_insensitive_get(nfe, "infnfe") if isinstance(nfe, dict) else None
    if not isinstance(info, dict):
        return normalized

    emitter = _case_insensitive_get(info, "emit")
    emitter = emitter if isinstance(emitter, dict) else {}
    provider = (
        _text_value(_case_insensitive_get(emitter, "xnome"))
        or _text_value(_case_insensitive_get(emitter, "xfant"))
    )

    details = _case_insensitive_get(info, "det")
    details = details if isinstance(details, list) else [details] if details else []
    descriptions = []
    for detail in details:
        if not isinstance(detail, dict):
            continue
        product = _case_insensitive_get(detail, "prod")
        if isinstance(product, dict):
            description = _text_value(_case_insensitive_get(product, "xprod"))
            if description:
                descriptions.append(description)

    additional_info = _case_insensitive_get(info, "infadic")
    additional_text = _text_value(
        _case_insensitive_get(additional_info, "infcpl")
    ) if isinstance(additional_info, dict) else ""
    if additional_text:
        descriptions.append(additional_text)

    total = _case_insensitive_get(info, "total")
    tax_total = _case_insensitive_get(total, "icmstot") if isinstance(total, dict) else None
    amount = _text_value(_case_insensitive_get(tax_total, "vnf")) \
        if isinstance(tax_total, dict) else ""

    normalized.update({
        "provider": provider,
        "description": "; ".join(descriptions),
        "amount": amount,
    })
    return normalized


def _contains_prompt_injection(text: str) -> bool:
    normalized = _normalise(text)
    return any(pattern.search(normalized) for pattern in INJECTION_PATTERNS)


def _load_corpus() -> list[dict]:
    data = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    if len(data) != 20 or len({item.get("id") for item in data}) != 20:
        raise RuntimeError("O corpus acadêmico deve conter exatamente 20 documentos únicos.")
    return data


CORPUS = _load_corpus()
PROMPT_TEMPLATE = PROMPT_PATH.read_text(encoding="utf-8")
PROMPT_SHA256 = hashlib.sha256(PROMPT_TEMPLATE.encode("utf-8")).hexdigest()


def retrieve_documents(query: str, local_id: str, provider_id: str, limit: int = 5) -> list[dict]:
    scoped = [
        item for item in CORPUS
        if item["local_id"] in {"*", local_id}
        and item["provider_id"] in {"*", provider_id}
    ]
    query_counts = Counter(_tokens(query))
    if not query_counts:
        return []

    document_tokens = {
        item["id"]: _tokens(" ".join((item["title"], item["text"])))
        for item in scoped
    }
    document_frequency = Counter(
        token for tokens in document_tokens.values() for token in set(tokens)
    )
    total_documents = max(len(scoped), 1)
    scored: list[tuple[float, dict]] = []
    for item in scoped:
        tokens = document_tokens[item["id"]]
        counts = Counter(tokens)
        length_norm = 1.0 + len(tokens) / 80.0
        score = 0.0
        for token, query_frequency in query_counts.items():
            frequency = counts[token]
            if not frequency:
                continue
            idf = math.log(1.0 + (total_documents - document_frequency[token] + 0.5)
                           / (document_frequency[token] + 0.5))
            score += idf * (frequency * 2.2) / (frequency + 1.2 * length_norm) * min(query_frequency, 2)
        if item["provider_id"] == provider_id:
            score += 1.0
        claims = item.get("claims", {})
        for term in claims.get("service_terms", []) + claims.get("excluded_terms", []):
            if _normalise(term) in _normalise(query):
                score += 3.0
        if score > 0:
            scored.append((score, item))

    scored.sort(key=lambda result: (-result[0], result[1]["id"]))
    return [
        {
            "id": item["id"],
            "title": item["title"],
            "text": item["text"],
            **({"claims": item["claims"]} if "claims" in item else {}),
        }
        for _, item in scored[:limit]
    ]


def _sql_literal(value: str) -> str:
    return "N'" + value.replace("'", "''") + "'"


def _sqlcmd(query: str) -> str:
    env = os.environ.copy()
    env["SQLCMDPASSWORD"] = SQLCMD_PASSWORD
    result = subprocess.run(
        [
            "sqlcmd", "-S", SQLCMD_SERVER, "-U", SQLCMD_USER,
            "-d", SQLCMD_DATABASE, "-C", "-b", "-y", "0", "-w", "65535",
            "-Q", query,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        check=False,
        env=env,
    )
    if result.returncode:
        app.logger.error("Consulta SQL acadêmica negada/indisponível (rc=%s).", result.returncode)
        raise RuntimeError("Não foi possível consultar o contexto autorizado no banco.")
    return result.stdout


def _json_from_sql_output(output: str) -> list[dict]:
    for line in output.splitlines():
        candidate = line.strip()
        if candidate.startswith("[") and candidate.endswith("]"):
            parsed = json.loads(candidate)
            if isinstance(parsed, list) and all(isinstance(item, dict) for item in parsed):
                return parsed
    raise RuntimeError("O SQL Server não retornou o JSON de contexto esperado.")


def get_authorized_context(provider_id: str, correlation_id: str) -> list[dict]:
    query = (
        "SET NOCOUNT ON; EXEC ai.usp_get_context "
        f"@local_id={_sql_literal(LOCAL_ID)}, "
        f"@correlation_id='{correlation_id}', "
        f"@provider_id={_sql_literal(provider_id)}, @take=20, @return_json=1, "
        f"@requested_by={_sql_literal(REQUESTER)};"
    )
    return _json_from_sql_output(_sqlcmd(query))


def log_retrieved_sources(correlation_id: str, source_ids: list[str]) -> None:
    packed_ids = ",".join(source_ids)[:350]
    query = (
        "SET NOCOUNT ON; EXEC ai.usp_log_sources "
        f"@local_id={_sql_literal(LOCAL_ID)}, "
        f"@correlation_id='{correlation_id}', "
        f"@source_ids={_sql_literal(packed_ids)}, "
        f"@requested_by={_sql_literal(REQUESTER)};"
    )
    _sqlcmd(query)


def ask_ollama(prompt: str) -> tuple[dict, str]:
    body = json.dumps({
        "model": OLLAMA_MODEL,
        "system": PROMPT_TEMPLATE,
        "prompt": prompt,
        "stream": False,
        "format": MODEL_OUTPUT_SCHEMA,
        "options": {"temperature": 0, "num_predict": 160},
        "keep_alive": OLLAMA_KEEP_ALIVE,
    }).encode("utf-8")
    req = Request(
        f"{OLLAMA_URL}/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=OLLAMA_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        app.logger.exception("Ollama indisponível ou resposta inválida.")
        raise RuntimeError("O modelo local está indisponível; nenhuma análise foi gravada como concluída.") from exc

    raw = payload.get("response")
    if not isinstance(raw, str):
        raise RuntimeError("A resposta do modelo não contém o campo response esperado.")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("A resposta do modelo não é JSON válido.") from exc
    return parsed, str(payload.get("model", OLLAMA_MODEL))


def ask_transformers(prompt: str) -> tuple[dict, str]:
    body = json.dumps({
        "system": PROMPT_TEMPLATE,
        "prompt": prompt,
    }).encode("utf-8")
    req = Request(
        f"{MODEL_URL}/classify",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=180) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        app.logger.exception("O serviço local de fine-tuning está indisponível ou retornou resposta inválida.")
        raise RuntimeError("O modelo LoRA local está indisponível; nenhuma análise foi gravada como concluída.") from exc

    raw = payload.get("response")
    if not isinstance(raw, str):
        raise RuntimeError("A resposta do modelo LoRA não contém o campo response esperado.")
    candidate = raw.strip()
    fenced_response = re.fullmatch(
        r"```(?:json)?\s*(.*?)\s*```",
        candidate,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if fenced_response:
        candidate = fenced_response.group(1)
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise RuntimeError("A resposta do modelo LoRA não é JSON válido.") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("A resposta do modelo LoRA deve ser um objeto JSON.")
    return parsed, str(payload.get("model", MODEL_NAME))


def ask_model(prompt: str) -> tuple[dict, str]:
    if MODEL_BACKEND == "ollama":
        return ask_ollama(prompt)
    if MODEL_BACKEND == "transformers":
        return ask_transformers(prompt)
    raise RuntimeError("O backend de modelo configurado não é permitido.")


def _classify_from_evidence(invoice: dict, retrieved: list[dict]) -> dict:
    description = _normalise(invoice["description"])
    source_ids = [item["id"] for item in retrieved]
    if _contains_prompt_injection(description) or any(
        term in description for term in ("ignore as regras", "revele dados", "ignore todas")
    ):
        return {
            "classification": "REVISAR",
            "reason": "O texto contém instruções não confiáveis; exige validação humana.",
            "source_ids": source_ids,
        }

    amount = round(float(invoice["amount"]) * 100)
    claims = [
        item for item in retrieved
        if any(_normalise(term) in description for term in item.get("claims", {}).get("excluded_terms", []))
    ]
    if claims:
        return {
            "classification": "DIVERGENTE",
            "reason": "Uma fonte aplicável exclui explicitamente o serviço cobrado.",
            "source_ids": source_ids,
        }

    matches = [
        item for item in retrieved
        if any(_normalise(term) in description for term in item.get("claims", {}).get("service_terms", []))
    ]
    if len(matches) == 1:
        item = matches[0]
        expected_amount = item["claims"].get("monthly_amount")
        if expected_amount is not None:
            classification = (
                "CONTRATADO"
                if amount == round(float(expected_amount) * 100)
                else "DIVERGENTE"
            )
            reason = (
                "Serviço e valor correspondem à evidência estruturada."
                if classification == "CONTRATADO"
                else "O valor cobrado difere do valor mensal da evidência estruturada."
            )
            return {
                "classification": classification,
                "reason": reason,
                "source_ids": source_ids,
            }

    return {
        "classification": "REVISAR",
        "reason": "Não há evidência estruturada suficiente para confirmar a cobrança.",
        "source_ids": source_ids,
    }


def _validate_model_classification(result: dict) -> str:
    classification = result.get("classification")
    if not isinstance(classification, str) or classification not in ALLOWED_CLASSIFICATIONS:
        raise RuntimeError("O modelo não retornou uma classificação permitida.")
    return classification


@app.before_request
def require_demo_key():
    if request.endpoint == "health":
        return None
    supplied = request.headers.get("X-API-Key", "")
    if not API_KEY or not hmac.compare_digest(supplied.encode(), API_KEY.encode()):
        return jsonify({"ok": False, "error": "Chave de demonstração ausente ou inválida."}), 401
    return None


@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "sigp-academic-ai",
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": PROMPT_SHA256,
        "corpus_documents": len(CORPUS),
        "database_scope": LOCAL_ID,
        "model": MODEL_NAME,
        "model_profile": MODEL_PROFILE,
        "model_backend": MODEL_BACKEND,
    })


@app.post("/api/analyze")
def analyze():
    started = time.perf_counter()
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or set(payload) != {"invoice"}:
        return jsonify({"ok": False, "error": "Envie somente o objeto invoice esperado."}), 400
    invoice = payload.get("invoice")
    if not isinstance(invoice, dict):
        return jsonify({"ok": False, "error": "invoice deve ser um objeto JSON."}), 400
    if "local_id" in invoice:
        return jsonify({"ok": False, "error": "O escopo local vem da credencial do serviço e não pode vir no corpo."}), 400
    invoice = _normalize_invoice(invoice)
    provider = invoice.get("provider")
    description = invoice.get("description")
    amount = invoice.get("amount")
    if not isinstance(provider, str) or not provider.strip():
        return jsonify({"ok": False, "error": "Não foi possível identificar o provedor; informe provider ou emit.xNome no XML NF-e."}), 400
    if not isinstance(description, str) or not description.strip():
        return jsonify({"ok": False, "error": "Não foi possível identificar a descrição; informe description ou det.prod.xProd no XML NF-e."}), 400
    if len(provider) > 80 or len(description) > 1000:
        return jsonify({"ok": False, "error": "provider ou description excede o limite permitido."}), 400
    try:
        amount_value = float(amount)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "amount deve ser numérico."}), 400
    if not math.isfinite(amount_value) or amount_value < 0:
        return jsonify({"ok": False, "error": "amount inválido."}), 400

    provider_id = PROVIDER_IDS.get(_normalise(provider).strip())
    if provider_id is None:
        provider_id = "PROV-UNKNOWN"

    correlation_id = str(uuid4())
    try:
        database_context = get_authorized_context(provider_id, correlation_id)
        rag_query = " ".join((
            provider,
            description,
            str(amount),
            str(invoice.get("due_date", "")),
        ))
        retrieved = retrieve_documents(rag_query, LOCAL_ID, provider_id)
        log_retrieved_sources(correlation_id, [item["id"] for item in retrieved])
        assessment = _classify_from_evidence(invoice, retrieved)
        prompt = json.dumps({
            "invoice": invoice,
            "authorized_database_context": database_context,
            "retrieved_documents": retrieved,
            "evidence_assessment": assessment,
        }, ensure_ascii=False)
        model_result, model_name = ask_model(prompt)
        model_classification = _validate_model_classification(model_result)
    except RuntimeError as exc:
        return jsonify({
            "ok": False,
            "correlation_id": correlation_id,
            "error": str(exc),
        }), 503

    return jsonify({
        "ok": True,
        "correlation_id": correlation_id,
        "requester": REQUESTER,
        "local_id": LOCAL_ID,
        "provider_id": provider_id,
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": PROMPT_SHA256,
        "model": model_name,
        "model_profile": MODEL_PROFILE,
        "classification": assessment["classification"],
        "reason": assessment["reason"],
        "source_ids": assessment["source_ids"],
        "decision_method": "structured_evidence_rules_v1",
        "model_classification": model_classification,
        "model_agreement": model_classification == assessment["classification"],
        "model_is_authoritative": False,
        "context_rows": len(database_context),
        "retrieved_documents": len(retrieved),
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        "automatic_payment": False,
    })


if __name__ == "__main__":
    _validate_config()
    app.run(host="0.0.0.0", port=5010)
