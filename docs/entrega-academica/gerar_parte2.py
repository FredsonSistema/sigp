"""Relatório da parte 2 (andamento, evidências, identificação e contribuição individual) -> relatorio-parte2.pdf.

Usa o mesmo visual de gerar_pdfs.py e a identificação de identificacao.json. Todos os números vêm dos arquivos de
evidência citados na tabela "Evidências" (pasta sqlserver/evidence/parte2 e seguranca/).
Uso, nesta pasta:  python gerar_parte2.py
"""
from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Spacer

import gerar_pdfs as g

PASTA = Path(__file__).resolve().parent
IDENT = json.loads((PASTA / "identificacao.json").read_text(encoding="utf-8"))
W = 176 * mm  # largura útil (A4 menos margens)


def identificacao() -> list:
    linhas = [["Integrante", "Matrícula"]] + [[i["nome"], i["matricula"]] for i in IDENT["integrantes"]]
    return [
        Spacer(1, 6 * mm),
        g.P("SIGp · PROJETO ACADÊMICO · PARTE 2", "SubTitle"),
        g.P("Relatório de andamento", "CoverTitle"),
        g.P("IA local, segurança e otimização de banco, e integração por n8n — o que foi feito desde a parte 1", "CoverSubtitle"),
        g.P(f"<b>Grupo:</b> {IDENT['grupo']} · <b>Data:</b> {IDENT['data']}", "BodySIGp"),
        g.P(f"<b>Disciplinas:</b> {'; '.join(IDENT['disciplinas'])}", "BodySIGp"),
        g.P(f"<b>Repositório:</b> {IDENT['repositorio']}", "BodySIGp"),
        Spacer(1, 2 * mm),
        g.make_table(linhas, [W * 0.65, W * 0.35]),
        Spacer(1, 3 * mm),
    ]


def andamento() -> list:
    return [
        *g.section("1. Resumo", [g.P(
            "Na parte 1, o protótipo acadêmico (SQL Server com RLS, busca em corpus sintético e Qwen local) funcionava pelo "
            "endpoint direto, e o fluxo n8n estava pendente. Na parte 2, o fluxo n8n roda de ponta a ponta, as permissões foram "
            "testadas com evidência (inclusive a IA sem acesso e tentativa de injeção), o banco ganhou mascaramento e índices "
            "medidos com 100.020 notas, e o SIGp operacional passou a usar a IA local para triagem dos e-mails, sempre com a "
            "decisão final humana. Nada paga sozinho por sugestão da IA; o único pagamento automático vem de um aviso explícito do "
            "provedor (\"pagamento confirmado\"), vinculado a uma única cobrança.")]),
        *g.section("2. Inteligência Artificial", g.bullets([
            "<b>Fluxo n8n de ponta a ponta</b> (pendente na parte 1): webhook → API acadêmica → SQL Server/RLS → RAG → Qwen 0.5B. "
            "Caso \"IP adicional R$ 35,00\" classificado como DIVERGENTE (esperado), só dados do local permitido, sem pagamento automático, 27,8 s com o modelo carregando.",
            "<b>Casos de teste</b>: 5 casos da API — regra 5/5; concordância do modelo 3/5 (a regra decide, o modelo sugere).",
            "<b>Prompts versionados</b> (v4.0 → v4.2, com hash): fatos calculados antes da LLM; exemplos do operador entram como dados, nunca como instrução.",
            "<b>Memória de exemplos</b> (aprende com as decisões do operador, sem fine-tune): teste A/B com nota de hotel — sem exemplos a LLM disse \"nota fiscal\"; com 1 exemplo do mesmo remetente, \"não é cobrança\".",
            "<b>Triagem em três níveis</b> no SIGp operacional (alta / inconclusiva / baixa probabilidade de ser conta de internet); PDF ilegível nunca é ignorado.",
            "<b>Métricas</b> (Painel da IA): acerto da triagem 4 de 6 decididos (67%), campos lidos sem correção 10 de 10 — amostra pequena, apresentada como linha de base.",
            "<b>Custo e latência</b> (CPU, sem GPU, sem custo por token): qwen2.5:0.5b 305 ms por chamada (p95 381 ms); qwen2.5:3b 1.191 ms (p95 2.329 ms).",
            "<b>Fine-tune LoRA</b> mantido da parte 1 (macro-F1 0,522 → 0,900 em 20 exemplos sintéticos): exploratório, não integrado.",
        ])),
        *g.section("3. Segurança e otimização de banco", g.bullets([
            "<b>IA sem permissão</b>: o usuário de banco da IA não lê tabelas nem a view; a procedure só entrega o local permitido; "
            "IA configurada para outro local recebe 503 sem dado; prompt injection responde REVISAR sem vazar outro local.",
            "<b>Auditoria</b>: cada chamada da IA grava quem pediu, o que consultou e quando, inclusive as negações.",
            "<b>Mascaramento dinâmico</b> em chave fiscal e referência; papel com UNMASK só nessas colunas e só no próprio local.",
            "<b>Troca de senhas</b> dos usuários da IA (geradas aleatoriamente; senha antiga recusada).",
            "<b>Perfis e permissões na API do SIGp</b>: administrador fixo, grupos (Gerente, Operador, Leitura, Integração), usuários com chave própria "
            "(guardada só como hash), ajustes individuais e auditoria; 25 funcionalidades catalogadas; matriz testada (403 para o que o perfil não pode).",
            "<b>Otimização</b> (100.020 notas, 15 execuções por configuração): consulta 2 de 33,1 para 16,4 ms e de 4.954 para 7 leituras lógicas; "
            "consulta 1 de 82,7 para 66,2 ms e leituras de Notas de 3.277 para 380. Os índices candidatos da parte 1 não reduziam as leituras; foram substituídos.",
            "<b>Operação do banco do SIGp</b>: backup diário verificado (teste de restauração) com rodízio 7 diários + 4 semanais, verificação de integridade e manutenção pelo n8n às 03:00.",
            "<b>Segredos fora do código</b>: .env fora do repositório; PDFs com senha (Brisanet, Claro) abertos pela regra do CNPJ, sem guardar a senha.",
        ])),
        *g.section("4. Integração", g.bullets([
            "Gmail → n8n (WF-08) → OCR local → regras do SIGp → Qwen local → SIGp; avisos sem PDF (pagamento confirmado, atraso) entram pelo mesmo fluxo.",
            "Alertas: vencimento, fatura que não chegou no prazo esperado, fatura na caixa sem associar e leitura do Gmail parada.",
            "Integração configurável na tela (endereços, chaves e webhooks com balões de ajuda; nada fixo no código): o sistema pode ser trocado mantendo Docker, n8n e e-mail.",
        ])),
        *g.section("5. Limites e próximos passos", g.bullets([
            "Amostras pequenas (6 documentos decididos; 5 casos de API): números são linha de base, não desempenho garantido.",
            "Leitura na API do SIGp ainda é liberada sem chave (gravação exige); ligar a exigência após ajustar downloads e workflows.",
            "Embeddings/Qdrant não implementados (busca lexical); LoRA não integrado; SIGp operacional segue em SQLite (o SQL Server é o ambiente acadêmico).",
            "Até 25/11: alertas por e-mail, associação em lote com prévia, contrato da API (OpenAPI) e conector no n8n.",
        ])),
    ]


