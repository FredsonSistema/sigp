# Contrato de API — SIGp ⇄ n8n (versão 3)

> Documento de referência da integração. Atualizado em 12/11/2026. Arquitetura em `docs/plano-correcoes.md`, seção 0.
> **Estado**: ✅ em uso hoje · 🟡 em uso, com ajuste previsto · 🔜 planejado (ainda não existe).

## 1. Princípios

1. **O n8n orquestra tudo.** Busca (Gmail, e no futuro NSDocs e ERP), OCR, extração, LLM local, análise, alertas.
2. **O SIGp recebe e informa.** Guarda os resultados (SQLite), mantém as localidades atualizadas e é a entrada manual enquanto não há ERP/NSDocs. Não processa documentos: envia ao n8n e recebe o resultado.
3. **Só API/webhook entre os sistemas.** Trocar o SIGp pelo ERP é trocar quem chama e quem recebe, sem mudar o n8n.
4. **Idempotência.** Todo documento tem um identificador estável; reenviar o mesmo documento atualiza, nunca duplica.
5. **Nada se perde.** Quem envia guarda e reenvia até receber 2xx (o SIGp já faz isso com os eventos).
6. **LLM somente local** (Ollama na rede Docker). Nenhum payload deste contrato é enviado a serviço externo.
7. **Versão no envelope.** Mudanças incompatíveis sobem `versao`; campos novos são opcionais.

## 2. Endereços e autenticação

| Quem chama | Endereço | Autenticação |
|---|---|---|
| SIGp → n8n | `http://127.0.0.1:5678/webhook/<caminho>` (no Docker: `http://n8n:5678/webhook/<caminho>`) | 🔜 Header Auth nos webhooks (hoje sem autenticação; só acessível em `127.0.0.1`) |
| n8n → SIGp | `{{$env.SIGP_API_URL}}` = `http://api:5001` | `X-API-Key: {{$env.SIGP_API_KEY}}` em toda escrita (POST/PUT/PATCH/DELETE); GET livre |
| n8n → LLM | `{{$env.SIGP_OLLAMA_URL}}` = `http://ollama:11434`, modelo `{{$env.SIGP_OLLAMA_MODEL}}` | rede interna, sem porta no Windows |
| n8n → OCR | `http://ocr:5002/extract` | rede interna, sem porta no Windows |

## 3. Identificação e idempotência

| Documento | Identificador estável | Comportamento ao reenviar |
|---|---|---|
| Nota recebida (Gmail) | `gmailMessageId` + `gmailAttachmentId` | atualiza a extração enquanto não associada |
| Nota lançada | `id`; ou `sistemaOrigem` + `idExterno` (ERP, NSDocs); ou chave fiscal | atualiza; chave fiscal de outra nota → 409 |
| Nota lançada sem número/chave real | mesmo local + mesma empresa + mesmo mês de vencimento | **recorrência**: atualiza a nota do mês (`item.recorrencia`) |
| Nota paga | `id`; ou `sistemaOrigem` + `idExterno` | atualiza |
| Fatura PDF | `id` gerado pelo SIGp | novo PDF do mesmo provedor vira a fatura atual; o anterior fica no histórico |
| Evento SIGp → n8n | `id` do evento (`eventos_saida`) | reenviado até 2xx (máx. 10 tentativas) |

Valores de `origem` / `sistemaOrigem`: `manual` (tela do SIGp), `gmail`, `n8n`, `erp`, `nsdocs`, `praxio`, `globus`.

Regras aplicadas pelo SIGp ao receber (valem para qualquer origem):
- Número ou chave vazio/inválido → `999999999` (não é identidade fiscal: nunca casa duas notas por ele).
- Sem data de emissão → data de recebimento, com `dataEmissaoOrigem = "recebimento"`.
- Valor, vencimento e nome do emissor são **obrigatórios** (400 se faltarem).
- Nota ou fatura associada a um local preenche o **provedor** dele (nome, valor, data e dia de vencimento, fatura atual); fatura mais antiga que a atual não regride; local excluído (inativo) é ignorado.

## 4. Webhooks do n8n (entrada)

### 4.1 ✅ `POST /webhook/sigp-nota-lancada` — WF-01

