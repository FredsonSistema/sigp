// Configurações > Integração: listas recolhíveis com os campos e balões de ajuda (o que é, para que serve,
// como configurar, onde achar). Grava em window.SIGP_CONFIG; o estado do servidor vem de GET /api/integracao/estado.
(() => {
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  let seq = 0;

  function balao(ajuda) {
    const id = `cfg-balao-${++seq}`;
    return `<button type="button" class="cfg-help" aria-expanded="false" aria-controls="${id}" aria-label="Ajuda" data-cfg-help>?</button>
      <div class="cfg-balao" id="${id}" role="note" hidden>
        <div><b>O que é:</b> ${esc(ajuda.oque)}</div>
        <div><b>Para que serve:</b> ${esc(ajuda.para)}</div>
        <div><b>Como configurar:</b> ${esc(ajuda.como)}</div>
        <div><b>Onde achar:</b> ${esc(ajuda.onde)}</div>
      </div>`;
  }

  const ORIGEM = { tela: 'configurado nesta tela', instalacao: 'padrão da instalação (.env)', vazio: 'não configurado' };

  function campo(nome) {
    const c = window.SIGP_CONFIG.CAMPOS[nome];
    const valor = window.SIGP_CONFIG.get(nome);
    const origem = window.SIGP_CONFIG.origem(nome);
    let entrada;
    if (c.tipo === 'opcoes') {
      entrada = `<select class="f" data-cfg="${nome}">${c.opcoes.map(([v, r]) => `<option value="${esc(v)}"${v === valor ? ' selected' : ''}>${esc(r)}</option>`).join('')}</select>`;
    } else {
      const tipo = c.tipo === 'segredo' ? 'password' : 'text';
      entrada = `<div class="cfg-linha"><input class="f mono-in" type="${tipo}" data-cfg="${nome}" value="${esc(valor)}" autocomplete="off" placeholder="${esc(c.padrao() || '')}">
        ${c.tipo === 'segredo' ? '<button type="button" class="ghost small" data-cfg-mostrar title="Mostrar/ocultar">👁</button>' : ''}</div>`;
    }
    return `<div class="cfg-campo">
      <div class="cfg-rotulo"><label>${esc(c.rotulo)}</label>${balao(c.ajuda)}</div>
      ${entrada}
      <div class="hint" data-cfg-origem="${nome}">${esc(ORIGEM[origem])}${c.tipo === 'webhook' && window.SIGP_CONFIG.webhookUrl(nome) ? ` · ${esc(window.SIGP_CONFIG.webhookUrl(nome))}` : ''}</div>
    </div>`;
  }

  // Variáveis do servidor e do n8n: só leitura (ficam no .env; segredos nunca aparecem aqui).
  const SERVIDOR = [
    ['SIGP_API_KEY', 'Chave exigida pela API em toda gravação.', 'Proteger a API: sem ela, qualquer programa da rede grava dados.', 'Gere um texto aleatório longo e coloque em SIGP_API_KEY=. Use o mesmo valor aqui na tela (grupo 1).', 'Arquivo .env na pasta do sistema.'],
    ['SIGP_CORS_ORIGINS', 'Endereços de tela que podem chamar a API.', 'O navegador só deixa esta tela falar com a API se o endereço dela estiver na lista.', 'Endereço desta tela (ex.: http://127.0.0.1:8000); vários, separados por vírgula.', 'Arquivo .env, linha SIGP_CORS_ORIGINS=.'],
    ['SIGP_N8N_EVENTOS_URL', 'Webhook do n8n que recebe os eventos da API (conciliação, decisão do gerente).', 'A API avisa o n8n sozinha; eventos que falham ficam na fila e são reenviados.', 'URL completa do webhook do WF-05, vista pelo container da API: http://n8n:5678/webhook/sigp-eventos.', 'Arquivo .env; no n8n, workflow WF-05, nó Webhook.'],
    ['SIGP_N8N_TOKEN', 'Token que a API envia ao n8n (cabeçalho Authorization: Bearer).', 'Garante que o webhook do n8n só aceite eventos da API.', 'O mesmo texto na credencial "Header Auth" do webhook WF-05 no n8n.', 'Arquivo .env; no n8n, Credentials.'],
    ['SIGP_EXIGIR_FATURA', 'Regra da conciliação: exigir a fatura PDF para fechar o ciclo (MATCH).', 'Com 1, só fecha com nota lançada + nota paga + fatura conferida.', '1 (recomendado) ou 0.', 'Arquivo .env.'],
    ['SIGP_PDF_SENHA_CNPJS', 'Raízes de CNPJ das empresas do grupo, usadas para abrir PDFs com senha (Brisanet, Claro...).', 'O OCR testa o começo do CNPJ como senha; a senha nunca é gravada.', 'Os 8 primeiros dígitos de cada CNPJ, separados por vírgula.', 'Arquivo .env (serviço OCR).'],
    ['SIGP_PUBLIC_API_URL', 'Endereço padrão da API para esta tela (quando o usuário não configurou nada).', 'Uma instalação nova já abre funcionando.', 'Igual ao endereço da API do grupo 1.', 'Arquivo .env (serviço web).'],
    ['SIGP_PUBLIC_N8N_URL', 'Endereço padrão do n8n para esta tela.', 'Uma instalação nova já abre funcionando.', 'Igual ao endereço do n8n do grupo 2.', 'Arquivo .env (serviço web).'],
  ];
  const N8N = [
    ['SIGP_API_URL', 'Endereço da API visto de dentro do n8n.', 'Todos os workflows chamam a API por ele ({{$env.SIGP_API_URL}}).', 'Na rede Docker: http://api:5001. Se o sistema for trocado, aponte para a API do sistema novo.', 'docker-compose.yml, serviço n8n, "environment".'],
    ['SIGP_API_KEY (no n8n)', 'A chave da API usada pelos workflows.', 'Os workflows gravam na API com ela.', 'Mesmo valor de SIGP_API_KEY (vem do .env).', 'docker-compose.yml, serviço n8n.'],
    ['SIGP_OLLAMA_URL / SIGP_OLLAMA_MODEL', 'Endereço e modelo da IA local (Ollama).', 'Classificação dos e-mails, análises e resumos.', 'Padrão: http://ollama:11434 e qwen2.5:3b.', 'docker-compose.yml e .env.'],
    ['Conta do Gmail', 'A caixa de e-mail que o WF-08 lê e etiqueta.', 'É de onde chegam as faturas e avisos dos provedores.', 'No n8n: Credentials > Gmail account (OAuth do Google); depois ative o WF-08.', 'Editor do n8n, menu Credentials.'],
    ['Notificações', 'E-mail do relatório, Telegram e WhatsApp.', 'Enviar alertas e resumos para fora do sistema.', 'SIGP_RELATORIO_EMAIL, SIGP_TELEGRAM_CHAT_ID, SIGP_WHATSAPP_URL/NUMERO/APIKEY; credenciais no n8n.', 'Arquivo .env e Credentials do n8n.'],
  ];

  function linhaSomenteLeitura([nome, oque, para, como, onde], estado) {
    const st = estado ? `<span class="cfg-estado ${estado.ok ? 'cfg-ok' : 'cfg-falta'}">${esc(estado.texto)}</span>` : '';
    return `<div class="cfg-campo cfg-leitura"><div class="cfg-rotulo"><code>${esc(nome)}</code>${balao({ oque, para, como, onde })}${st}</div></div>`;
  }

  function estadoServidor(nome, s) {
    if (!s) return null;
    const v = (s.variaveis || {})[nome];
    if (!v) return null;
    if (v.segredo) return { ok: v.definida, texto: v.definida ? 'definida' : 'não definida' };
    return { ok: v.definida, texto: v.definida ? (v.valor || 'definida') : 'não definida' };
  }

  async function render(alvo) {
    const box = typeof alvo === 'string' ? document.getElementById(alvo) : alvo;
    if (!box) return;
    let estado = null;
    try {
      const r = await fetch(`${window.SIGP_CONFIG.apiUrl()}/api/integracao/estado`);
      if (r.ok) estado = await r.json();
    } catch (e) { estado = null; }
    const grupos = (g) => Object.keys(window.SIGP_CONFIG.CAMPOS).filter((n) => window.SIGP_CONFIG.CAMPOS[n].grupo === g).map(campo).join('');
    // O bloco do webhook de contas (campos, fila e log da tela) é preservado entre um desenho e outro.
    const contas = document.getElementById('cfgContasHolder');
    const contasAberto = box.querySelector('#cfgGrupoContas')?.open;
    if (contas) contas.remove();
    box.innerHTML = `
      <details class="nr-list cfg-grupo" open><summary><span class="nr-list-title">1. Sistema (API)</span><span class="hint">onde ficam os dados e as regras</span></summary>
        <div class="cfg-corpo">${grupos('api')}
          <div class="task-add-row"><button type="button" class="ghost small" data-cfg-testar="api">🔌 Testar API</button><span class="hint" data-cfg-resultado="api"></span></div></div></details>
      <details class="nr-list cfg-grupo"><summary><span class="nr-list-title">2. n8n e webhooks</span><span class="hint">orquestrador: Gmail, IA local, alertas</span></summary>
        <div class="cfg-corpo">${grupos('n8n')}
          <div class="task-add-row"><button type="button" class="ghost small" data-cfg-testar="n8n">🔌 Testar n8n</button><span class="hint" data-cfg-resultado="n8n"></span></div></div></details>
      <details class="nr-list cfg-grupo" id="cfgGrupoContas"><summary><span class="nr-list-title">3. Webhook de contas de provedores</span><span class="hint">envio de alterações de contas, com fila e reenvio</span></summary>
        <div class="cfg-corpo" id="cfgContasCorpo"></div></details>
      <details class="nr-list cfg-grupo"><summary><span class="nr-list-title">4. Servidor e serviços</span><span class="hint">arquivo .env · só leitura${estado ? '' : ' · API sem resposta'}</span></summary>
        <div class="cfg-corpo">
          ${estado ? `<div class="hint">OCR: ${estado.ocr?.ok ? `no ar · ${estado.ocr.regrasSenha ?? 0} regra(s) de senha de PDF` : 'sem resposta'} · IA local: ${estado.ollama?.disponivel ? `no ar (${esc(estado.ollama.modeloConfigurado || '')})` : 'sem resposta'} · Eventos para o n8n: ${esc(estado.eventos?.texto || '—')}</div>` : ''}
          ${SERVIDOR.map((l) => linhaSomenteLeitura(l, estadoServidor(l[0], estado))).join('')}
          <div class="hint">Mudou o .env? Rode <code>docker compose up -d</code> na pasta do sistema para aplicar.</div></div></details>
      <details class="nr-list cfg-grupo"><summary><span class="nr-list-title">5. Variáveis do n8n e e-mail</span><span class="hint">configuradas no n8n e no docker-compose</span></summary>
        <div class="cfg-corpo">${N8N.map((l) => linhaSomenteLeitura(l, null)).join('')}</div></details>
      <div class="task-add-row" style="margin-top:10px">
        <button class="primary small" type="button" data-cfg-salvar>Salvar integração</button>
        <button class="ghost small" type="button" data-cfg-restaurar>Usar padrões da instalação</button>
        <span class="hint" data-cfg-status role="status" aria-live="polite"></span>
      </div>`;
    if (contas) {
      contas.hidden = false;
      box.querySelector('#cfgContasCorpo').appendChild(contas);
      if (contasAberto) box.querySelector('#cfgGrupoContas').open = true;
    }
    ligar(box);
  }

  function fecharBaloes(box, exceto) {
    box.querySelectorAll('[data-cfg-help][aria-expanded="true"]').forEach((b) => {
      if (b === exceto) return;
      b.setAttribute('aria-expanded', 'false');
      document.getElementById(b.getAttribute('aria-controls')).hidden = true;
    });
  }

  function ligar(box) {
    if (box.dataset.ligado) return;
    box.dataset.ligado = '1';
    box.addEventListener('click', async (ev) => {
      const help = ev.target.closest('[data-cfg-help]');
      if (help) {
        const aberto = help.getAttribute('aria-expanded') === 'true';
        fecharBaloes(box, help);
        help.setAttribute('aria-expanded', String(!aberto));
        document.getElementById(help.getAttribute('aria-controls')).hidden = aberto;
        return;
      }
      if (ev.target.closest('[data-cfg-mostrar]')) {
        const inp = ev.target.closest('.cfg-linha').querySelector('input');
        inp.type = inp.type === 'password' ? 'text' : 'password';
        return;
      }
      if (ev.target.closest('[data-cfg-salvar]')) {
        const valores = {};
        box.querySelectorAll('[data-cfg]').forEach((el) => { valores[el.dataset.cfg] = el.value; });
        const ruim = ['apiUrl', 'n8nUrl'].find((n) => valores[n] && !/^https?:\/\/[^\s]+$/i.test(valores[n].trim()));
        if (ruim) {
          box.querySelector('[data-cfg-status]').textContent = `Endereço inválido em "${window.SIGP_CONFIG.CAMPOS[ruim].rotulo}": use http://... ou https://...`;
          return;
        }
        window.SIGP_CONFIG.set(valores);
        await render(box);
        box.querySelector('[data-cfg-status]').textContent = 'Integração salva. As próximas chamadas já usam os novos valores.';
        window.dispatchEvent(new CustomEvent('sigp:integracao-atualizada'));
        return;
      }
      if (ev.target.closest('[data-cfg-restaurar]')) {
        window.SIGP_CONFIG.restaurarPadroes();
        await render(box);
        box.querySelector('[data-cfg-status]').textContent = 'Usando os padrões da instalação (.env).';
        window.dispatchEvent(new CustomEvent('sigp:integracao-atualizada'));
        return;
      }
      const testar = ev.target.closest('[data-cfg-testar]');
      if (testar) {
        const saida = box.querySelector(`[data-cfg-resultado="${testar.dataset.cfgTestar}"]`);
        const url = (box.querySelector(`[data-cfg="${testar.dataset.cfgTestar === 'api' ? 'apiUrl' : 'n8nUrl'}"]`)?.value || '').trim().replace(/\/+$/, '');
        saida.textContent = 'Testando…';
        saida.textContent = await (testar.dataset.cfgTestar === 'api' ? testarApi(url) : testarN8n(url));
      }
    });
    box.addEventListener('keydown', (ev) => { if (ev.key === 'Escape') fecharBaloes(box); });
  }

  async function testarApi(url) {
    if (!url) return 'Informe o endereço da API.';
    try {
      const r = await fetch(`${url}/api/health`);
      return r.ok ? `✅ API respondeu (${url}).` : `❌ A API respondeu HTTP ${r.status}.`;
    } catch (e) {
      return '❌ Sem resposta. Confira o endereço, se o container da API está no ar e se SIGP_CORS_ORIGINS inclui o endereço desta tela.';
    }
  }

  async function testarN8n(url) {
    if (!url) return 'Informe o endereço do n8n.';
    try {
      // O n8n não libera CORS para esta tela: "no-cors" só confirma que o endereço responde.
      await fetch(`${url}/healthz`, { mode: 'no-cors' });
      return `✅ O n8n respondeu (${url}). Confira se os workflows dos webhooks estão ativos.`;
    } catch (e) {
      return '❌ Sem resposta. Confira o endereço e se o container sigp_n8n está no ar.';
    }
  }

  window.SIGP_CONFIG_TELA = { render };
})();
