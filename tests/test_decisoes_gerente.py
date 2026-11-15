"""Fase C: análise SIG aguarda o gerente; validar/corrigir/devolver com auditoria e evento para o n8n."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import app as app_module
from backend import database


class DecisoesGerenteTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.patches = [
            patch.object(database, "DB_PATH", Path(self.temp_dir.name) / "test.db"),
            patch.object(app_module, "API_KEY", ""),
            patch.object(app_module.events, "webhook_url", lambda: ""),  # não tenta entregar ao n8n no teste
        ]
        for item in self.patches:
            item.start()
        database.init_db()
        self.client = app_module.app.test_client()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp_dir.cleanup()

    def analise(self, referencia="nota-1", requer=True):
        r = self.client.post("/api/analises", json={
            "escopo": "SIG", "titulo": "Ciclo fechado · Garagem X · NF 302500", "referencia": referencia,
            "conteudo": "Análise da LLM local.", "modelo": "qwen2.5:3b (local)",
            "dados": {"status": "MATCH", "requerValidacao": requer, "provedor": "OPIX INTERNET"},
        })
        self.assertEqual(r.status_code, 200)
        return r.get_json()["item"]

    def decidir(self, analise_id, acao, **extra):
        return self.client.post("/api/sig/decisoes", json={"analiseId": analise_id, "acao": acao, "usuario": "gerente", **extra})

    def test_analise_que_requer_validacao_fica_pendente(self):
        item = self.analise()
        self.assertEqual(item["status_validacao"], "PENDENTE")
        self.assertEqual(self.analise("nota-2", requer=False)["status_validacao"], "")
        pendentes = self.client.get("/api/analises?escopo=SIG&status=PENDENTE").get_json()["items"]
        self.assertEqual([p["id"] for p in pendentes], [item["id"]])

    def test_nova_analise_do_mesmo_ciclo_substitui_a_pendente(self):
        antiga = self.analise()
        nova = self.analise()
        self.assertEqual(database.get_analise(antiga["id"])["status_validacao"], "SUBSTITUIDA")
        self.assertEqual(database.get_analise(nova["id"])["status_validacao"], "PENDENTE")

    def test_validar_registra_auditoria_e_avisa_o_n8n(self):
        item = self.analise()
        r = self.decidir(item["id"], "validar")
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()["analise"]["status_validacao"], "VALIDADA")
        self.assertEqual(r.get_json()["analise"]["validado_por"], "gerente")
        eventos = [e for e in database.list_eventos("", 20) if e["evento"] == "decisao_gerente"]
        self.assertEqual(len(eventos), 1)
        self.assertEqual(self.client.get(f"/api/sig/decisoes?analiseId={item['id']}").get_json()["items"][0]["acao"], "validar")
        self.assertEqual(self.decidir(item["id"], "validar").status_code, 409)  # uma decisão por análise

    def test_corrigir_e_devolver_exigem_justificativa(self):
        item = self.analise()
        self.assertEqual(self.decidir(item["id"], "devolver").status_code, 400)
        self.assertEqual(self.decidir(item["id"], "corrigir", justificativa="valor errado").status_code, 400)
        r = self.decidir(item["id"], "corrigir", justificativa="valor errado", conteudoCorrigido="Ciclo confere após ajuste.")
        self.assertEqual(r.get_json()["decisao"]["status"], "CORRIGIDA")
        self.assertEqual(self.decidir(self.analise("nota-3")["id"], "devolver", justificativa="faltou a fatura").status_code, 200)

    def test_analise_sem_pendencia_nao_aceita_decisao(self):
        item = self.analise(requer=False)
        self.assertEqual(self.decidir(item["id"], "validar").status_code, 409)
        self.assertEqual(self.decidir("nao-existe", "validar").status_code, 404)


if __name__ == "__main__":
    unittest.main()