Corpo: o documento da nota (mesmo formato de `POST /api/notas/lancadas`, seção 5.2) + `canal` (`interface` | `integracao`).
O n8n define `origem` (`manual` para a interface, `n8n` para integração) e repassa ao SIGp; a resposta é a do SIGp (inclusive 409).
🟡 Hoje só repassa; no destino (plano B-05) o n8n normaliza o XML/JSON antes de enviar.

### 4.2 ✅ `POST /webhook/sigp-nota-paga` — WF-02

Igual ao 4.1, para pagamentos (`POST /api/notas/pagas`).

### 4.3 ✅ `POST /webhook/sigp-faturas-pdf` — WF-03

- Corpo: bytes do PDF (`Content-Type: application/pdf`, até 15 MiB, até 10 páginas lidas).
- Query (opcionais): `provedorEsperado`, `valorEsperado`, `vencimentoEsperado`, `entidadeTipo`, `entidadeId`, `localNome`, `localCidade`, `provedorId`, `notaId`.
- Resposta 200 (síncrona, pode levar até ~2 min com OCR):

```json
{
  "ok": true, "extrator": "n8n_lib_extrator_v1", "textEncontrado": true, "ocrUsado": false,
  "emissorNome": "FIBRANET TELECOMUNICACOES LTDA", "emissorEsperadoEncontrado": true,
  "cnpjEmissor": "11222333000181", "cnpjCandidatos": ["11222333000181"],
  "numeroFatura": "4455667", "numero": "4455667", "numeroPadrao": false, "chave": "999999999",
  "dataEmissao": "2026-12-01", "dataVencimento": "2026-12-12", "valorTotal": 289.9,
  "descricaoServico": "Link dedicado de internet 300 Mbps", "linhaDigitavelUsada": false,
  "comparacao": { "emissorConfere": true, "valorConfere": true, "vencimentoConfere": true },
  "camposParaRevisar": [], "aviso": ""
}
```

A extração é feita no próprio n8n (`n8n/lib/extrator.js`, `extrator: n8n_lib_extrator_v1`). Se o nó falhar, o WF-03 chama `POST /api/extracao/texto` do SIGp (contingência, `extrator: sigp_backend_unificado_v1`). As duas respostas são iguais (paridade em `tests/n8n/paridade_extrator.py`).

### 4.4 ✅ `POST /webhook/sigp-eventos` — WF-05

Enviado pelo SIGp (fila `eventos_saida`) e pelo botão "Enviar para análise".

```json
{
  "versao": 2,
  "id": "evt-…",
  "evento": "conciliacao_atualizada",
  "timestamp": "2026-11-12T20:00:00+00:00",
  "dados": {
    "status": "MATCH",
    "notaLancada": { "id": "…", "numero": "302500", "provedor_nome": "OPIX INTERNET", "valor_total": 119.9,
                     "data_vencimento": "2026-11-10", "entidade_tipo": "garagem", "entidade_id": "…" },
    "notaPaga": { "valor_pago": 119.9, "data_pagamento": "2026-11-09" },
    "fatura": { "id": "…", "dados": { "valorTotal": 119.9, "dataVencimento": "2026-11-10", "emissorNome": "…" } },
    "local": { "nome": "Rota Aracaju", "cidade": "Aracaju" },
    "comparacao": {}, "observacao": "", "valorPagoAcumulado": 119.9, "aceitaDivergencia": false
  }
}
```

`evento`: `conciliacao_atualizada` (automático, a cada mudança de status) ou `analise_manual` (botão).
`status`: `PENDENTE`, `PAGO_PARCIAL`, `AGUARDANDO_FATURA`, `DIVERGENCIA`, `MATCH` (`MATCH` = 3 evidências: lançada + paga + fatura conferidas).
Resposta: 200 imediato (o processamento segue em segundo plano). O resultado volta por `POST /api/analises` (5.6).
✅ Desde a fase C: `MATCH` e `DIVERGENCIA` são analisados pela LLM local e gravados no **SIG** com `dados.requerValidacao: true` (aguardam o gerente); os demais status ficam com o texto da regra. Também recebe `evento: "decisao_gerente"` (enviado pelo SIGp, seção 5.8): `VALIDADA` ou `CORRIGIDA` geram o resumo executivo (LLM local) gravado na **SIE**; `DEVOLVIDA` encerra.

