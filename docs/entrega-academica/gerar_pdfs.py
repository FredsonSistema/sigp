from __future__ import annotations

from pathlib import Path
from textwrap import wrap

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    PageTemplate,
    PageBreak,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parent
OUT = ROOT
NAVY = colors.HexColor("#15324B")
BLUE = colors.HexColor("#245B82")
TEAL = colors.HexColor("#178F8A")
PALE = colors.HexColor("#EAF2F7")
MINT = colors.HexColor("#E6F4F1")
INK = colors.HexColor("#243746")
MUTED = colors.HexColor("#5E7180")
GOLD = colors.HexColor("#D69A2D")
RED = colors.HexColor("#A83B3B")
WHITE = colors.white

# Identificação: um arquivo só para todos os PDFs (identificacao.json, nesta pasta).
import json as _json

_IDENT = _json.loads((Path(__file__).resolve().parent / "identificacao.json").read_text(encoding="utf-8"))
TEAM = [(i["nome"], i["matricula"]) for i in _IDENT["integrantes"]]
_PENDENTE = [i["nome"] for i in _IDENT["integrantes"] if "confirmar" in i["matricula"]]
TEAM_NOTE = (
    (f"Grupo: {_IDENT['grupo']}. " if _IDENT["grupo"] else "")
    + "Integrantes: " + "; ".join(f"{n} (matrícula {m})" if m else n for n, m in TEAM) + "."
)
DATE_LABEL = "2 de novembro de 2026"


def register_fonts() -> None:
    candidates = [
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path(r"C:\Windows\Fonts\Arial.ttf"),
    ]
    bold_candidates = [
        Path(r"C:\Windows\Fonts\arialbd.ttf"),
        Path(r"C:\Windows\Fonts\Arialbd.ttf"),
    ]
    regular = next((path for path in candidates if path.exists()), None)
    bold = next((path for path in bold_candidates if path.exists()), None)
    if regular and bold:
        pdfmetrics.registerFont(TTFont("SIGpSans", str(regular)))
        pdfmetrics.registerFont(TTFont("SIGpSans-Bold", str(bold)))
        pdfmetrics.registerFontFamily(
            "SIGpSans", normal="SIGpSans", bold="SIGpSans-Bold",
            italic="SIGpSans", boldItalic="SIGpSans-Bold",
        )


register_fonts()
FONT = "SIGpSans" if "SIGpSans" in pdfmetrics.getRegisteredFontNames() else "Helvetica"
FONT_BOLD = "SIGpSans-Bold" if "SIGpSans-Bold" in pdfmetrics.getRegisteredFontNames() else "Helvetica-Bold"

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
    name="CoverTitle", fontName=FONT_BOLD, fontSize=26, leading=31,
    textColor=NAVY, alignment=TA_LEFT, spaceAfter=8 * mm,
))
styles.add(ParagraphStyle(
    name="CoverSubtitle", fontName=FONT, fontSize=12, leading=17,
    textColor=MUTED, alignment=TA_LEFT, spaceAfter=5 * mm,
))
styles.add(ParagraphStyle(
    name="SectionTitle", fontName=FONT_BOLD, fontSize=19, leading=24,
    textColor=NAVY, spaceBefore=2 * mm, spaceAfter=4 * mm, keepWithNext=True,
))
styles.add(ParagraphStyle(
    name="SubTitle", fontName=FONT_BOLD, fontSize=12, leading=16,
    textColor=BLUE, spaceBefore=3 * mm, spaceAfter=2 * mm, keepWithNext=True,
))
styles.add(ParagraphStyle(
    name="BodySIGp", fontName=FONT, fontSize=9.2, leading=13,
    textColor=INK, spaceAfter=2.2 * mm, alignment=TA_LEFT,
))
styles.add(ParagraphStyle(
    name="SmallSIGp", fontName=FONT, fontSize=7.3, leading=9.6,
    textColor=INK, spaceAfter=0.8 * mm,
))
styles.add(ParagraphStyle(
    name="TinySIGp", fontName=FONT, fontSize=6.4, leading=8.1,
    textColor=INK,
))
styles.add(ParagraphStyle(
    name="BulletSIGp", parent=styles["BodySIGp"], leftIndent=5 * mm,
    firstLineIndent=-3 * mm, bulletIndent=0, spaceAfter=1.5 * mm,
))
styles.add(ParagraphStyle(
    name="CalloutSIGp", fontName=FONT_BOLD, fontSize=9, leading=13,
    textColor=NAVY, backColor=PALE, borderColor=BLUE, borderWidth=0.6,
    borderPadding=7, spaceBefore=2 * mm, spaceAfter=3 * mm,
))
styles.add(ParagraphStyle(
    name="TableHeadSIGp", fontName=FONT_BOLD, fontSize=7.1, leading=9,
    textColor=WHITE,
))
styles.add(ParagraphStyle(
    name="TableCellSIGp", fontName=FONT, fontSize=6.9, leading=8.8,
    textColor=INK,
))
styles.add(ParagraphStyle(
    name="TableCellSmallSIGp", fontName=FONT, fontSize=6.1, leading=7.6,
    textColor=INK,
))


def P(text: str, style: str = "BodySIGp") -> Paragraph:
    return Paragraph(text, styles[style])


def bullets(items: list[str]) -> list[Paragraph]:
    return [Paragraph(f"• {item}", styles["BulletSIGp"]) for item in items]


def section(title: str, body: list) -> list:
    return [Paragraph(title, styles["SectionTitle"]), *body]


def make_table(rows: list[list[str]], widths: list[float], small: bool = False) -> Table:
    cell_style = "TableCellSmallSIGp" if small else "TableCellSIGp"
    converted = []
    for row_index, row in enumerate(rows):
        row_style = "TableHeadSIGp" if row_index == 0 else cell_style
        converted.append([Paragraph(str(cell), styles[row_style]) for cell in row])
    table = Table(converted, colWidths=widths, repeatRows=1, hAlign="LEFT", splitByRow=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C6D3DC")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, PALE]),
    ]))
    return table


class CanvasDiagram(Flowable):
    def __init__(self, width: float = 174 * mm, height: float = 87 * mm):
        super().__init__()
        self.width = width
        self.height = height

    def draw(self) -> None:
        c = self.canv
        c.setFillColor(PALE)
        c.roundRect(0, 0, self.width, self.height, 8, fill=1, stroke=0)
        cells = [
            ("PROBLEMA", "Contas chegam em documentos e horários diferentes; risco de atraso, valor divergente ou serviço indevido."),
            ("USUÁRIO", "Responsável por contas e auditor/financeiro. A decisão final permanece humana."),
            ("ENTRADAS", "PDF de fatura; XML/JSON de nota lançada e paga; dados sempre fictícios na demonstração."),
            ("SAÍDAS", "Conciliação, divergências com evidências, pendências de revisão e auditoria."),
            ("ARQUITETURA", "CLI/API → n8n + OCR → banco SQL; RAG local → LLM local, sem acesso direto ao banco."),
            ("MVP · 3 SEMANAS", "SQL Server com seed sintético, consultas medidas, testes defensivos, fluxo RAG e demonstração CLI."),
        ]
        gap = 5 * mm
        cell_w = (self.width - 4 * gap) / 3
        cell_h = (self.height - 3 * gap) / 2
        for index, (heading, text) in enumerate(cells):
            col = index % 3
            row = index // 3
            x = gap + col * (cell_w + gap)
            y = self.height - gap - (row + 1) * cell_h - row * gap
            c.setFillColor(WHITE)
            c.roundRect(x, y, cell_w, cell_h, 5, fill=1, stroke=0)
            c.setFillColor(TEAL if row else BLUE)
            c.roundRect(x, y + cell_h - 8 * mm, cell_w, 8 * mm, 5, fill=1, stroke=0)
            c.rect(x, y + cell_h - 8 * mm, cell_w, 3 * mm, fill=1, stroke=0)
            c.setFillColor(WHITE)
            c.setFont(FONT_BOLD, 7.1)
            c.drawString(x + 3 * mm, y + cell_h - 5.3 * mm, heading)
            c.setFillColor(INK)
            c.setFont(FONT, 7.1)
            words = text.split()
            lines: list[str] = []
            current = ""
            for word in words:
                candidate = f"{current} {word}".strip()
                if c.stringWidth(candidate, FONT, 7.1) > cell_w - 6 * mm:
                    lines.append(current)
                    current = word
                else:
                    current = candidate
            if current:
                lines.append(current)
            line_y = y + cell_h - 12 * mm
            for line in lines[:7]:
                c.drawString(x + 3 * mm, line_y, line)
                line_y -= 3.2 * mm


