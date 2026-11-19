"""Documentos da mesma cobrança: o segundo documento de um local/provedor/mês (XML ou NFS-e em PDF, boleto à parte, outro
e-mail) entra como documento adicional e não substitui a fatura principal; associar de novo o mesmo documento não duplica;
divergência confirmada (correção) continua substituindo."""
import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from backend import app as app_module
from backend import database


class DocumentosCobrancaTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp = Path(self.temp_dir.name)
        self.patches = [
            patch.object(database, "DB_PATH", self.temp / "test.db"),
            patch.object(app_module, "FATURAS_DIR", self.temp),
            patch.object(app_module, "NOTAS_RECEBIDAS_DIR", self.temp),
            patch.object(app_module, "API_KEY", ""),
        ]
        for item in self.patches:
            item.start()
        database.init_db()
        self.client = app_module.app.test_client()
        self.local = self.client.post("/api/locais/agencia/item", json={"nome": "Agência Docs", "cidade": "Eunápolis"}).json["item"]["id"]

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp_dir.cleanup()

    DADOS = {"emissorNome": "Infortel", "numero": "4572", "valorTotal": 1880, "dataEmissao": "2026-11-17", "dataVencimento": "2026-12-05"}

    def receber(self, mensagem, anexo, nome):
        r = self.client.post("/api/notas-recebidas", data={
            "gmailMessageId": mensagem, "gmailAttachmentId": anexo, "dadosExtracao": json.dumps(self.DADOS),
            "arquivo": (BytesIO(f"%PDF-1.4 {nome}".encode()), nome)}, content_type="multipart/form-data")
        self.assertIn(r.status_code, (200, 201), r.json)
        return r.json["item"]["id"]

    def associar(self, item_id, **extra):
        r = self.client.patch(f"/api/notas-recebidas/{item_id}/associar",
                              json={"entidadeTipo": "agencia", "entidadeId": self.local, "dados": self.DADOS, **extra})
        self.assertEqual(r.status_code, 200, r.json)
        return r.json

    def test_segundo_documento_da_cobranca_entra_como_adicional(self):
        fatura = self.associar(self.receber("msg-1", "a1", "fatura.pdf"))
        self.assertFalse(fatura["documentoAdicional"])
        danfse = self.associar(self.receber("msg-1", "a2", "nfse.pdf"))
        self.assertTrue(danfse["documentoAdicional"])
        self.assertEqual(danfse["notaLancada"]["id"], fatura["notaLancada"]["id"])
        faturas = database.list_faturas_locais("agencia", self.local)
        self.assertEqual(len(faturas), 2)
        self.assertEqual(sorted(f["nome_arquivo"] for f in faturas), ["fatura.pdf", "nfse.pdf"])
        for f in faturas:  # os dois arquivos continuam no local
            self.assertTrue((self.temp / f["arquivo_storage"]).is_file(), f["nome_arquivo"])
        self.assertEqual(sum(bool(f["dados"].get("documentoAdicional")) for f in faturas), 1)
        # A fatura atual do provedor e a referência da nota continuam sendo a principal.
        principal = next(f for f in faturas if not f["dados"].get("documentoAdicional"))
        self.assertEqual(database.latest_fatura_for_nota(fatura["notaLancada"]["id"])["id"], principal["id"])
        provedor = next(p for p in database.get_local(self.local)["provedores"])
        self.assertEqual(provedor["faturaAtualId"], principal["id"])
        # Um terceiro documento (outro e-mail) também soma; e associar de novo o mesmo documento não duplica.
        terceiro = self.receber("msg-2", "a1", "boleto.pdf")
        self.associar(terceiro)
        self.associar(terceiro)
        self.assertEqual(len(database.list_faturas_locais("agencia", self.local)), 3)
        self.assertEqual(len(database.list_nota_lancadas()), 1)


if __name__ == "__main__":
    unittest.main()