### 4.5 🟡 `POST /webhook/sigp-tomada-decisao` — WF-07 (legado)

Usado só pelo painel legado (`sie:5000`). A decisão do gerente agora é feita na aba SIG e gravada em `POST /api/sig/decisoes` (5.8); o SIGp avisa o n8n pelo evento `decisao_gerente` (4.4).

### 4.6 ✅ Gmail — WF-08 (gatilho interno, a cada 5 min)

Não é chamado pelo SIGp. Lê a caixa, OCR, regras, LLM local, e grava em `POST /api/notas-recebidas` (5.1). WF-09 aplica as etiquetas `SIGp/...` (5.1).

### 4.7 🔜 `POST /webhook/sigp-documento` — entrada genérica (A-01/B-05)

Um único webhook para qualquer documento manual (NFS-e XML/JSON, NFCom, fatura PDF, nota paga), no formato do envelope da seção 6. Substituirá 4.1–4.3 sem quebrar: os três continuam aceitos.

## 5. API do SIGp (chamada pelo n8n)

### 5.1 ✅ Notas recebidas (Gmail)

| Rota | Uso |
|---|---|
| `POST /api/notas-recebidas` (multipart) | `gmailMessageId`, `gmailAttachmentId`, `gmailThreadId`, `assunto`, `remetente`, `recebidaEm`, `arquivo` (PDF), `dadosExtracao` (JSON). 201 criada, 200 já existia (idempotente) |
| `POST /api/notas-recebidas/classificar` | `{texto, assunto, remetente, nomeArquivo}` → categoria e confiança por regras e provedores cadastrados |
| `GET /api/notas-recebidas?etiquetaPendente=1` | notas associadas aguardando etiqueta Gmail |
| `POST /api/notas-recebidas/<id>/confirmar-etiqueta` | `{ok: true}` ou `{ok: false, erro}` |

Associar, descartar e restaurar são ações da tela do SIGp (`PATCH .../associar`, `.../descartar`, `.../restaurar`); cada uma grava um exemplo rotulado em `extracao_feedback` (base do aprendizado da LLM).

**XML da nota fiscal (v19).** Além do PDF em `arquivo`, o WF-08 envia o XML da mesma mensagem em `xmlConteudo` (texto) e `xmlNomeArquivo`;
também é aceito como arquivo em `xml` (preserva os bytes, recomendado para XML assinado). Até 2 MiB, sem DOCTYPE/ENTITY.
Mensagem só com XML: o XML vem em `arquivo`, a nota entra em `REVISAO` com `semPdf: true` e não associa até a fatura PDF chegar (409).
Em `dadosExtracao`, `xmlFiscal` traz a leitura do XML (`n8n/lib/xml_fiscal.js`) e os campos fiscais já vêm com a prioridade do XML; `divergenciasXml` lista PDF × XML.

| Rota | Uso |
|---|---|
| `GET /api/notas-recebidas/<id>/xml` | XML guardado da nota recebida (`xmlUrl` na listagem) |
| `GET /api/notas/lancadas/<id>/xml` | XML da nota lançada (copiado na associação; vale o da associação mais recente) |
| `PATCH /api/notas-recebidas/<id>/analise` e `/liberar` | nota em dúvida: `EM_ANALISE` com `observacao` e `operador`; `/liberar` devolve à fila |

### 5.2 ✅ `POST /api/notas/lancadas`

```json
{
  "id": "opcional-estavel",
  "entidadeTipo": "agencia | rodoviaria | garagem",
  "entidadeId": "id-do-local",
  "origem": "manual | n8n | erp | nsdocs",
  "sistemaOrigem": "erp", "idExterno": "123",
  "source": "json | xml",
  "dados": {
    "chave": "", "numero": "302500", "serie": "1", "provedorNome": "OPIX INTERNET",
    "valor": 119.9, "dataEmissao": "2026-11-01", "dataVencimento": "2026-11-10",
    "servicos": [{ "descricao": "Link 300 Mbps", "valorTotal": 119.9, "classificacao": "CONTRATADO" }]
  }
}
```

`dados` pode ser o XML da NFS-e (`source: "xml"`). Resposta: `{ok, item, conciliacoes, provedor, provedorAcao, provedorAviso}`; `item.recorrencia` quando a nota do mês foi atualizada. 409 = chave fiscal de outra nota.