def evidencias() -> list:
    e = "sqlserver/evidence/parte2/"
    linhas = [["Arquivo", "O que comprova"],
              [f"{e}n8n-ponta-a-ponta.json", "Fluxo n8n → API → SQL Server/RLS → RAG → Qwen, resultado DIVERGENTE"],
              [f"{e}ai-test-results.json · ia/casos-de-teste-parte2.md", "5 casos: regra 5/5, modelo 3/5"],
              [f"{e}ia-permissao-e-injecao.json · {e}auditoria-ia.txt", "IA sem permissão (503), injeção barrada, auditoria"],
              [f"{e}mascaramento.txt", "Mascaramento dinâmico e UNMASK por papel"],
              [f"{e}benchmark-tempos.txt · leituras-logicas.txt · *.sqlplan", "Tempos, leituras e planos A/B/C"],
              [f"{e}latencia-custo.json", "Latência e custo dos modelos locais"],
              [f"{e}memoria-exemplos-ab.json · teste-inverso-nao-internet.json", "Aprendizado por exemplos e teste com documento que não é internet"],
              ["seguranca/permissoes-perfis.md · seguranca/evidence/permissoes-perfis.json", "Matriz de perfis e permissões da API e auditoria"],
              ["ia/prompts/CHANGELOG.md · v4.md · v4.1.md", "Versões dos prompts com hash"],
              ["../registro-mudancas.md", "Antes e depois de cada mudança, com a verificação feita"]]
    return g.section("6. Evidências", [g.make_table(linhas, [W * 0.52, W * 0.48], small=True)])


def contribuicao() -> list:
    linhas = [["Integrante", "Contribuição"]] + [[i["nome"], i["contribuicao"]] for i in IDENT["integrantes"]]
    return g.section("7. Contribuição individual", [g.make_table(linhas, [W * 0.3, W * 0.7])])


def main() -> None:
    story = identificacao() + andamento() + [PageBreak()] + evidencias() + [Spacer(1, 4 * mm)] + contribuicao()
    g.build_pdf(PASTA / "relatorio-parte2.pdf", "SIGp — Relatório da parte 2", story)
    print("ok: relatorio-parte2.pdf")


if __name__ == "__main__":
    main()
