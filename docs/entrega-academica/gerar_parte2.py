"""Entrega 2 (relatorio-parte2.pdf), na ordem do enunciado: identificação; parte comum (relatório de andamento,
repositório e como rodar, contribuição individual); parte de IA; parte de Segurança; parte de Integração.

Interface do projeto: terminal (PowerShell), API e n8n — sem site nem aplicação web. Os números vêm das evidências
citadas; os "prints" são trechos da execução real de demo-parte2.ps1 (sqlserver/evidence/parte2/demo-parte2-saida.txt).
Identificação em identificacao.json. Uso, nesta pasta:  python gerar_parte2.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, PageBreak, Spacer, XPreformatted

import gerar_pdfs as g

PASTA = Path(__file__).resolve().parent
IDENT = json.loads((PASTA / "identificacao.json").read_text(encoding="utf-8"))
SAIDA_DEMO = PASTA / "sqlserver" / "evidence" / "parte2" / "demo-parte2-saida.txt"
W = 176 * mm
E = "sqlserver/evidence/parte2/"

MONO = g.FONT
for nome, arquivo in (("Consolas", r"C:\Windows\Fonts\consola.ttf"), ("Cascadia", r"C:\Windows\Fonts\CascadiaMono.ttf")):
    if Path(arquivo).exists():
        pdfmetrics.registerFont(TTFont(nome, arquivo))
        MONO = nome
        break
ESTILO_PRINT = ParagraphStyle("PrintSIGp", fontName=MONO, fontSize=6.6, leading=8.2, textColor=g.INK,
                              backColor=g.PALE, borderColor=g.colors.HexColor("#C6D3DC"), borderWidth=0.4,
                              borderPadding=4, leftIndent=4, rightIndent=4, spaceBefore=4, spaceAfter=8)


def passos_demo() -> dict:
    """Trechos da saída real da demonstração, por passo."""
    if not SAIDA_DEMO.exists():
        return {}
    texto = SAIDA_DEMO.read_text(encoding="utf-8-sig", errors="replace").replace("\r\n", "\n")
    texto = re.sub(r"\x1b?\[[0-9;]*m", "", texto)
    partes = re.split(r"\n=+\n PASSO (\d+) \S+ ", texto)
    blocos = {}
    for i in range(1, len(partes) - 1, 2):
        linhas = [l.rstrip() for l in partes[i + 1].splitlines()]
        titulo = linhas[0]
        resto = [l for l in linhas[1:] if l.strip() and not set(l.strip()) <= {"="}]
        blocos[int(partes[i])] = (titulo, resto[1:])  # pula a frase explicativa
    return blocos


def print_texto(passos: dict, numero: int, filtro=None, maximo: int = 18) -> list:
    if numero not in passos:
        return [g.P("(Execute demo-parte2.ps1 -SemPausa para gerar este print.)", "SmallSIGp")]
    titulo, linhas = passos[numero]
    if filtro:
        linhas = [l for l in linhas if re.search(filtro, l)]
    corte = [(l[:118] + "…") if len(l) > 119 else l for l in linhas[:maximo]]
    texto = "\n".join(corte).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return [g.P(f"<b>Print (terminal) · passo {numero}:</b> {titulo}", "SmallSIGp"), XPreformatted(texto, ESTILO_PRINT)]


def tabela_requisitos(linhas: list) -> list:
    return [g.make_table([["Exigência", "O que foi feito", "Evidência"]] + linhas, [W * 0.24, W * 0.46, W * 0.30], small=True)]


def identificacao() -> list:
    nomes = [[i["nome"]] + ([i["matricula"]] if i["matricula"] else []) for i in IDENT["integrantes"]]
    cab = ["Integrante"] + (["Matrícula"] if any(i["matricula"] for i in IDENT["integrantes"]) else [])
    larg = [W] if len(cab) == 1 else [W * 0.65, W * 0.35]
    return [
        g.P("SIGp · PROJETO INTEGRADOR · ENTREGA 2", "SubTitle"),
        g.P("Auditoria de faturas de provedores com IA local", "CoverTitle"),
        g.P("Parte comum, Parte de IA, Parte de Segurança e Parte de Integração (a equipe cursa as duas disciplinas)", "CoverSubtitle"),
        g.P(f"<b>Data:</b> {IDENT['data']} · <b>Disciplinas:</b> {'; '.join(IDENT['disciplinas'])}"
            + (f" · <b>Grupo:</b> {IDENT['grupo']}" if IDENT['grupo'] else ""), "BodySIGp"),
        g.P(f"<b>Repositório:</b> {IDENT['repositorio']} · <b>Interface:</b> terminal (PowerShell), API e n8n — sem site nem aplicação web · "
            "<b>Dados:</b> só fictícios ou anonimizados · <b>Segredos:</b> fora do repositório (.env).", "BodySIGp"),
        g.make_table([cab] + nomes, larg),
        Spacer(1, 2 * mm),
    ]


def parte_comum() -> list:
    return [
        *g.section("1. Relatório de andamento", [
            g.P("<b>O que já funciona.</b> O fluxo de ponta a ponta roda: o n8n recebe a fatura (webhook), chama a API, que lê do SQL Server "
                "só o contexto do local permitido (RLS), busca as fontes no corpus de 20 documentos fictícios (RAG) e pede a sugestão ao Qwen local. "
                "A regra decide (DIVERGENTE no caso do IP adicional de R$ 35); o modelo só sugere e nada é pago sozinho. Os 5 casos de teste "
                "batem com a regra (5/5) e o modelo concorda em 3/5. Papéis com GRANT e DENY, RLS e mascaramento estão aplicados e testados; "
                "a base tem 100.020 notas e as duas consultas lentas têm plano e melhoria medida. A IA sem permissão não obtém dado, "
                "a tentativa de prompt injection é barrada, e cada consulta da IA fica na auditoria. O fine-tuning LoRA tem resultado preliminar."),
            g.P("<b>O que falta.</b> Embeddings e banco vetorial (o RAG usa busca lexical); integrar o adaptador LoRA ao serviço; ampliar os casos "
                "de teste (hoje 5) e repetir as métricas com mais exemplos; exigir chave também na leitura da API do sistema operacional."),
            g.P("<b>O que mudou na arquitetura desde 27/10.</b> (1) O n8n entrou no caminho real da IA (antes o endpoint era chamado direto e o workflow "
                "estava inativo). (2) Mascaramento dinâmico e o papel fiscal com UNMASK só nas colunas sensíveis. (3) Índices refeitos: os candidatos "
                "de 27/10 não reduziam as leituras; os ajustados reduziram (configuração C). (4) A IA passou a aprender com as decisões do operador "
                "por exemplos no prompt, sem treinar o modelo, e a classificar e-mails reais do Gmail em três níveis. (5) Perfis e permissões também na "
                "API do sistema (grupos, chave por usuário, auditoria). (6) Ambiente leve: SQL Server limitado a 2 GB e um só Ollama para tudo."),
            g.P("<b>Principais riscos.</b> A IA errar ou ser enganada: o modelo concorda com a regra só em 3/5, por isso a regra decide e há aprovação "
                "humana; prompt injection é testado a cada versão. Vazamento entre locais: RLS, IA sem leitura direta e teste de perfil sem permissão. "
                "Amostras pequenas: os números são linha de base. Desempenho em CPU: 0,3 s (0,5B) a 1,2 s (3B) por chamada, mais o OCR nos PDFs reais."),
        ]),
        *g.section("2. Repositório e como rodar", [
            g.P(f"Repositório: <b>{IDENT['repositorio']}</b>. O README da raiz explica como subir os containers e rodar as demonstrações. "
                "Tudo pelo terminal, na raiz do projeto (PowerShell):"),
            XPreformatted("docker compose --env-file docs/entrega-academica/sqlserver/.env.academic `\n"
                          "  -f docs/entrega-academica/sqlserver/compose.academic.yml `\n"
                          "  -f docs/entrega-academica/sqlserver/compose.leve.yml up -d\n"
                          "pwsh -File docs/entrega-academica/demo-parte2.ps1          # todos os passos, com pausa (vídeo)\n"
                          "pwsh -File docs/entrega-academica/demo-parte2.ps1 -SemPausa  # gera os prints deste PDF", ESTILO_PRINT),
            g.P("Antes, uma vez: pwsh -File docs/entrega-academica/sqlserver/setup-academic.ps1 (cria o banco, os papéis e a carga e gera as senhas aleatórias em .env.academic, fora do repositório; as variáveis estão descritas em .env.academic.example).", "SmallSIGp"),
        ]),
        *g.section("3. Contribuição individual", [g.make_table(
            [["Integrante", "O que fez no projeto"]] + [[i["nome"], i["contribuicao"]] for i in IDENT["integrantes"]], [W * 0.26, W * 0.74], small=True)]),
    ]


def parte_ia(p: dict) -> list:
    return [
        *g.section("4. Parte de IA", tabela_requisitos([
            ["Fluxo de ponta a ponta (RAG e n8n)", "Webhook n8n → API → SQL Server/RLS → RAG (5 fontes citadas) → Qwen 0.5B local. Resultado DIVERGENTE, modelo não decide, sem pagamento automático.",
             f"Print abaixo; {E}n8n-ponta-a-ponta.json; demo-parte2.ps1 (passo 1)"],
            ["Prompts versionados", "Versão atual v4.2 (com hash). Em relação à v4.1: campo novo de tipo de e-mail (fatura, 2ª via, atraso, pagamento) e o provedor vem só do documento atual (antes a IA copiava de um exemplo).",
             "ia/prompts/CHANGELOG.md; v4.md; v4.1.md"],
            ["5 casos de teste (entrada, esperado, obtido)", "IA-001 a IA-005: regra 5/5; modelo concorda 3/5; IA-004 é prompt injection e é barrado.", f"ia/casos-de-teste-parte2.md; {E}ai-test-results.json"],
            ["Fine-tuning preliminar", "LoRA (rank 4) no Qwen2.5-0.5B-Instruct, 80 exemplos de treino, 20 de teste: base acurácia 0,65 e macro-F1 0,522; ajustado 0,90 e 0,900. Dados sintéticos; exploratório.",
             "ia/finetuning/training-results.json; README"],
            ["Custo e latência", "CPU, sem GPU: 0,5B 305 ms (p95 381); 3B 1.191 ms (p95 2.329). Sem custo por token; 1.000 usos = 5,1 min de CPU (0,5B) ou 19,9 min (3B).",
             f"{E}latencia-custo.json"],
        ])),
        *print_texto(p, 1), *print_texto(p, 2, r"^\| IA-0|^base|^LoRA|mediana", 10),
    ]


def parte_seguranca(p: dict) -> list:
    return [
        *g.section("5. Parte de Segurança e Otimização", tabela_requisitos([
            ["Papéis e permissões (scripts, GRANT, DENY, permitido e negado)", "Papéis sigp_api, sigp_auditor e sigp_ia; DENY de DELETE para a aplicação e de leitura direta para a IA. Teste: 50 linhas permitidas do LOC-001; leitura direta, outro local, DELETE e principal sem papel negados (PASS).",
             "sqlserver/01_schema_seed.sql; 02_security_tests.sql; evidence/security-tests.txt"],
            ["Proteção de dado sensível", "RLS por local + mascaramento dinâmico na chave fiscal e na referência; papel fiscal com UNMASK só nessas colunas; auditor não lê a tabela; a view da IA não tem a chave.",
             f"sqlserver/07_mascaramento_parte2.sql; {E}mascaramento.txt"],
            ["Base com volume", "100.020 notas, 100.020 itens, 50.010 pagamentos (dados sintéticos).", "Print abaixo (contagem ao vivo)"],
            ["2 consultas lentas com plano", "Consulta 2: 33,1 → 16,4 ms e 4.954 → 7 leituras lógicas; consulta 1: 82,7 → 66,2 ms e leituras de Notas 3.277 → 380 (15 execuções cada).",
             f"{E}benchmark-tempos.txt; leituras-logicas.txt; A/B/C-consulta1/2.sqlplan"],
        ])),
        *print_texto(p, 3, None, 22), *print_texto(p, 4, None, 14), *print_texto(p, 5, None, 18),
    ]


def parte_integracao(p: dict) -> list:
    return [
        *g.section("6. Parte de Integração", tabela_requisitos([
            ["A IA respeita as permissões", "IA configurada para outro local com credencial do LOC-001: o banco nega (HTTP 503) e nenhum dado do LOC-002 sai. Fatura com instrução maliciosa: REVISAR, só LOC-001, sem pagamento.",
             f"sqlserver/testar-ia-permissao.ps1; {E}ia-permissao-e-injecao.json"],
            ["Auditoria inicial", "Cada chamada grava quem pediu (ator), o que consultou (objeto, linhas, fontes do RAG) e quando, inclusive as negações (AI_CONTEXT_DENIED).",
             f"tabela audit.Eventos; {E}auditoria-ia.txt"],
            ["Permissões também na API do sistema", "Administrador, Gerente, Operador e Leitura com chave própria; 403 para o que o perfil não pode; recusas na auditoria.",
             "seguranca/permissoes-perfis.md; seguranca/evidence/permissoes-perfis.json"],
        ])),
        *print_texto(p, 6, None, 6), *print_texto(p, 7, None, 10), *print_texto(p, 8, r"^\||Auditoria", 9),
    ]


def main() -> None:
    p = passos_demo()
    story = identificacao() + parte_comum() + [PageBreak()] + parte_ia(p) + [PageBreak()] + parte_seguranca(p) + [PageBreak()] + parte_integracao(p)
    g.build_pdf(PASTA / "relatorio-parte2.pdf", "SIGp — Entrega 2", story)
    print("ok: relatorio-parte2.pdf")


if __name__ == "__main__":
    main()