### 5.3 ✅ `POST /api/notas/pagas`

Igual a 5.2 + `valorPago`, `dataPagamento`, `notaLancadaId` (opcional; sem ele o SIGp procura a única nota correspondente). Resposta inclui `conciliacao`.

### 5.4 ✅ `POST /api/faturas` (multipart)

`arquivo` (PDF), `dadosExtracao` (JSON revisado; `emissorConfirmado: true` obrigatório), `entidadeTipo`, `entidadeId`, `notaLancadaId` (opcional), `provedorId` (opcional), `provedorEsperado`. Resposta inclui `provedor`/`provedorAcao`.

### 5.5 ✅ `GET /api/alertas?dias=7&tipo=vencimento,fatura_ausente,divergencia,pagamento&hoje=AAAA-MM-DD`

Alertas ordenados por severidade (`VENCIDO`, `VENCE_HOJE`, `VENCE_EM_BREVE`, `AGUARDANDO_FATURA`, `FATURA_AUSENTE`, `DIVERGENCIA`, `PAGO_COM_ATRASO`, `PAGO`). Tipo `pagamento`: `PAGO` (info) e `PAGO_COM_ATRASO` (média). O vencimento da fatura atual do provedor tem prioridade sobre o dia cadastrado; o alerta do provedor não repete o da nota do mesmo local. Rótulo do local sem tipo repetido ("Agência Itacaré") e valores em `R$ 174,00`. Usado pelo WF-06. Locais excluídos não geram alerta.

### 5.6 ✅ `POST /api/analises` — resultado da análise (SIG e SIE)

```json
{ "escopo": "SIG | SIE", "titulo": "Ciclo fechado · Garagem Rota Aracaju · NF 302500", "referencia": "id-da-nota",
  "conteudo": "texto para a tela", "modelo": "qwen2.5:3b (local)", "dados": { "parecerIA": {} }, "origem": "n8n" }
```

`GET /api/analises?escopo=SIG|SIE` lista para as abas.

`GET /api/sie/resumo`: indicadores contam só ciclos MATCH com análise SIG `VALIDADA` ou `CORRIGIDA`. Campos extras: `aguardandoGerente` (ciclos fechados sem decisão), `valorAguardandoGerente`, `devolvidosPeloGerente`.

### 5.7 ✅ Eventos e contingência

| Rota | Uso |
|---|---|
| `POST /api/eventos/reenviar` | reenvia ao n8n os eventos pendentes/falhos (WF-06 a cada 15 min) |
| `GET /api/eventos?status=` | fila de eventos |
| `POST /api/extracao/texto` | ✅ extrator do SIGp: `{texto, ocrUsado, provedorEsperado, valorEsperado, vencimentoEsperado}` → resposta igual a 4.3. No destino, só **contingência** (n8n fora do ar) |
| `GET /api/health` | saúde e configuração (`autenticacao`, `exigirFatura`, `eventosN8n`) |

### 5.8 ✅ Decisão do gerente (aba SIG)

| Rota | Uso |
|---|---|
| `POST /api/sig/decisoes` | `{analiseId, acao: validar\|corrigir\|devolver, justificativa, conteudoCorrigido, usuario}`. Justificativa obrigatória para corrigir/devolver; uma decisão por análise (409 se já decidida). Grava em `decisoes_gerente` e emite `decisao_gerente` para o n8n |
| `GET /api/sig/decisoes?analiseId=` | histórico de decisões |
| `GET /api/analises?escopo=SIG&status=PENDENTE` | análises que aguardam o gerente (`status_validacao`: `PENDENTE`, `VALIDADA`, `CORRIGIDA`, `DEVOLVIDA`, `SUBSTITUIDA`) |

### 5.9 🔜 Planejado

| Rota | Fase | Uso |
|---|---|---|
| `GET /api/llm/exemplos?provedor=&limite=` | D-02 | exemplos confirmados (associações, descartes, decisões) para o n8n montar o prompt |
| `POST /api/resultados` | A-03 | retorno assíncrono genérico do n8n (resultado de extração/análise de um documento enviado pela entrada genérica) |

## 6. Envelope v3 (entrada genérica 🔜 e retorno assíncrono 🔜)

