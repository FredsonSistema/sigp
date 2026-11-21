"""Gera os PDFs da entrega final a partir das evidências (mesmos dados da página apresentacao.html, via dados.py):

  docs/entrega-academica/relatorio-limitacoes.pdf   relatório de limitações (1 a 2 páginas; o script confere)
  docs/entrega-academica/relatorio-apresentacao.pdf relatório que acompanha a apresentação de 10 minutos

Uso, na raiz:  .venv-1\\Scripts\\python.exe docs/entrega-academica/apresentacao/gerar_relatorios.py
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DIR))
import dados  # noqa: E402

ENTREGA = DIR.parent
# Estado da fase de separação do repositório e do pacote de instalação (atualizar ao concluir e gerar de novo).
SEPARACAO_CONCLUIDA = False

NAVY, TEAL, INK, MUTED, PALE, MINT, RED, GOLD = (colors.HexColor(c) for c in
                                                 ("#15324B", "#178F8A", "#243746", "#5E7180", "#EAF2F7", "#E6F4F1", "#A83B3B", "#D69A2D"))
for nome, arq in (("SIGpSans", "arial.ttf"), ("SIGpSans-Bold", "arialbd.ttf")):
    caminho = Path(r"C:\Windows\Fonts") / arq
    if caminho.exists():
        pdfmetrics.registerFont(TTFont(nome, str(caminho)))
FONTE = "SIGpSans" if "SIGpSans" in pdfmetrics.getRegisteredFontNames() else "Helvetica"
NEGRITO = "SIGpSans-Bold" if "SIGpSans-Bold" in pdfmetrics.getRegisteredFontNames() else "Helvetica-Bold"
if FONTE == "SIGpSans":
    pdfmetrics.registerFontFamily("SIGpSans", normal="SIGpSans", bold="SIGpSans-Bold", italic="SIGpSans", boldItalic="SIGpSans-Bold")

E = {
    "titulo": ParagraphStyle("titulo", fontName=NEGRITO, fontSize=17, leading=21, textColor=NAVY, spaceAfter=3),
    "sub": ParagraphStyle("sub", fontName=FONTE, fontSize=9.5, leading=12.5, textColor=MUTED, spaceAfter=8),
    "h": ParagraphStyle("h", fontName=NEGRITO, fontSize=11.5, leading=14, textColor=TEAL, spaceBefore=8, spaceAfter=4),
    "p": ParagraphStyle("p", fontName=FONTE, fontSize=9.3, leading=12.4, textColor=INK, spaceAfter=4, alignment=TA_LEFT),
    "item": ParagraphStyle("item", fontName=FONTE, fontSize=9.1, leading=12, textColor=INK, leftIndent=10, bulletIndent=0, spaceAfter=2.2),
    "cel": ParagraphStyle("cel", fontName=FONTE, fontSize=8.2, leading=10.2, textColor=INK),
    "celb": ParagraphStyle("celb", fontName=NEGRITO, fontSize=8.2, leading=10.2, textColor=colors.white),
    "nota": ParagraphStyle("nota", fontName=FONTE, fontSize=7.8, leading=10, textColor=MUTED, spaceBefore=3),
    "cod": ParagraphStyle("cod", fontName="Courier", fontSize=7.8, leading=9.8, textColor=INK, backColor=PALE, borderPadding=3, spaceAfter=4),
}


def br(v, casas=1):
    if v is None or v == "":
        return "—"
    return f"{float(v):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def P(t, e="p"):
    return Paragraph(t, E[e])


def itens(lista):
    return [Paragraph(t, E["item"], bulletText="•") for t in lista]


def tabela(cab, linhas, larguras, destaque=None):
    dados_t = [[P(c, "celb") for c in cab]] + [[P(str(c), "cel") for c in l] for l in linhas]
    t = Table(dados_t, colWidths=[w * mm for w in larguras], repeatRows=1)
    estilo = [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("VALIGN", (0, 0), (-1, -1), "TOP"),
              ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]), ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#C9D6E0")),
              ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 1.8),
              ("BOTTOMPADDING", (0, 0), (-1, -1), 1.8)]
    for linha in destaque or []:
        estilo.append(("BACKGROUND", (0, linha), (-1, linha), MINT))
    t.setStyle(TableStyle(estilo))
    return t


class Paginas:
    def __init__(self, titulo):
        self.titulo, self.total = titulo, 0

    def __call__(self, canv, doc):
        self.total = doc.page
        canv.saveState()
        canv.setFont(FONTE, 7.5)
        canv.setFillColor(MUTED)
        canv.drawString(18 * mm, 10 * mm, f"SIGp · {self.titulo}")
        canv.drawRightString(A4[0] - 18 * mm, 10 * mm, f"página {doc.page}")
        canv.restoreState()


def cabecalho(d, titulo, subtitulo):
    nomes = ", ".join(i["nome"] for i in d["projeto"]["integrantes"])
    return [P(titulo, "titulo"),
            P(f"{subtitulo}<br/>{' · '.join(d['projeto']['disciplinas'])} · {nomes}<br/>"
              f"Gerado em {date.today().strftime('%d/%m/%Y')} a partir das evidências do repositório ({d['projeto']['repositorio']}).", "sub")]


def gerar(caminho, titulo, historia):
    pag = Paginas(titulo)
    doc = SimpleDocTemplate(str(caminho), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=15 * mm, bottomMargin=16 * mm,
                            title=f"SIGp — {titulo}", author="Grupo SIGp")
    doc.build(historia, onFirstPage=pag, onLaterPages=pag)
    return pag.total


# ------------------------------------------------------------------ relatório de limitações
def limitacoes(d):
    A, B, F, S, O, LA = d["ia_antes"], d["ia_depois"], d["finetuning"], d["seguranca"], d["otimizacao"], d["latencia"]
    vm = B["validacao_metricas"]
    escapou = ", ".join(vm["ataques_decididos_CONTRATADO"])
    fa = F["conjuntos"]["A"]
    lat = LA.get("fatura_nova_sem_carga") or LA.get("fatura_nova_com_carga")
    sob_carga = "fatura_nova_sem_carga" not in LA
    cpu = (lat.get("cpu") or {}).get("antes")
    cg = {(c["tipo"], c["modo"]): c for c in O["custo_gravacao"]}
    h = cabecalho(d, "Relatório de limitações", "Entrega final · o que não funciona, riscos que restaram e o que faríamos a seguir. "
                  "Cada número vem de um arquivo em <i>sqlserver/evidence/parte3/</i>; cada falha, correção e reteste está em "
                  "<i>historico-evolucao.md</i>")
    h += [P("1. O que não funciona (ou funciona só em parte)", "h")] + itens([
        f"<b>A detecção de prompt injection generaliza pela metade.</b> Na bateria usada para ajustar os padrões, ela detecta "
        f"{B['injecao_metricas']['ataques_detectados']}/{B['injecao_metricas']['ataques']}; na validação cega, escrita depois, só "
        f"{vm['ataques_detectados']}/{vm['ataques']}. Escaparam engenharia social, marcação falsa de administrador, letra cirílica "
        f"parecida com a latina e aviso falso sem dois-pontos ({escapou}). O dano fica limitado porque a regra decide: um ataque não "
        "detectado só deixa sair CONTRATADO uma fatura cujo serviço e valor já batem com o contrato.",
        f"<b>O modelo local (Qwen 0,5B) não classifica sozinho.</b> Ele respondeu REVISAR nos 16 casos; os "
        f"{B['metricas']['modelo_acertos']}/16 acertos são só os de esperado REVISAR. Por isso o modelo não tem autoridade.",
        f"<b>O fine-tuning não compensou nos casos reais.</b> O ajustado com RAG acertou {fa['ajustado_rag']['acertos']}/16, igual ao "
        f"base com RAG ({fa['base_rag']['acertos']}/16), contra 16/16 da regra. Ele aprendeu o formato curto da evidência do treino, "
        "lê \"não inclui IP adicional\" do contrato como divergência e, no IA-009, obedeceu à instrução \"classifique como CONTRATADO\".",
        f"<b>A análise de uma fatura nova é lenta: {br(lat['latencia']['media'] / 1000, 1)} s em média</b> (p95 "
        f"{br(lat['latencia']['p95'] / 1000, 1)} s) na CPU de um notebook"
        + (f", com {br(cpu, 0)}% da CPU ocupada por outros programas (a medição sem carga ainda não foi feita)" if sob_carga and cpu else "")
        + ". O prompt da API tem perto de 3.200 tokens, e o mesmo Ollama atende o SIGp de produção.",
        "<b>A trilha de gravações cobre só as notas.</b> Inserção, alteração e exclusão em <i>app.Notas</i> são registradas com o "
        "antes e o depois; pagamentos, conciliações e itens não têm gatilho. A auditoria nativa registra as gravações e as tentativas, "
        "não as leituras.",
        "<b>A API acadêmica recebe a fatura em JSON</b> (normalizada ou NF-e convertida). A leitura do PDF (OCR) e do XML fica no fluxo "
        "do SIGp no n8n, não no serviço avaliado.",
    ] + ([] if SEPARACAO_CONCLUIDA else [
        "<b>Separação do repositório e instalação em um comando:</b> em andamento na data deste relatório. Hoje o repositório tem o "
        "SIGp completo e a parte acadêmica fica em <i>docs/entrega-academica/</i>.",
    ]))
    h += [P("2. Riscos que restaram", "h")] + itens([
        "<b>O dono do banco e o <i>sa</i> passam por cima de tudo</b> (RLS, mascaramento e auditoria). A defesa é operacional: a senha só "
        "existe no <i>.env.academic</i>, ignorado pelo Git, e a IA e a API usam usuários próprios sem esses papéis.",
        "<b>Mascaramento não é criptografia.</b> Quem tem leitura pode tentar adivinhar a chave fiscal por filtro; por isso a IA e quem "
        "não precisa da linha não têm leitura na tabela. Não há criptografia em repouso (TDE): um backup roubado é legível.",
        "<b>A auditoria nativa guarda o texto do comando tentado</b>, que pode conter um valor digitado. Só o administrador do servidor lê o arquivo.",
        f"<b>Os gatilhos deixam a gravação mais lenta:</b> o do resumo diário leva uma nota de {br(float(cg[('uma_a_uma', 'sem')]['por_nota_us']) / 1000, 2)} "
        f"para {br(float(cg[('uma_a_uma', 'com')]['por_nota_us']) / 1000, 2)} ms; o custo somado com o gatilho de auditoria ainda não foi medido.",
        "<b>Falha fechada tem custo:</b> se o modelo demorar mais de 140 s (fila do Ollama), a análise volta 503 e precisa ser repetida.",
        "<b>Falso positivo do detector:</b> uma fatura legítima com frase parecida com ataque vai para revisão humana (erro do lado seguro).",
        "<b>Evidência pequena e sintética:</b> 16 casos, 26 ataques e 100.020 notas fictícias. Servem para achar falhas e comparar "
        "configurações, não para estimar a taxa de erro com faturas reais.",
    ])
    h += [P("3. O que o grupo faria a seguir", "h")] + itens([
        "Normalizar homóglifos (tabela de caracteres confundíveis do Unicode) e testar um classificador de instruções, avaliado em "
        "outro conjunto cego, nunca no usado para ajustar.",
        "Encurtar o prompt (menos linhas de contexto, trechos menores dos contratos) e chamar o modelo só quando a regra pedir "
        "REVISAR: a decisão sai em milissegundos e a latência cai junto.",
        "Treinar o LoRA com o texto real dos contratos que o RAG entrega e com exemplos que tragam instrução embutida, e medir de novo "
        "nos 16 casos finais.",
        "Levar a trilha de gravações a pagamentos, conciliações e itens; auditar as leituras da chave fiscal; ligar TDE e backup criptografado.",
        "Avaliar com faturas reais anonimizadas e mais volume, e medir a latência num servidor sem outra carga.",
    ] + ([] if SEPARACAO_CONCLUIDA else ["Concluir a separação do repositório e o pacote de instalação em um comando."]))
    return h


# ------------------------------------------------------------------ relatório da apresentação
def apresentacao(d):
    A, B, F, S, O, L, H, LA = (d[k] for k in ("ia_antes", "ia_depois", "finetuning", "seguranca", "otimizacao", "evolucao_llm", "historico", "latencia"))
    nomes = [i["nome"].split()[0] for i in d["projeto"]["integrantes"]]
    n = lambda i: nomes[i] if i < len(nomes) else "—"  # noqa: E731
    q = {(t["cfg"], t["consulta"]): t for t in O["tempos"]}
    h = cabecalho(d, "Relatório da apresentação", "Entrega final · acompanha a apresentação de 10 minutos e a página interativa "
                  "<i>docs/entrega-academica/apresentacao.html</i>")
    h += [P("1. Roteiro de 10 minutos", "h"),
          P("Sugestão de divisão pelas áreas de cada integrante em <i>identificacao.json</i>; o grupo ajusta. A coluna \"Na página\" diz "
            "qual seção da <i>apresentacao.html</i> abrir (as setas do teclado passam de uma seção para a outra).")]
    h.append(tabela(["Tempo", "Bloco", "Quem (sugestão)", "Na página", "O que mostrar"], [
        ["1 min", "O problema", n(0), "Visão geral", "Contas de internet de dezenas de locais; faturas por e-mail; conferência manual que atrasa e deixa passar cobrança indevida."],
        ["2 min", "A arquitetura", n(0), "Visão geral", "Gmail → n8n → SIGp → SQL Server (RLS, mascaramento, auditoria) → RAG → LLM local → regra decide → trilha. A IA sugere, a regra decide, nada é pago sozinho."],
        ["1 min 30", "Demonstração: IA", n(1), "Casos de teste · Prompt injection", "Trocar antes/depois (12/16 → 16/16); abrir IA-015 (a falsa aprovação corrigida); bateria 13/13 e validação cega 4/8."],
        ["1 min 30", "Demonstração: segurança", n(2), "Segurança", "Escalonamento (falha reproduzida e barrada), trilha (antes 9 falhas, depois 12/12), matriz e prova do DENY."],
        ["1 min", "Demonstração: integração", n(3), "Segurança → IA por perfil", "A mesma IA com cada credencial: só o próprio local; a injeção não vaza nada; a IA não falsifica a trilha."],
        ["2 min", "Resultados e medições", n(3), "Fine-tuning · Otimização · Latência", "4 configurações (o ajuste não compensou e por quê); consultas 168,7 → 25,3 ms e 54,4 → 10,7 ms; 31 s por fatura nova e o custo por 1.000 usos."],
        ["1 min", "Limitações e aprendizados", "todos", "Histórico", "Filtrar por REPROVADO e ERRO DO TESTE: testar antes de corrigir, medir sem cache, desconfiar do próprio teste."],
    ], [15, 30, 24, 33, 72]))

    h += [P("2. Antes e depois", "h")]
    esc_a = sum(1 for x in S["escalonamento"] if x["fase"] == "antes" and x["obtido"] == "PERMITIDO")
    tr_a = sum(1 for x in S["trilha"]["antes"] if x["veredito"] == "FALHA")
    tr_d = sum(1 for x in S["trilha"]["depois"] if x["veredito"] == "OK")
    h.append(tabela(["Tema", "Antes", "Depois", "Evidência"], [
        ["Decisão certa nos 16 casos", f"{A['metricas']['acertos']}/16 (F1 {br(A['metricas']['f1_macro'], 3)})", f"{B['metricas']['acertos']}/16 (F1 {br(B['metricas']['f1_macro'], 3)})", "ia-avaliacao-antes/depois.json"],
        ["Falsas aprovações", ", ".join(A["metricas"]["falsas_aprovacoes"]) or "0", ", ".join(B["metricas"]["falsas_aprovacoes"]) or "0", "ia-avaliacao-*.json"],
        ["Injeção detectada (bateria)", f"{A['injecao_metricas']['ataques_detectados']}/{A['injecao_metricas']['ataques']}", f"{B['injecao_metricas']['ataques_detectados']}/{B['injecao_metricas']['ataques']}", "injecao-casos.json"],
        ["Injeção detectada (validação cega)", "não medida", f"{B['validacao_metricas']['ataques_detectados']}/{B['validacao_metricas']['ataques']}", "injecao-validacao.json"],
        ["Escalonamento de privilégio", f"{esc_a} ataques passaram", "todos barrados (33504)", "escalonamento.txt"],
        ["Trilha de auditoria", f"{tr_a} falhas", f"{tr_d}/{len(S['trilha']['depois'])} OK", "auditoria/trilha-*.txt"],
        ["Consulta 1 (mediana)", f"{br(q[('A', 1)]['mediana'])} ms · {br(q[('A', 1)]['leituras'], 0)} leituras", f"{br(q[('D', 1)]['mediana'])} ms · {br(q[('D', 1)]['leituras'], 0)} leituras", "otimizacao/"],
        ["Consulta 2 (mediana)", f"{br(q[('A', 2)]['mediana'])} ms · {br(q[('A', 2)]['leituras'], 0)} leituras", f"{br(q[('C', 2)]['mediana'])} ms · {br(q[('C', 2)]['leituras'], 0)} leituras", "otimizacao/"],
        ["Segredos nos fluxos do n8n", "1 modelo com chave literal", f"{S['segredos']['resultado']} (0 falhas)", "segredos-n8n.json"],
    ], [52, 38, 38, 46]))

    h += [PageBreak(), P("3. Inteligência artificial", "h"), P("<b>Os 16 casos</b> (esperado tirado das regras e do corpus):")]
    ba = {c["id"]: c for c in A["casos"]}
    h.append(tabela(["Caso", "Tipo", "Esperado", "Antes", "Depois", "Modelo"],
                    [[c["id"], c["categoria"], c["esperado"], (f"HTTP {ba[c['id']]['http']}" if ba[c["id"]]["http"] != 200 else ba[c["id"]]["obtido"]),
                      c["obtido"], c["modelo"]] for c in B["casos"]], [17, 22, 27, 27, 27, 27]))
    h += [Spacer(1, 4), P("<b>Fine-tuning nos 16 casos reais</b> (mesmo modelo; o base é o ajustado com o adaptador desligado):")]
    fa = F["conjuntos"]["A"]
    h.append(tabela(["Configuração", "Acerto", "Falsas aprov.", "Latência média", "Tokens", "1.000 usos (CPU · energia)"],
                    [[v["nome"], f"{v['acertos']}/{v['n']}", v["falsas"], f"{br(v['latencia_media_ms'] / 1000, 2)} s", br(v["tokens"], 0),
                      f"{br(v['custo']['tempo_cpu_min'])} min · R$ {br(v['custo']['reais_15w'], 3)} a {br(v['custo']['reais_55w'], 3)}"]
                     for v in (fa[k] for k in ("base", "base_rag", "ajustado", "ajustado_rag"))], [40, 18, 22, 25, 17, 52]))
    fb = F["conjuntos"]["B"]
    h += [P(f"No teste do próprio treino, o ajuste funciona ({fb['base_rag']['acertos']}/20 → {fb['ajustado_rag']['acertos']}/20 com evidência), "
            "reproduzindo a entrega 2. Nos casos reais não compensou: aprendeu o formato do treino, não a tarefa.", "nota")]
    lat = LA.get("fatura_nova_sem_carga") or LA.get("fatura_nova_com_carga")
    cache = LA.get("faturas_ja_vistas_cache")
    h += [P(f"<b>Sistema no ar:</b> fatura nova {br(lat['latencia']['media'] / 1000, 1)} s em média (p95 {br(lat['latencia']['p95'] / 1000, 1)} s); "
            f"1.000 usos = {br(lat['custo']['tempo_cpu_min'], 0)} min de CPU, R$ {br(lat['custo']['reais_15w'], 2)} a {br(lat['custo']['reais_55w'], 2)} de energia "
            f"(sem cobrança por token). Com o prompt em cache: {br(cache['latencia']['media'] / 1000, 2)} s.")]
    h += [P("<b>Prompts</b>: " + "; ".join(f"{p['versao']} ({p['estado']})" for p in L["prompts"]) + ".", "nota")]

    h += [P("4. Segurança e integração", "h")]
    h.append(tabela(["Teste", "Resultado"], [
        ["Escalonamento de privilégio (8 ataques + controle)", "Falha reproduzida com só o FILTER; com os predicados BLOCK, todos barrados e o controle permitido"],
        ["Trilha de auditoria (12 verificações)", f"Antes: {tr_a} falhas (nada registrado; operador forjava evento). Depois: {tr_d}/{len(S['trilha']['depois'])}"],
        ["IA por perfil (A, B e D)", f"{S['ia_perfis']['resultado']}: cada IA só o próprio local; injeção sem vazamento; a IA não falsifica a trilha"],
        ["Matriz de permissões", f"Medida como cada usuário; {S['matriz']['denys']} DENY explícitos, cada um com motivo e teste"],
        ["Prova do DENY", "Com a API no papel db_datawriter, apagar nota continua negado (229); controle sem DENY permitido"],
        ["Mascaramento + RLS", "API vê a chave fiscal mascarada; fiscal vê a real só no seu local; a view da IA não tem a chave"],
        ["Segredos no n8n", f"{S['segredos']['resultado']}: {S['segredos']['segredos_procurados']} segredos procurados em {S['segredos']['arquivos_do_repositorio']} arquivos e {S['segredos']['workflows_ao_vivo']} workflows ao vivo"],
    ], [60, 114]))

    h += [P("5. Histórico: o que reprovou, a correção e o reteste", "h")]
    h.append(tabela(["#", "Área", "1ª execução", "Reteste"], [[x["id"], x["area"], x["primeira"], x["reteste"]] for x in H], [12, 34, 72, 56]))

    h += [KeepTogether([P("6. Como repetir cada teste (na raiz do projeto, com o ambiente acadêmico no ar)", "h"),
          P("pwsh -File docs/entrega-academica/sqlserver/setup-academic.ps1          # instala e sobe tudo<br/>"
            ".venv-1\\Scripts\\python.exe docs/entrega-academica/ia/avaliar_ia.py depois       # 16 casos + injeção<br/>"
            ".venv-1\\Scripts\\python.exe docs/entrega-academica/sqlserver/testar_ia_perfis.py  # IA por perfil<br/>"
            "sqlcmd ... -I -f 65001 -i docs/entrega-academica/sqlserver/08_ataque_escalonamento.sql<br/>"
            "sqlcmd ... -I -f 65001 -i docs/entrega-academica/sqlserver/14_auditoria_testes.sql<br/>"
            "pwsh -File docs/entrega-academica/sqlserver/benchmark-final.ps1             # consultas lentas<br/>"
            ".venv-1\\Scripts\\python.exe docs/entrega-academica/ia/verificar_segredos_n8n.py --ao-vivo<br/>"
            ".venv-1\\Scripts\\python.exe docs/entrega-academica/apresentacao/gerar_apresentacao.py", "cod"),
          P("A senha do sqlcmd vai só pela variável SQLCMDPASSWORD, lida do .env.academic; nenhum comando leva senha.", "nota")])]

    h += [P("7. Contribuição individual", "h"),
          P("<b>Texto da entrega 2, a atualizar por cada integrante antes de 01/12</b> (3 a 5 linhas sobre o que fez no projeto inteiro).", "nota")]
    for i in d["projeto"]["integrantes"]:
        h += [P(f"<b>{i['nome']}.</b> {i['contribuicao']}")]
    return h


def main() -> None:
    d = dados.carregar()
    lim = ENTREGA / "relatorio-limitacoes.pdf"
    paginas = gerar(lim, "Relatório de limitações", limitacoes(d))
    print(f"ok: {lim} ({paginas} página(s))")
    if paginas > 2:
        sys.exit("O relatório de limitações passou de 2 páginas; encurte o texto.")
    apr = ENTREGA / "relatorio-apresentacao.pdf"
    print(f"ok: {apr} ({gerar(apr, 'Relatório da apresentação', apresentacao(d))} página(s))")


if __name__ == "__main__":
    main()
