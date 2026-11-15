import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import buscador_nfse


class ManualDecisionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(buscador_nfse, "DB_PATH", Path(self.temp_dir.name) / "sie.db")
        self.db_patch.start()
        self.client = buscador_nfse.app.test_client()
        response = self.client.post("/api/conciliacoes", json={
            "chave": "nf-chave-1",
            "numero": "123",
            "provedorNome": "Provedor",
            "localNome": "Agência Centro",
            "valor": 100,
            "valorPago": 100,
            "dataVencimento": "2026-10-10",
            "status": "DIVERGENCIA_CADASTRAL",
            "faturaValor": 120,
            "faturaVencimento": "2026-10-10",
            "faturaEmissor": "Provedor",
        })
        self.assertEqual(response.status_code, 200)

    def tearDown(self):
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def test_decision_audits_corrections_without_changing_automatic_status(self):
        response = self.client.post("/api/sig/decisoes", json={
            "id": "decision-1",
            "chave": "nf-chave-1",
            "decisao": "APROVADA",
            "usuario": "Ana",
            "justificativa": "PDF conferido com o contrato vigente.",
            "dadosCorrigidos": {
                "valorLancado": 120,
                "faturaValor": 120,
                "faturaVencimento": "2026-10-10",
            },
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["item"]["dados_anteriores"]["valorLancado"], 100)
        self.assertEqual(response.json["item"]["dados_corrigidos"]["valorLancado"], 120)

        automatic = self.client.get("/api/conciliacoes").json["items"][0]
        self.assertEqual(automatic["status"], "DIVERGENCIA_CADASTRAL")
        self.assertEqual(automatic["valor_lancado"], 100)

        decision = self.client.get("/api/sig/decisoes").json["items"][0]["decisao_humana"]
        self.assertEqual(decision["decisao"], "APROVADA")
        history = self.client.get("/api/sig/decisoes/nf-chave-1").json["items"]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["justificativa"], "PDF conferido com o contrato vigente.")

    def test_same_decision_id_is_idempotent_and_required_audit_fields_are_validated(self):
        payload = {
            "id": "decision-repeat",
            "chave": "nf-chave-1",
            "decisao": "REJEITADA",
            "usuario": "Bruno",
            "justificativa": "Dados insuficientes.",
            "dadosCorrigidos": {},
        }
        self.assertEqual(self.client.post("/api/sig/decisoes", json=payload).status_code, 201)
        repeated = self.client.post("/api/sig/decisoes", json=payload)
        self.assertEqual(repeated.status_code, 200)
        self.assertTrue(repeated.json["idempotente"])

        invalid = self.client.post("/api/sig/decisoes", json={
            **payload,
            "id": "decision-invalid",
            "justificativa": "",
        })
        self.assertEqual(invalid.status_code, 400)
        rows = self.client.get("/api/sig/decisoes/nf-chave-1").json["items"]
        self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