```json
{
  "versao": 3,
  "id": "doc-…",
  "tipo": "nfse | nfcom | fatura_pdf | nota_paga | decisao_gerente",
  "origem": "manual | gmail | erp | nsdocs",
  "sistemaOrigem": "sigp", "idExterno": "…",
  "enviadoEm": "2026-11-12T20:00:00-03:00",
  "local": { "tipo": "agencia", "id": "…" },
  "retorno": { "url": "http://api:5001/api/resultados", "correlacao": "…" },
  "conteudo": { "formato": "xml | json | pdf_base64", "dados": "…" },
  "metadados": { "operador": "…", "observacao": "…" }
}
```

`id` é estável (o mesmo documento reenviado tem o mesmo `id`) e garante a idempotência.
Resposta imediata: `202 {"ok": true, "id": "doc-…", "recebidoEm": "…"}`. O resultado chega depois em `retorno.url` com o mesmo `id` e `correlacao`.

## 7. Códigos de resposta

| Código | Significado | O que fazer |
|---|---|---|
| 200 / 201 | gravado (201 = criado) | — |
| 202 | recebido para processamento assíncrono | aguardar o retorno |
| 400 | dado inválido ou obrigatório ausente (valor, vencimento, emissor) | corrigir; **não** reenviar igual |
| 401 | `X-API-Key` ausente ou errada | configurar a chave |
| 404 | documento/local inexistente | conferir o id |
| 409 | conflito de identidade (chave de outra nota; divergência sem confirmação) | revisão humana |
| 413 | arquivo grande demais (PDF > 15 MiB) | — |
| 422 | PDF sem texto reconhecível | entrada manual |
| 502 / 503 | OCR, LLM ou n8n indisponível | reenviar depois (fila) |

## 8. Status

- **Conciliação**: `PENDENTE` → `PAGO_PARCIAL` → `AGUARDANDO_FATURA` → `MATCH`; `DIVERGENCIA` quando identidade, local, valor, serviço ou fatura não batem. Pagamento integral após o vencimento: nota paga `PAGO_COM_ATRASO`.
- **Nota recebida**: `AGUARDANDO_ASSOCIACAO`, `REVISAO`, `ASSOCIADA`, `DESCARTADA` (reversível).
- **Alerta**: `VENCIDO`, `VENCE_HOJE`, `VENCE_EM_BREVE`, `AGUARDANDO_FATURA`, `FATURA_AUSENTE`, `DIVERGENCIA`, `PAGO`, `PAGO_COM_ATRASO`.

## 9. Regras de conciliação (inalteradas da versão 2)

- Nota lançada, nota paga e fatura podem chegar em qualquer ordem e são persistidas mesmo sem formar par. O SIGp associa lançada e paga automaticamente só quando identidade e local apontam para uma única combinação.
- `MATCH` exige identidade compatível, mesmo local, valor integral pago e serviços revisados como `CONTRATADO`; com `SIGP_EXIGIR_FATURA=1`, também a fatura conferida.
- Sem chave, a identidade é número + série + provedor + data de emissão. O valor padrão `999999999` não conta como identidade.
- Pagamentos parciais ficam `PAGO_PARCIAL` e não liberam `MATCH`; pagamentos distintos da mesma nota são acumulados.
- `aceitaDivergencia` no evento `analise_manual` autoriza encaminhar a análise; não altera o status nem transforma divergência em `MATCH`.
- A regra determinística do SIGp decide o status; a LLM analisa, explica e sinaliza (D13 pendente de confirmação).

## 10. Integrações futuras (mesmo contrato)

| Fonte | Como entra | Mapeamento |
|---|---|---|
| NSDocs (NFS-e/NFCom) | workflow agendado no n8n → extração → 5.2 | `origem: nsdocs`, `sistemaOrigem: nsdocs`, `idExterno` = id do NSDocs |
| ERP — nota lançada | workflow agendado ou webhook do ERP → 5.2 | `origem: erp`, `idExterno` = id do lançamento |
| ERP — nota paga | idem → 5.3 | `idExterno` = id do pagamento, `notaLancadaId` quando o ERP informar |
| Resultados para o ERP | o n8n chama a API do ERP no lugar de 5.6 | mesmo conteúdo do resultado SIG/SIE |
