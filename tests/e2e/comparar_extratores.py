"""Compara o extrator antigo do WF-03 com o extrator unificado do backend sobre os mesmos textos OCR.

Pré-requisito: node tests/e2e/comparar_wf03.js (gera out/wf03_antigo.json).
Sem gabarito: mede quantos campos cada um preenche e onde discordam, para revisão humana.
"""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from backend.app import app  # noqa: E402

pasta = RAIZ / "tests" / "e2e" / ".data-test" / "ocr_textos"
antigo = json.loads((RAIZ / "tests" / "e2e" / "out" / "wf03_antigo.json").read_text(encoding="utf-8"))
cliente = app.test_client()
campos = ("emissorNome", "numeroFatura", "dataEmissao", "dataVencimento", "valorTotal", "cnpjEmissor")
preenchidos = {"antigo": dict.fromkeys(campos, 0), "novo": dict.fromkeys(campos, 0)}
so_antigo = dict.fromkeys(campos, 0)
divergencias = []
vistos = set()
total = 0
for arquivo in sorted(pasta.glob("*.json")):
    ocr = json.loads(arquivo.read_text(encoding="utf-8"))
    texto = str(ocr.get("text") or "")
    if not texto.strip() or texto in vistos:
        continue  # sem texto (PDF protegido) ou cópia idêntica
    vistos.add(texto)
    total += 1
    novo = cliente.post("/api/extracao/texto", json={"texto": texto, "ocrUsado": ocr.get("ocrUsado")}).get_json()
    velho = antigo.get(arquivo.name, {})
    for campo in campos:
        a, n = velho.get(campo), novo.get(campo)
        if campo == "numeroFatura" and n == "999999999":
            n = ""
        tem_a, tem_n = a not in (None, "", 0), n not in (None, "", 0)
        preenchidos["antigo"][campo] += tem_a
        preenchidos["novo"][campo] += tem_n
        if tem_a and not tem_n:
            so_antigo[campo] += 1
        if tem_a and tem_n and str(a).strip().casefold() != str(n).strip().casefold():
            divergencias.append((ocr.get("arquivo"), campo, a, n))

print(f"Textos distintos com conteúdo: {total}\n")
print(f"{'campo':<16}{'antigo (WF-03)':>16}{'novo (backend)':>16}{'só o antigo achou':>20}")
for campo in campos:
    print(f"{campo:<16}{preenchidos['antigo'][campo]:>16}{preenchidos['novo'][campo]:>16}{so_antigo[campo]:>20}")
print("\nSó o antigo achou (para revisar):")
for arquivo in sorted(pasta.glob("*.json")):
    ocr = json.loads(arquivo.read_text(encoding="utf-8"))
    texto = str(ocr.get("text") or "")
    if not texto.strip():
        continue
    novo = cliente.post("/api/extracao/texto", json={"texto": texto}).get_json()
    velho = antigo.get(arquivo.name, {})
    for campo in ("numeroFatura", "dataEmissao", "dataVencimento"):
        n = "" if novo.get(campo) == "999999999" else novo.get(campo)
        if velho.get(campo) and not n:
            print(f"  {arquivo.name[:36]:<36} {campo:<15} antigo={velho.get(campo)!r}")
print(f"\nDivergências (os dois acharam valores diferentes): {len(divergencias)}")
divergencias = [d for d in divergencias if str(d[2]).strip().casefold() != str(d[3]).strip().casefold()]
for arquivo, campo, a, n in divergencias[:40]:
    print(f"  {arquivo[:36]:<36} {campo:<15} antigo={str(a)[:38]!r:<42} novo={str(n)[:38]!r}")