class OrgChart(Flowable):
    def __init__(self, width: float = 174 * mm, height: float = 79 * mm):
        super().__init__()
        self.width = width
        self.height = height

    def _box(self, x, y, w, h, title, detail, color):
        c = self.canv
        c.setFillColor(WHITE)
        c.setStrokeColor(colors.HexColor("#B7C7D1"))
        c.roundRect(x, y, w, h, 5, fill=1, stroke=1)
        c.setFillColor(color)
        c.roundRect(x, y + h - 9 * mm, w, 9 * mm, 5, fill=1, stroke=0)
        c.rect(x, y + h - 9 * mm, w, 3 * mm, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont(FONT_BOLD, 7.1)
        c.drawCentredString(x + w / 2, y + h - 5.8 * mm, title)
        c.setFillColor(INK)
        c.setFont(FONT, 6.7)
        lines = wrap(detail, width=max(10, int(w / 2.2)))
        baseline = y + h - 13 * mm
        for line in lines[:4]:
            c.drawCentredString(x + w / 2, baseline, line)
            baseline -= 3.5 * mm

    def draw(self) -> None:
        c = self.canv
        root_w = 72 * mm
        root_h = 19 * mm
        root_x = (self.width - root_w) / 2
        root_y = self.height - root_h - 2 * mm
        self._box(root_x, root_y, root_w, root_h, "COORDENAÇÃO DO PROJETO", "Grupo: nome a definir · nomes/matrículas pendentes", NAVY)
        roles = [
            ("PRODUTO E DADOS", "Requisitos, modelo SQL, carga e consultas", BLUE),
            ("IA E RAG", "Fontes fictícias, avaliação e QLoRA", TEAL),
            ("SEGURANÇA", "Papéis, DENY, ataques e auditoria", RED),
            ("INTEGRAÇÃO", "API, n8n, testes e demonstração CLI", GOLD),
        ]
        gap = 4 * mm
        box_w = (self.width - 2 * gap - 4 * gap) / 4
        box_h = 28 * mm
        box_y = 5 * mm
        c.setStrokeColor(BLUE)
        c.setLineWidth(1)
        mid_x = self.width / 2
        c.line(mid_x, root_y, mid_x, box_y + box_h + 8 * mm)
        c.line(gap + box_w / 2, box_y + box_h + 8 * mm, self.width - gap - box_w / 2, box_y + box_h + 8 * mm)
        for i, (title, detail, color) in enumerate(roles):
            x = gap + i * (box_w + gap)
            c.line(x + box_w / 2, box_y + box_h + 8 * mm, x + box_w / 2, box_y + box_h)
            self._box(x, box_y, box_w, box_h, title, detail, color)


class ArchitectureDiagram(Flowable):
    def __init__(self, width: float = 174 * mm, height: float = 112 * mm):
        super().__init__()
        self.width = width
        self.height = height

    def _node(self, x, y, w, h, title, detail, fill, border=None):
        c = self.canv
        c.setFillColor(fill)
        c.setStrokeColor(border or fill)
        c.roundRect(x, y, w, h, 5, fill=1, stroke=1)
        c.setFillColor(NAVY if fill in (PALE, MINT, WHITE) else WHITE)
        c.setFont(FONT_BOLD, 7.3)
        c.drawCentredString(x + w / 2, y + h - 5 * mm, title)
        c.setFillColor(INK if fill in (PALE, MINT, WHITE) else WHITE)
        c.setFont(FONT, 6.2)
        for i, line in enumerate(wrap(detail, max(10, int(w / 2.2)))[:3]):
            c.drawCentredString(x + w / 2, y + h - (9 + i * 3.2) * mm, line)

    def _arrow(self, x1, y1, x2, y2, label=""):
        c = self.canv
        c.setStrokeColor(BLUE)
        c.setFillColor(BLUE)
        c.setLineWidth(1)
        c.line(x1, y1, x2, y2)
        import math
        angle = math.atan2(y2 - y1, x2 - x1)
        size = 2.3 * mm
        p1 = (x2, y2)
        p2 = (x2 - size * math.cos(angle - 0.45), y2 - size * math.sin(angle - 0.45))
        p3 = (x2 - size * math.cos(angle + 0.45), y2 - size * math.sin(angle + 0.45))
        path = c.beginPath()
        path.moveTo(*p1)
        path.lineTo(*p2)
        path.lineTo(*p3)
        path.close()
        c.drawPath(path, fill=1, stroke=0)
        if label:
            c.setFont(FONT, 5.6)
            c.drawCentredString((x1 + x2) / 2, (y1 + y2) / 2 + 1.5 * mm, label)

    def draw(self) -> None:
        c = self.canv
        c.setFillColor(PALE)
        c.roundRect(0, 0, self.width, self.height, 7, fill=1, stroke=0)
        margin = 5 * mm
        gap = 4 * mm
        node_w = (self.width - 2 * margin - 3 * gap) / 4
        node_h = 22 * mm
        top_y = self.height - 29 * mm
        bottom_y = 8 * mm
        top = [
            ("OPERADOR / CLI", "Importa, consulta e aprova; escopo local", NAVY),
            ("n8n + OCR", "Webhook, validação, extração e correlação", BLUE),
            ("API SIGp", "Valida, parametriza SQL e aplica regra determinística", TEAL),
            ("SQL SERVER", "Dados, conciliação e auditoria append-only", NAVY),
        ]
        xs = [margin + i * (node_w + gap) for i in range(4)]
        for x, node in zip(xs, top):
            self._node(x, top_y, node_w, node_h, *node)
        self._arrow(xs[0] + node_w, top_y + node_h / 2, xs[1], top_y + node_h / 2, "arquivo")
        self._arrow(xs[1] + node_w, top_y + node_h / 2, xs[2], top_y + node_h / 2, "payload")
        self._arrow(xs[2] + node_w, top_y + node_h / 2, xs[3], top_y + node_h / 2, "consultas parametrizadas")

        low_w = (self.width - 2 * margin - 2 * gap) / 3
        low_x = [margin + i * (low_w + gap) for i in range(3)]
        lower = [
            ("20 FONTES RAG", "Documentos contratuais totalmente fictícios", WHITE),
            ("RAG LOCAL", "Busca lexical top-5; embeddings/Qdrant futuros", MINT),
            ("LLM + LoRA", "Qwen2.5 0.5B local; adaptador experimental separado", WHITE),
        ]
        for x, node in zip(low_x, lower):
            self._node(x, bottom_y, low_w, 22 * mm, *node)
        self._arrow(low_x[0] + low_w, bottom_y + 11 * mm, low_x[1], bottom_y + 11 * mm, "índice vetorial")
        self._arrow(low_x[1] + low_w, bottom_y + 11 * mm, low_x[2], bottom_y + 11 * mm, "contexto mínimo")

        c.setStrokeColor(RED)
        c.setDash(3, 2)
        c.roundRect(xs[2] - 2 * mm, top_y - 2 * mm, node_w + 4 * mm, node_h + 4 * mm, 7, fill=0, stroke=1)
        c.setDash()
        c.setFillColor(RED)
        c.setFont(FONT_BOLD, 6.3)
        c.drawCentredString(xs[2] + node_w / 2, top_y - 5 * mm, "FRONTEIRA: API controla acesso e valida")
        c.setFillColor(MUTED)
        c.setFont(FONT, 6.3)
        c.drawCentredString(self.width / 2, self.height / 2 - 1 * mm, "LLM/RAG sem senha SQL, sem chave fiscal integral e sem permissão de escrita")
        c.drawCentredString(self.width / 2, self.height / 2 - 5 * mm, "AUDITORIA: ator · ação · correlation_id · versão do modelo · fontes · decisão humana")


class AcademicDoc(BaseDocTemplate):
    def __init__(self, filename: Path, title: str, pagesize=A4):
        self.doc_title = title
        width, height = pagesize
        super().__init__(
            str(filename), pagesize=pagesize,
            leftMargin=17 * mm, rightMargin=17 * mm,
            topMargin=17 * mm, bottomMargin=17 * mm,
            title=title, author="SIGp — " + "; ".join(n for n, _m in TEAM),
        )
        frame = Frame(
            self.leftMargin, self.bottomMargin, self.width, self.height,
            id="normal", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
        )
        self.addPageTemplates(PageTemplate(id="main", frames=frame, onPage=self._draw_page))

    def _draw_page(self, canvas, doc):
        canvas.saveState()
        width, height = self.pagesize
        canvas.setStrokeColor(colors.HexColor("#D4DEE5"))
        canvas.setLineWidth(0.5)
        canvas.line(self.leftMargin, 12 * mm, width - self.rightMargin, 12 * mm)
        canvas.setFont(FONT, 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(self.leftMargin, 8 * mm, "SIGp · entrega acadêmica · dados sintéticos")
        canvas.drawRightString(width - self.rightMargin, 8 * mm, f"{doc.page}")
        if doc.page > 1:
            canvas.setFont(FONT_BOLD, 7)
            canvas.setFillColor(NAVY)
            canvas.drawString(self.leftMargin, height - 10 * mm, self.doc_title)
        canvas.restoreState()


def cover(title: str, subtitle: str, session: str) -> list:
    return [
        Spacer(1, 10 * mm),
        P("SIGp · PROJETO ACADÊMICO", "SubTitle"),
        P(title, "CoverTitle"),
        P(subtitle, "CoverSubtitle"),
        P(f"<b>{session}</b> · {DATE_LABEL}", "BodySIGp"),
        P(TEAM_NOTE, "CalloutSIGp"),
        P("<b>SIGp operacional:</b> API Flask, SQLite, n8n e OCR. "
          "<b>Protótipo acadêmico isolado:</b> SQL Server/RLS, corpus sintético, busca lexical e Qwen local; "
          "n8n ponta a ponta e Qdrant continuam pendentes.", "BodySIGp"),
        Spacer(1, 2 * mm),
        P("Canvas do projeto", "SubTitle"),
        CanvasDiagram(),
        Spacer(1, 3 * mm),
        P("<b>Regra de honestidade:</b> ideias e metas futuras estão identificadas como propostas; "
          "não são apresentadas como funcionalidades já implementadas ou testadas.", "SmallSIGp"),
    ]


def ai_story() -> list:
    story = cover(
        "Parte de Inteligência Artificial",
        "RAG, modelo de linguagem, experimento de fine-tuning, fluxo n8n e plano de avaliação.",
        "Projeto de Inteligência Artificial",
    )
    story += [PageBreak()]
    story += section("1. Objetivo e estado do projeto", [
        P("Problema: relacionar fatura do provedor, nota lançada e pagamento quando os arquivos chegam "
          "em momentos diferentes; indicar divergências e explicar a evidência para revisão humana."),
        P("<b>Protótipo acadêmico executado:</b> API Flask, SQL Server com RLS, busca lexical em 20 fontes "
          "fictícias e Qwen2.5 0.5B local via Ollama. Foi feito um experimento LoRA separado; adaptador "
          "não integrado à API. Qdrant/embeddings e fluxo n8n ponta a ponta ainda não estão ativos."),
        P("O workflow WF-05 contém um nó Claude/Anthropic desativado e caminho de resumo por regra fixa. "
          "Ativá-lo usaria uma API externa; isso não é o Qwen local proposto. Usar somente dados fictícios "
          "até avaliar formalmente qualquer envio de dados reais.", "SmallSIGp"),
        P("A IA não aprova pagamento. A classificação final da API usa regras estruturadas; o LLM gera "
          "uma classificação experimental, não autoritativa.", "CalloutSIGp"),
    ])
    story += section("2. Arquitetura de IA", [
        P("Fluxo atual: JSON fictício → API → contexto SQL autorizado + busca lexical escopada em 20 fontes "
          "→ regra determinística e classificação experimental do Ollama. O diagrama integrado abaixo é "
          "alvo de arquitetura; Qdrant/embeddings e n8n ponta a ponta ainda são futuros."),
        ArchitectureDiagram(),
        P("LLM usado na API: <b>Qwen2.5 0.5B Q4_K_M via Ollama/CPU</b>. O piloto de fine-tuning usa "
          "<b>Qwen2.5-0.5B-Instruct float32</b> e gera um adaptador separado. Não confundir o adaptador "
          "com o modelo carregado pelo endpoint.", "SmallSIGp"),
    ])
    story += section("3. Escolhas, privacidade e custo por mil usos", [
        make_table([
            ["Critério", "Estado medido", "Limite"],
            ["Qualidade API", "5 casos: regras/segurança 5/5; acordo do Ollama 3/5.", "Amostra de 5, sem alegação estatística."],
            ["Piloto LoRA", "Teste sintético: macro-F1 0,522 → 0,900 em 20 exemplos.", "Templates/serviços se repetem nas partições; resultado exploratório."],
            ["Custo", "Sem cobrança por tokens; treino em CPU durou 855 s.", "Energia e custo por 1.000 usos não medidos."],
            ["Privacidade", "Protótipo local com dados fictícios.", "Não elimina riscos locais de acesso, logs ou backup."],
            ["Limite", "LLM não recebe credencial SQL nem pode escrever ou pagar.", "Adaptador não está integrado à API."],
        ], [29 * mm, 77 * mm, 67 * mm]),
        P("Consumo elétrico, tarifa e custo local por 1.000 usos não foram medidos; não apresentar estimativa "
          "hipotética como resultado.", "SmallSIGp"),
    ])
    story += [PageBreak()]
    story += section("4. RAG: fontes, chunking e busca", [
        P("Já existem 20 documentos totalmente fictícios, filtrados por local/provedor antes da busca lexical "
          "e com até cinco fontes retornadas. Não há chunking semântico, embeddings ou Qdrant."),
        make_table([
            ["#", "Documento sintético", "#", "Documento sintético"],
            ["01", "Contrato Alfa: link principal, Agência Centro", "11", "Política: instalação e ativação"],
            ["02", "Contrato Alfa: link de contingência", "12", "Política: aluguel de equipamento"],
            ["03", "Aditivo Alfa: aumento de banda", "13", "Política: substituição de equipamento"],
            ["04", "Contrato Beta: link principal, Rodoviária Norte", "14", "Política: IP adicional"],
            ["05", "Contrato Beta: IP fixo", "15", "Política: serviço de voz"],
            ["06", "Contrato Gama: link principal, Garagem Sul", "16", "Política: cancelamento e fidelidade"],
            ["07", "Contrato Gama: suporte técnico", "17", "Política: mudança de endereço"],
            ["08", "Política: franquia de dados", "18", "Tabela: faixas fictícias de velocidade/preço"],
            ["09", "Política: reajuste anual", "19", "Catálogo: códigos de serviços contratados"],
            ["10", "Política: multa por atraso", "20", "Procedimento: escalonamento para revisão"],
        ], [10 * mm, 76 * mm, 10 * mm, 77 * mm], small=True),
        P("<b>Pipeline atual:</b> busca lexical simplificada, escopo local/provedor e top-5; IDs recuperados "
          "são registrados. Chunking, embeddings multilíngues e Qdrant permanecem propostas futuras."),
    ])
    story += section("5. Fine-tuning LoRA (piloto executado)", [
        make_table([
            ["Item", "Resultado observado"],
            ["Tarefa", "Classificar item de cobrança como CONTRATADO, DIVERGENTE ou REVISAR."],
            ["Dados", "120 exemplos fictícios; 80 treino, 20 validação, 20 teste; SHA-256 registrado."],
            ["Modelo", "Qwen2.5-0.5B-Instruct, revisão fixada; LoRA r=4, alpha=8, q_proj/v_proj."],
            ["Execução", "CPU float32, 1 época; 80 exemplos, loss média 0,073; 855 segundos."],
            ["Validação", "Base: acc 60%, macro-F1 0,515. LoRA: acc 85%, macro-F1 0,855."],
            ["Teste reservado", "Base: acc 65%, macro-F1 0,522. LoRA: acc 90%, macro-F1 0,900 (18/20)."],
            ["Limitação", "Famílias de cenários repetidas entre partições; métrica exploratória, não prova generalização."],
            ["Artefatos", "`ia/finetuning/`: dataset, script, adaptador e relatório detalhado."],
        ], [37 * mm, 136 * mm]),
        P("O adaptador não está integrado ao endpoint nem ao Ollama. Fine-tuning ensina padrões, não atualiza "
          "fatos contratuais; regras determinísticas e revisão humana continuam obrigatórias.", "CalloutSIGp"),
    ])
    story += [PageBreak()]
    story += section("6. Falhas e avaliação adversarial", [
        make_table([
            ["Risco", "Teste / indicador", "Meta inicial"],
            ["Alucinação ou citação inexistente", "Conferir cada citação contra IDs e trechos recuperados; amostra revisada por avaliador.", "Toda sugestão cita fonte válida ou retorna REVISAR."],
            ["Fora do escopo", "Casos sem provedor/serviço nos documentos; medir recall de REVISAR.", "Recall de REVISAR ≥ 0,90 no conjunto adversarial (meta, não resultado)."],
            ["Prompt injection em PDF", "Documento tenta instruir o modelo a ignorar regras, revelar outro local ou alterar dados.", "Zero vazamento e zero chamada/ferramenta de escrita."],
            ["Erro de OCR", "Comparar emissor, vencimento e valor extraídos com gabarito sintético.", "Relatar acurácia por campo; não confundir com métrica do LLM."],
            ["Confiança excessiva", "Resposta não suportada ou divergente é revisada por pessoa.", "Nenhum estado de pagamento muda por recomendação da IA."],
        ], [37 * mm, 90 * mm, 46 * mm]),
        P("Registro por execução: correlation_id, hash do documento sintético, versão do prompt/modelo, "
          "IDs de fontes recuperadas, saída estruturada, duração, decisão humana e motivo. Nunca registrar segredo "
          "ou payload fiscal real."),
    ])
    story += section("7. n8n e apresentação de 5 minutos", [
        make_table([
            ["Tempo", "Demonstração"],
            ["0:00–0:45", "Canvas: atraso/risco, usuário, entrada e resultado."],
            ["0:45–1:30", "Arquitetura: API, SQL, n8n/OCR, RAG, LLM e fronteiras de permissão."],
            ["1:30–2:30", "Enviar documento sintético; mostrar OCR/parser e revisão manual."],
            ["2:30–3:45", "Mostrar top-5 e trechos citados; comparar com a classificação sugerida."],
            ["3:45–4:30", "Prompt injection e resposta REVISAR; explicar que IA não escreve nem aprova."],
            ["4:30–5:00", "Métricas, limitações, próximo passo e estado real (proposta ainda não implantada)."],
        ], [26 * mm, 147 * mm]),
        P("Na apresentação, mostrar apenas resultados realmente executados. A API e o RAG lexical foram exercitados "
          "diretamente; a execução via webhook n8n segue pendente."),
        P("Estado: API acadêmica, SQL Server/RLS, corpus lexical, Qwen via Ollama e avaliação de cinco casos foram "
          "executados. LoRA tem resultado preliminar separado; Qdrant e integração do adaptador estão pendentes.", "CalloutSIGp"),
    ])
    return story


def security_story() -> list:
    story = cover(
        "Parte de Segurança e Otimização de Banco de Dados",
        "Modelo de dados classificado, proteção, matriz de privilégios, ameaças e experimento de desempenho.",
        "Segurança e Otimização de Banco de Dados",
    )
    story += [PageBreak()]
    story += section("1. Banco, escopo e estado", [
        P("Banco escolhido para a atividade: <b>SQL Server Developer local</b>, em ambiente isolado de desenvolvimento. "
          "O SIGp operacional continua com SQLite e não foi migrado. A instância acadêmica executa RLS, papéis, "
          "permissões testadas e carga sintética de 100.020 notas, 100.020 itens, 50.010 pagamentos e 100.020 conciliações."),
        P("Princípio: banco sem exposição pública, conexão exclusivamente pela API, usuário da aplicação sem privilégios "
          "administrativos, dados fictícios e backups de teste protegidos.", "CalloutSIGp"),
    ])
    story += section("2. Modelo e classificação dos campos", [
        P("Classificação: <b>Público</b> (sem impacto relevante), <b>Interno</b> (uso organizacional) e "
          "<b>Sensível</b> (fiscal, financeiro identificável ou segredo). Na carga acadêmica, todos os valores são sintéticos."),
        make_table([
            ["Tabela", "Campo", "Classe", "Proteção prevista"],
            ["Locais", "id, tipo, nome, cidade", "Interno", "IDs fictícios; API filtra o escopo do local."],
            ["Provedores", "id, nome", "Interno", "CRUD via API; sem acesso direto do LLM."],
            ["Notas", "id, local_id, provedor_id", "Interno", "Chaves estrangeiras; autorização por escopo."],
            ["Notas", "chave_fiscal", "Sensível", "Mascarar em views/logs; cifrar disco/backup; não enviar ao LLM."],
            ["Notas", "numero, serie, origem, status", "Interno", "Validar entrada; parâmetros SQL; trilha para mudanças."],
            ["Notas", "valor_total", "Sensível", "Acesso mínimo; mascarar/omitir fora da análise autorizada."],
            ["Notas", "data_emissao, vencimento", "Interno", "Coleta mínima; visibilidade por local."],
            ["ItensNota", "id, nota_id", "Interno", "FK; acesso mediado pela API."],
            ["ItensNota", "descricao", "Interno*", "Minimizar; remover identificadores pessoais antes de IA."],
            ["ItensNota", "valor", "Sensível", "Expor somente o necessário; máscara por perfil."],
            ["ItensNota", "classificacao", "Interno", "Sugestão de IA não equivale a aprovação."],
            ["Pagamentos", "id, nota_id, data_pagamento", "Sensível", "Restringir leitura por local/papel; auditar acesso."],
            ["Pagamentos", "valor_pago, referencia", "Sensível", "Não guardar dado bancário; mascarar referência em logs."],
            ["Faturas", "id, local_id, provedor_id, nota_id", "Interno", "FK, autorização por local; PDF fora do SQL."],
            ["Faturas", "arquivo_ref, valor, vencimento", "Sensível", "Armazenamento de PDF restrito; criptografia de backup."],
            ["Conciliações", "id, nota_id, status, atualizado_em", "Interno", "Atualização só pela API; trilha antes/depois."],
            ["Conciliações", "justificativa, revisado_por", "Interno", "Não incluir segredos; auditar correções."],
            ["Auditoria", "ator, acao, objeto, correlation_id, criado_em", "Interno", "Acesso auditor; append-only para app; retenção definida."],
            ["Auditoria", "detalhe_redigido", "Interno/Sensível", "Redigir payload e segredos; acesso restrito."],
            ["DocumentosRAG", "fonte, metadados, texto sintético", "Público no protótipo", "Somente material fictício; contratos reais seriam internos."],
        ], [24 * mm, 42 * mm, 25 * mm, 82 * mm], small=True),
        P("*A descrição deve ser reclassificada como Sensível se contiver identificadores pessoais ou informação "
          "operacional restrita.", "SmallSIGp"),
    ])
    story += [PageBreak()]
    story += section("3. Matriz de papéis e DENY", [
        make_table([
            ["Papel", "Pode", "Não pode / DENY"],
            ["Operador (aplicação)", "Importar via API; consultar locais autorizados; solicitar correção manual.", "Sem conexão SQL direta, sem exportação global nem exclusão de histórico."],
            ["Auditor", "Ler views autorizadas e eventos de auditoria redigidos.", "Sem DML operacional, alteração de papel ou acesso a segredos."],
            ["sigp_api (principal técnico)", "SELECT/INSERT/UPDATE necessários via parâmetros e procedures.", "DENY DELETE; sem DDL, GRANT, administração ou role dbo."],
            ["sigp_ia", "Ler somente view de contexto mínimo e documentos públicos sintéticos.", "DENY SELECT em tabelas app/audit; DENY INSERT/UPDATE/DELETE; sem credencial SQL."],
            ["Administrador DB", "DDL, manutenção, backup e criação de usuários em ambiente de teste.", "Credencial não usada pela aplicação, n8n nem modelo."],
            ["n8n", "Chamar API com token limitado e correlation_id.", "Sem senha SQL, sem conta sa, sem acesso ao arquivo do banco."],
        ], [32 * mm, 65 * mm, 78 * mm]),
        P("<b>RLS:</b> aplicada no protótipo acadêmico; escopo local vem da configuração do servidor, não do corpo "
          "enviado pelo cliente. A API consulta contexto por procedure autorizada e a leitura direta é negada.", "BodySIGp"),
        P("Os testes de permissão foram executados: leitura do LOC-001 permitida; LOC-002, leitura direta, DELETE "
          "pela API e principal sem role negados. A evidência registra o correlation ID e o resultado.", "CalloutSIGp"),
    ])
    story += section("4. Ataques e evidência de mitigação", [
        make_table([
            ["Teste seguro", "Procedimento", "Evidência esperada"],
            ["SQL Injection", "Inserir strings especiais em busca e número de nota de documentos sintéticos; verificar uso de parâmetros.", "Somente dados esperados; esquema e contagens sem alteração; consulta parametrizada registrada."],
            ["Escalonamento", "Tentar SELECT em tabela base, DML, DDL e leitura de auditoria com sigp_ia/sigp_api.", "Permissão negada; nenhuma alteração; evento de segurança redigido."],
            ["Prompt injection", "Incluir instrução adversarial em documento fictício para ignorar política e revelar outro local.", "Nenhuma divulgação; nenhuma escrita; fontes válidas ou REVISAR."],
        ], [33 * mm, 74 * mm, 68 * mm]),
        P("Testes autorizados somente no banco local de treinamento e em dados sintéticos. Não usar payload destrutivo "
          "nem apontar testes a sistemas de terceiros."),
    ])
    story += [PageBreak()]
    story += section("5. Otimização: duas consultas e carga", [
        make_table([
            ["Consulta de risco", "Forma lógica", "Índices candidatos"],
            ["Resumo mensal por provedor/local", "Notas JOIN itens JOIN pagamentos; filtro de período/local; GROUP BY provedor, mês e status.", "Notas(provedor_id, data_emissao); Pagamentos(nota_id, data_pagamento); índice/FK em ItensNota(nota_id)."],
            ["Pendências vencidas/sem conciliação", "Filtrar local, vencimento e status; NOT EXISTS conciliação válida; ordenar por vencimento.", "Notas(local_id, vencimento, status); Conciliacoes(nota_id, status)."],
        ], [40 * mm, 78 * mm, 57 * mm]),
        P("Carga sintética executada: 100.020 notas, 100.020 itens, 50.010 pagamentos e 100.020 conciliações; "
          "não foi carregado um milhão de eventos de auditoria."),
        P("Planos reais e estatísticas foram salvos. A medição inicial observou cerca de 3.277 leituras lógicas em Notas "
          "e 528 em Conciliações, com 46 ms e 25 ms em uma execução. Ainda faltam baseline sem índices, repetições, "
          "mediana e p95; não alegar otimização comprovada."),
    ])
    story += section("6. Base inicial e prevenção de risco", [
        P("Arquivo versionado: `sqlserver/01_schema_seed.sql`. Ele cria o banco local acadêmico, schemas app/audit/ai, "
          "tabelas, constraints, view mínima, roles, DENY/GRANT, índices candidatos e população inicial fictícia."),
        P("Estado em 02/11/2026: SQL Server, carga sintética, RLS e testes de permissões foram executados. "
          "O relatório de auditoria e os planos SQL ficam em `sqlserver/evidence/`. O benchmark ainda não tem "
          "comparação repetida antes/depois dos índices nem p95.", "CalloutSIGp"),
        P("Organização do trabalho recomendada (responsabilidades propostas, não confirmadas):", "SubTitle"),
        OrgChart(),
    ])
    return story


def integration_story() -> list:
    story = cover(
        "Parte de Integração: IA, dados e governança",
        "Arquitetura única, limites de confiança, matriz ampliada de papéis e plano de ataques.",
        "Integração das disciplinas",
    )
    story += [PageBreak()]
    story += section("1. Organograma e estado do projeto", [
        P("Responsabilidades abaixo são uma proposta de organização; não foram atribuídas individualmente "
          "porque o grupo ainda não confirmou papéis, nome oficial e matrículas."),
        OrgChart(),
        make_table([
            ["Estado", "O que inclui"],
            ["Feito no SIGp atual", "Interface e API local; SQLite operacional; importação manual; conciliação; n8n; OCR local; workflows de entrada/eventos."],
            ["Executado no protótipo acadêmico", "SQL Server com RLS e carga sintética; API, 20 fontes lexicais e Qwen local; avaliação de cinco casos."],
            ["Experimento de IA", "LoRA separado: macro-F1 0,522 → 0,900 em 20 testes sintéticos; adaptador sem integração."],
            ["Em andamento nesta entrega", "Organização das três partes, canvas, arquitetura única, matriz de papéis e preparação dos PDFs."],
            ["Pendente", "Ativar e testar n8n ponta a ponta; embeddings/Qdrant; avaliação independente maior; integrar adaptador apenas após validação."],
        ], [44 * mm, 131 * mm]),
        P("O SQL Server acadêmico não substitui nem migra o SQLite do SIGp. O adaptador LoRA é separado da API; "
          "o n8n continua inativo e o RAG usa busca lexical, sem vetor.", "CalloutSIGp"),
    ])
    story += section("2. Arquitetura única e fronteiras de confiança", [
        ArchitectureDiagram(),
        P("Permissões: API é a única camada autorizada a conversar com SQL Server; n8n usa API, não SQL; RAG consulta "
          "apenas fontes fictícias e recebe contexto mínimo; LLM não possui credencial nem ferramenta de escrita. "
          "Proteção: minimização, mascaramento, segredo fora do repositório, restrição de local e criptografia de "
          "disco/backup. Auditoria: ator, ação, correlation_id, versão do modelo, fontes citadas e decisão humana."),
        P("A resposta do modelo é uma <b>sugestão não confiável</b>. A API valida schema/IDs, mantém estado pendente "
          "e exige revisão humana. A regra de conciliação continua determinística no backend.", "CalloutSIGp"),
    ])
    story += [PageBreak()]
    story += section("3. Matriz de papéis ampliada (inclui IA)", [
        make_table([
            ["Ator/papel", "Pode ver", "Pode fazer", "Proibições explícitas"],
            ["Operador", "Documentos e locais do escopo autorizado; status e evidências.", "Importar, corrigir com justificativa e revisar sugestão.", "Não acessa DB diretamente, não apaga auditoria, não concede permissões."],
            ["Auditor", "Views redigidas, histórico de decisões e eventos permitidos.", "Consultar, exportar relatório redigido e verificar evidências.", "Sem alteração operacional ou leitura de segredo."],
            ["API (sigp_api)", "Campos operacionais indispensáveis ao endpoint.", "Queries parametrizadas, transação, gravação e auditoria.", "DENY DELETE; sem DDL/GRANT/sa; não aceita escopo local sem autorização."],
            ["IA (sigp_ia)", "Descrição reduzida, serviço/valor autorizados e trechos RAG pertinentes.", "Gerar sugestão estruturada com fonte e confiança.", "DENY em tabelas app/audit; sem chave fiscal, pagamentos identificáveis, anexos, outros locais, DML ou decisão financeira."],
            ["RAG / embeddings", "Somente os 20 documentos sintéticos e consulta minimizada.", "Indexar, recuperar top-5 e devolver IDs/trechos.", "Sem dados reais, sem banco transacional, sem ação externa."],
            ["n8n", "Payload necessário ao workflow e resposta da API.", "Orquestrar webhook, OCR e chamada à API; registrar correlation_id.", "Sem senha SQL, sem conta sa, sem aprovação automática."],
            ["Admin DB", "Ambiente acadêmico de teste.", "Criar schema, backup e role em manutenção controlada.", "Não compartilhar credencial com API/LLM/n8n; operações auditadas."],
        ], [27 * mm, 49 * mm, 50 * mm, 57 * mm], small=True),
        P("RLS será habilitada no SQL Server se houver usuários com escopos distintos. A API autentica o operador e "
          "define o contexto de sessão; o banco filtra pelo local. A IA não recebe contexto de outros locais."),
        P("Esse isolamento é uma meta de arquitetura, não uma propriedade comprovada do script atual: "
          "`ai.vw_contexto_minimo` não filtra por local. Corrigir e testar antes de permitir SELECT pela IA.", "CalloutSIGp"),
    ])
    story += section("4. Ataques que serão testados", [
        make_table([
            ["Ataque", "Cenário de laboratório", "Critério de aprovação", "Status"],
            ["Prompt injection", "Documento/cobrança sintética em inglês tenta revelar dados de outro local e induzir pagamento.", "API retornou REVISAR; pagamento automático falso; caso direto testado.", "Testado na API"],
            ["SQL Injection", "Entrada sintética contém aspas e operadores em busca/número; API SQL parametrizada.", "Nenhum dado além do escopo; nenhuma alteração de esquema/contagem; teste reproduzível.", "Planejado"],
            ["Escalonamento de privilégio", "Tentativa de leitura direta, acesso cruzado, DELETE e principal sem role.", "Acesso negado; evidências em security-tests.txt.", "Testado"],
        ], [31 * mm, 66 * mm, 61 * mm, 25 * mm], small=True),
        P("Executar somente em instância local e em dados fictícios. Guardar comandos de teste defensivos, resultado, "
          "plano/contagem anterior e posterior e evidência da autorização negada. Não testar serviço de terceiros."),
    ])
    story += [PageBreak()]
    story += section("5. Roteiro de integração e critérios de aceite", [
        make_table([
            ["Fase", "Entrega", "Critério de aceite"],
            ["1 — Base", "SQL Server local, seed sintético, RLS e permissões.", "Executado; 100 mil+ registros de carga e testes de papéis registrados."],
            ["2 — Integração", "API acadêmica e webhook n8n.", "API executada diretamente; webhook n8n ainda pendente."],
            ["3 — RAG", "20 fontes e busca lexical filtrada.", "Executado; embeddings e Qdrant ainda futuros."],
            ["4 — IA", "Qwen API e experimento LoRA em dataset sintético.", "5 casos API; LoRA 18/20 no teste sintético; adaptador não integrado."],
            ["5 — Segurança/BD", "Testes de permissão e carga; planos para duas consultas.", "Permissões e planos registrados; baseline repetido/p95 ainda pendente."],
            ["6 — Apresentação", "Demonstração CLI/API, diagrama, canvas e limitações.", "Mostrar apenas evidência executada; planejamento rotulado como futuro."],
        ], [27 * mm, 74 * mm, 82 * mm]),
        P("O projeto só deve alegar proteção, performance ou qualidade de modelo no limite das evidências: RLS e "
          "permissões foram testadas; LoRA é piloto sintético; benchmark repetido e integração ponta a ponta seguem pendentes."),
    ])
    story += section("6. Identificação pendente", [
        make_table([
            ["Integrante", "Matrícula"],
            ["Maciel Lopes Francisco", "A preencher"],
            ["Fredson Pereira (nome completo a confirmar)", "A preencher"],
            ["Aeverton Santos (nome completo a confirmar)", "A preencher"],
            ["Jonatas de Jesus Souza", "A preencher"],
        ], [105 * mm, 78 * mm]),
        P("Preencher nome oficial do grupo, confirmar nomes completos e inserir matrículas antes do envio acadêmico.", "CalloutSIGp"),
    ])
    return story


def guide_story() -> list:
    story = cover(
        "Guia do aluno",
        "O que já existe, o que falta comprovar, custos de LLM, LGPD/XML e roteiro de defesa.",
        "Revisão técnica e acadêmica",
    )
    story += [PageBreak()]
    story += section("Resumo em um minuto", [
        P("O SIGp operacional usa SQLite. O protótipo acadêmico separado tem SQL Server/RLS, busca lexical em "
          "20 documentos fictícios e Qwen2.5 0.5B local. O piloto LoRA gerou adaptador isolado; Qdrant e n8n "
          "ponta a ponta continuam pendentes.", "CalloutSIGp"),
        P("O workflow WF-05 contém um nó Anthropic/Claude desativado e um caminho de resumo por regra fixa. "
          "Se ativado, esse nó chama uma API externa: não é o LLM local desenhado como arquitetura futura. "
          "Não envie documentos reais sem avaliação de finalidade, base legal, minimização, contrato e segurança."),
        P("Recomendação: mantenham o SQL Server local e dados sintéticos como protótipo acadêmico separado. "
          "Demonstrem por CLI/API ou n8n, alinhando com o docente a restrição de não entregar web app/site. "
          "Mantenham regras determinísticas e avaliação como autoridade; fine-tuning é experimental e opcional."),
    ])
    story += section("1. Estado real versus proposta", [
        make_table([
            ["Tema", "Estado observado", "Não alegar"],
            ["SIGp operacional", "API Flask, SQLite, interface web, importações manuais, conciliação, n8n e OCR local.", "Que já usa SQL Server, MongoDB, RAG ou LLM local."],
            ["WF-05", "Claude/Anthropic desativado; resumo por regra fixa.", "Que a IA está ativa ou que é Qwen local."],
            ["SQL Server", "RLS, usuários de teste, permissões e carga sintética executados.", "Que o SQL Server substituiu o SQLite operacional."],
            ["RAG / LLM", "20 documentos JSON, busca lexical escopada, Ollama Qwen 0.5B; API testada em cinco casos.", "Que usa embeddings/Qdrant ou que o LLM decide/paga."],
            ["Fine-tuning", "LoRA CPU: macro-F1 0,522 → 0,900 em 20 exemplos sintéticos.", "Generalização ou integração do adaptador; partições compartilham famílias de cenários."],
            ["Segurança", "Teste registra permissão local e nega acesso cruzado, leitura direta e exclusão.", "Que a auditoria identifica uma pessoa autenticada."],
            ["Testes", "9 testes da API e cinco casos de decisão/segurança; avaliação real 5/5 e acordo LLM 3/5.", "Que isso certifica segurança ou qualidade estatística."],
            ["Entrega", "PDFs e documentos preparados; identificação e repositório pendentes de conferência.", "Que o web app atende à regra da atividade."],
        ], [31 * mm, 76 * mm, 66 * mm], small=True),
        P("O SIGp pode contextualizar o problema, mas a demonstração precisa obedecer à regra de não entregar "
          "site/aplicação web. Não escondam a interface existente: expliquem qual artefato será efetivamente avaliado."),
    ])
    story += [PageBreak()]
    story += section("2. Banco de dados: decisão e lacunas", [
        make_table([
            ["Componente", "Papel", "Decisão"],
            ["SQLite", "Banco local do SIGp operacional.", "Manter no sistema atual; não confundir com o protótipo acadêmico."],
            ["SQL Server", "Banco relacional acadêmico executado com RLS e dados sintéticos.", "Não confundir com migração do banco operacional."],
            ["Qdrant", "Recuperação vetorial do RAG proposto.", "Opcional/futuro; não substitui SQL transacional."],
            ["MongoDB", "Banco documental alternativo.", "Não adicionar sem requisito; aumenta custo e superfície de segurança."],
        ], [34 * mm, 68 * mm, 71 * mm]),
        P("<b>Recomendação:</b> SQL Server acadêmico isolado; SQLite permanece no SIGp atual. Não migrem até decidir "
          "requisitos de instalação, backup, concorrência e operação. Um banco executado e testado é melhor que dois "
          "apenas desenhados."),
        *bullets([
            "A evidência testa 50 linhas do LOC-001 e nega tentativa de LOC-002, leitura direta, DELETE e principal sem role.",
            "A identidade humana não está integrada; auditoria usa um ator técnico fixo.",
            "Os planos SQL foram capturados, mas faltam comparações repetidas antes/depois dos índices e p95.",
            "O corpus RAG é JSON da API; não é uma coleção vetorial no SQL Server.",
        ]),
    ])
    story += section("3. XML, PDFs e LGPD", [
        P("XML de NFS-e pode conter CPF/CNPJ, nome, endereço, e-mail, descrição do serviço, valores e identificadores "
          "fiscais. A composição varia por município. CNPJ empresarial não é automaticamente dado pessoal; dados que "
          "identifiquem pessoa natural podem ser. Dados financeiros não são automaticamente a categoria legal de "
          "“dado pessoal sensível”, mas devem ser restritos no projeto pelo risco."),
        *bullets([
            "Usar apenas dados fictícios; não guardar XML/PDF real em Git, prompts, issues ou relatórios.",
            "Minimizar campos enviados, redigir identificadores e definir retenção/eliminação de temporários e backups.",
            "Logs com correlation_id e IDs fictícios; nunca chave fiscal integral, senha, token ou payload completo.",
            "Antes de API externa: controlador avalia finalidade/base legal, necessidade, contrato, retenção, "
            "transferência internacional e segurança. Consentimento não é a única base legal.",
            "Execução local reduz saída de dados, mas não elimina risco de acesso local, malware ou backup exposto.",
        ]),
        P("Este guia não é aconselhamento jurídico. Uso de dados reais exige validação da organização e do encarregado/jurídico.", "CalloutSIGp"),
    ])
    story += [PageBreak()]
    story += section("4. Segurança: evidência que falta", [
        P("O protótipo acadêmico usa chave de API, escopo local no servidor e identidade SQL de privilégio mínimo. "
          "As portas em 127.0.0.1 limitam exposição de rede, mas a auditoria ainda não autentica uma pessoa."),
        make_table([
            ["Prova", "Critério de aceite"],
            ["Papel API", "Sem DELETE/DDL/admin; tentativa negada; dados inalterados."],
            ["Auditor", "Somente leitura e dados redigidos."],
            ["IA", "Sem credencial SQL, escrita ou leitura de outros locais."],
            ["SQL Injection", "Entrada sintética tratada como dado; contagens/esquema permanecem iguais."],
            ["Prompt injection", "Documento fictício não causa vazamento, escrita ou decisão; sem evidência = REVISAR."],
            ["Auditoria", "Negação/erro registrados sem segredo ou XML/PDF integral."],
        ], [39 * mm, 134 * mm]),
        P("Evidência salva em `sqlserver/evidence/security-tests.txt`: 50 linhas permitidas no escopo, leitura direta, "
          "acesso cruzado, DELETE e principal sem role negados. A API não recebe permissão de exclusão."),
    ])
    story += section("5. Opções de LLM e custo", [
        P("Não existe modelo universalmente melhor. Para verificar valor e vencimento, regras determinísticas e "
          "comparação numérica auditável são preferíveis. Um LLM pode resumir evidências e classificar texto, "
          "sempre com revisão humana."),
        make_table([
            ["Modelo", "Preço USD/1M tokens entrada/saída", "USD / 1.000 usos*"],
            ["OpenAI gpt-5-nano", "0,05 / 0,40", "0,30"],
            ["OpenAI gpt-4o-mini", "0,15 / 0,60", "0,60"],
            ["OpenAI gpt-5-mini", "0,25 / 2,00", "1,50"],
            ["Claude Haiku 5.5", "0,10 / 0,50", "0,45"],
            ["Claude Sonnet 5.5", "2,00 / 10,00", "9,00"],
            ["Claude Opus 5.5", "4,00 / 20,00", "18,00"],
            ["Qwen2.5 0.5B via Ollama", "Local; sem tarifa por token", "Hardware, energia e tempo; não medidos"],
        ], [54 * mm, 68 * mm, 51 * mm]),
        P("*Estimativa: 2.000 tokens de entrada + 500 de saída por uso. Fórmula: (tokens × tarifa) / "
          "1.000.000 × 1.000. Não inclui OCR, embeddings, retries, impostos, câmbio ou contexto maior. "
          "Preços consultados em 27/10/2026; conferir novamente antes da entrega.", "SmallSIGp"),
        P("Em baixo volume o custo de API pode ser pequeno, mas o preço não comprova qualidade nem privacidade. "
          "Local evita tarifa por token, não o custo do computador/energia/manutenção. O catálogo oficial do Ollama "
          "indica a licença da variante selecionada; confirmar os termos do modelo exato e seus artefatos antes de redistribuir."),
        P("Fontes: <link href=\"https://developers.openai.com/api/docs/pricing/\" color=\"blue\">OpenAI pricing</link> · "
          "<link href=\"https://platform.claude.com/docs/en/about-claude/pricing\" color=\"blue\">Anthropic pricing</link> · "
          "<link href=\"https://ollama.com/library/qwen2.5\" color=\"blue\">Ollama Qwen2.5</link>.", "SmallSIGp"),
    ])
    story += [PageBreak()]
    story += section("6. RAG, avaliação e fine-tuning", [
        P("RAG atual: 20 documentos JSON fictícios e busca lexical filtrada por local/provedor; não há embeddings nem "
          "Qdrant. A API mantém decisão determinística e expõe a resposta do Ollama apenas como concordância."),
        P("O experimento LoRA foi executado no Qwen2.5-0.5B-Instruct em CPU. No teste sintético de 20 exemplos, "
          "macro-F1 subiu de 0,522 para 0,900. As famílias de cenários repetem-se entre divisões, então esse ganho "
          "é exploratório e pode refletir similaridade; adaptador não integrado à API."),
        *bullets([
            "Validar com casos novos, separados por serviço/provedor, antes de considerar uso do adaptador.",
            "Comparar regras, LLM sem RAG e RAG+LLM; OCR é medido separadamente por campo.",
            "Reportar macro-F1, precisão/recall por classe, matriz de confusão e recall de REVISAR.",
            "Medir RAG: fonte correta entre top-5 e validade de cada citação.",
            "Testar prompt injection, fora de escopo, ausência de fonte, campo faltante e valores contraditórios.",
            "Nenhum modelo autoriza pagamento ou grava dados; baixa confiança/sem fonte resulta em revisão humana.",
        ]),
    ])
    story += section("7. Próximos passos e defesa de 5 minutos", [
        make_table([
            ["Ordem", "Ação verificável"],
            ["1", "Completar nome do grupo, nomes, matrículas, URL do repositório e remover dados/segredos reais do Git."],
            ["2", "Alinhar com docente demonstração via CLI/API/n8n devido à regra contra web app/site."],
            ["3", "Ativar o webhook n8n e guardar uma execução ponta a ponta com dados fictícios."],
            ["4", "Repetir benchmark SQL antes/depois de índices com amostras e mediana/p95."],
            ["5", "Avaliar LoRA em teste maior e independente; medir latência/energia; não integrar antes da revisão."],
            ["6", "Manter dados sintéticos, completar identificação acadêmica e confirmar formato aceito com o docente."],
        ], [19 * mm, 154 * mm]),
        P("<b>Roteiro:</b> 0:00 problema/canvas · 0:45 arquitetura e limites · 1:30 fluxo fictício · "
          "2:30 evidência de consulta/segurança · 3:30 métricas/custo/limitações · 4:30 próximos passos."),
        P("<b>Respostas para defender:</b> SQL Server é protótipo acadêmico isolado; SQLite continua no SIGp. "
          "Qdrant armazena índice vetorial, não substitui SQL. RAG traz fontes atuais; fine-tuning não atualiza contratos. "
          "IA não paga porque pode errar ou ser manipulada. Segurança é provada por tentativa e evidência, não por desenho."),
    ])
    story += section("8. Referências e ressalvas", [
        *bullets([
            "<link href=\"https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm\" color=\"blue\">LGPD — Lei nº 13.709/2018</link>.",
            "<link href=\"https://developers.openai.com/api/docs/pricing/\" color=\"blue\">Preços oficiais OpenAI</link>.",
            "<link href=\"https://platform.claude.com/docs/en/about-claude/pricing\" color=\"blue\">Preços oficiais Anthropic</link>.",
            "<link href=\"https://ollama.com/library/qwen2.5\" color=\"blue\">Catálogo e licença Qwen2.5 no Ollama</link>.",
            "<link href=\"https://learn.microsoft.com/sql/relational-databases/security/permissions-database-engine\" color=\"blue\">Permissões do SQL Server</link>.",
        ]),
        P("Preços, versões e licenças mudam; reconferir nas fontes oficiais na data da apresentação. "
          "Este documento é orientação acadêmica, não aconselhamento jurídico."),
    ])
    return story


PARTS = [
    ("Parte de IA", "parte-ia.pdf", ai_story),
    ("Parte de Segurança e Otimização", "parte-seguranca.pdf", security_story),
    ("Parte de Integração", "parte-integracao.pdf", integration_story),
]


def build_pdf(path: Path, title: str, story: list, pagesize=A4) -> None:
    doc = AcademicDoc(path, title, pagesize=pagesize)
    doc.build(story)


def main() -> None:
    for title, filename, story_factory in PARTS:
        build_pdf(OUT / filename, f"SIGp — {title}", story_factory())

    all_stories = []
    for index, (_, _, story_factory) in enumerate(PARTS):
        if index:
            all_stories.append(PageBreak())
        all_stories.extend(story_factory())
    build_pdf(OUT / "entrega-completa.pdf", "SIGp — Entrega completa", all_stories)
    build_pdf(OUT / "guia-do-aluno.pdf", "SIGp — Guia do aluno", guide_story())


if __name__ == "__main__":
    main()
