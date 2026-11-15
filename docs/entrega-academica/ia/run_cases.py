from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
CASE_FILE = ROOT / "test-cases.json"
CORPUS_FILE = ROOT / "rag_documents.json"
OUTPUT = Path(os.environ.get(
    "SIGP_AI_TEST_OUTPUT",
    str(ROOT.parent / "sqlserver" / "evidence" / "ai-test-results.json"),
))
BASE_URL = "http://127.0.0.1:5010"


def main() -> int:
    api_key = __import__("os").environ.get("SIGP_ACADEMIC_AI_KEY", "")
    if not api_key:
        print("SIGP_ACADEMIC_AI_KEY is required; result not executed.", file=sys.stderr)
        return 2

    cases = json.loads(CASE_FILE.read_text(encoding="utf-8"))
    known_source_ids = {item["id"] for item in json.loads(CORPUS_FILE.read_text(encoding="utf-8"))}
    results = []
    for case in cases:
        body = json.dumps({"invoice": case["invoice"]}, ensure_ascii=False).encode("utf-8")
        req = Request(
            f"{BASE_URL}/api/analyze",
            data=body,
            headers={"Content-Type": "application/json", "X-API-Key": api_key},
            method="POST",
        )
        started = time.perf_counter()
        try:
            with urlopen(req, timeout=150) as response:
                status_code = response.status
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            status_code = exc.code
            payload = json.loads(exc.read().decode("utf-8"))
        except (URLError, TimeoutError) as exc:
            status_code = 0
            payload = {"ok": False, "error": str(exc)}
        measured_ms = round((time.perf_counter() - started) * 1000, 2)
        expected = case["expected"]
        observed_class = payload.get("classification")
        observed_sources = payload.get("source_ids", [])
        source_match = all(source in observed_sources for source in expected["required_source_ids"])
        security_checks = {
            "fixed_local_scope": payload.get("local_id") == "LOC-001",
            "no_automatic_payment": payload.get("automatic_payment") is False,
            "sources_belong_to_corpus": all(source in known_source_ids for source in observed_sources),
        }
        decision_passed = (
            status_code == 200
            and observed_class == expected["classification"]
            and source_match
            and all(security_checks.values())
        )
        model_agreement = payload.get("model_agreement") is True
        full_pass = decision_passed and model_agreement
        results.append({
            "case_id": case["id"],
            "description": case["description"],
            "expected": expected,
            "observed": {
                "http_status": status_code,
                "classification": observed_class,
                "source_ids": observed_sources,
                "correlation_id": payload.get("correlation_id"),
                "prompt_version": payload.get("prompt_version"),
                "prompt_sha256": payload.get("prompt_sha256"),
                "model": payload.get("model"),
                "model_profile": payload.get("model_profile"),
                "model_classification": payload.get("model_classification"),
                "model_agreement": payload.get("model_agreement"),
                "decision_method": payload.get("decision_method"),
                "latency_ms": payload.get("latency_ms", measured_ms),
                "error": payload.get("error"),
            },
            "security_checks": security_checks,
            "security_expectation": case["security_expectation"],
            "decision_passed": decision_passed,
            "model_agreement": model_agreement,
            "full_pass": full_pass,
        })

    report = {
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_url": BASE_URL,
        "case_count": len(results),
        "decision_pass_count": sum(result["decision_passed"] for result in results),
        "model_agreement_count": sum(result["model_agreement"] for result in results),
        "full_pass_count": sum(result["full_pass"] for result in results),
        "results": results,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "report": str(OUTPUT),
        "case_count": report["case_count"],
        "decision_pass_count": report["decision_pass_count"],
        "model_agreement_count": report["model_agreement_count"],
        "full_pass_count": report["full_pass_count"],
        "results": [
            {"case_id": result["case_id"], "decision_passed": result["decision_passed"],
             "model_agreement": result["model_agreement"], "full_pass": result["full_pass"],
             "observed": result["observed"]["classification"],
             "security_checks": result["security_checks"],
             "latency_ms": result["observed"]["latency_ms"]}
            for result in results
        ],
    }, ensure_ascii=False, indent=2))
    return 0 if report["full_pass_count"] == report["case_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
