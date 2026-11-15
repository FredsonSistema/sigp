(() => {
  const formatMoney = (value) => new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  }).format(Number(value) || 0);

  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[character]);

  function monthLabel(value) {
    const [year, month] = value.split('-').map(Number);
    return new Intl.DateTimeFormat('pt-BR', { month: 'short' }).format(new Date(year, month - 1, 1));
  }

  function renderBars(rows, valueField) {
    const maximum = Math.max(1, ...rows.map((row) => Number(row[valueField]) || 0));
    return rows.map((row) => {
      const value = Number(row[valueField]) || 0;
      const height = value ? Math.max(3, (value / maximum) * 100) : 0;
      return `<div class="sig-bar-row" title="${escapeHtml(row.nome)}: ${formatMoney(value)}">
        <div class="sig-bar-label">${escapeHtml(row.nome)}</div>
        <div class="sig-bar-track"><span style="width:${height}%"></span></div>
        <div class="sig-bar-value">${formatMoney(value)}</div>
      </div>`;
    }).join('') || '<div class="dash-empty">Sem dados para o período.</div>';
  }

  function renderMonthly(rows) {
    const maximum = Math.max(1, ...rows.flatMap((row) => [Number(row.lancado) || 0, Number(row.pago) || 0]));
    return rows.map((row) => {
      const launchedHeight = row.lancado ? Math.max(2, (row.lancado / maximum) * 100) : 0;
      const paidHeight = row.pago ? Math.max(2, (row.pago / maximum) * 100) : 0;
      return `<div class="sig-month" aria-label="${escapeHtml(monthLabel(row.mes))}: lançado ${formatMoney(row.lancado)}, pago ${formatMoney(row.pago)}">
        <div class="sig-month-bars">
          <span class="sig-month-launched" style="height:${launchedHeight}%" title="Lançado: ${formatMoney(row.lancado)}"></span>
          <span class="sig-month-paid" style="height:${paidHeight}%" title="Pago: ${formatMoney(row.pago)}"></span>
        </div>
        <span>${escapeHtml(monthLabel(row.mes))}</span>
      </div>`;
    }).join('');
  }

  function makeQuery(form) {
    const params = new URLSearchParams();
    const fields = new FormData(form);
    for (const [key, value] of fields.entries()) {
      if (String(value).trim()) params.set(key, String(value).trim());
    }
    return params.toString();
  }

  async function render() {
    const container = document.getElementById('view_sig');
    if (!container) return;
    container.innerHTML = '<div class="dash-empty" role="status">Carregando indicadores do SIG…</div>';

    const apiUrl = window.SIGP_CONFIG.apiUrl();
    try {
      const base = apiUrl.replace(/\/$/, '');
      const [response, extras] = await Promise.all([fetch(`${base}/api/sig/resumo`), loadExtras(base)]);
      const initial = await response.json();
      if (!response.ok || !initial.ok) throw new Error(initial.error || `HTTP ${response.status}`);
      container.innerHTML = renderDashboard(initial, extras);
      bindFilters(container, initial, {}, extras);
      container.onclick = (event) => {
        const button = event.target.closest('[data-decisao]');
        if (button) decidir(container, button);
      };
    } catch (error) {
      container.innerHTML = `<div class="backup-warn" role="alert">Não foi possível carregar o SIG: ${escapeHtml(error.message || 'falha de comunicação com a API')}.</div>
        <button type="button" class="ghost small" id="sigRetry">Tentar novamente</button>`;
      container.querySelector('#sigRetry').addEventListener('click', render);
    }
  }

  // Alertas (vencimentos, fatura ausente, divergências) e a análise mais recente da IA (gravada pelo n8n).
  async function loadExtras(base) {
    const dias = Number(window.CONFIG?.alertaFaturaDias) || 7;
    const [alerts, analyses] = await Promise.all([
      fetch(`${base}/api/alertas?dias=${dias}`).then((r) => r.json()).catch(() => ({ items: [] })),
      fetch(`${base}/api/analises?escopo=SIG&limite=30`).then((r) => r.json()).catch(() => ({ items: [] })),
    ]);
    const todas = (analyses.items || []).filter((item) => item.status_validacao !== 'SUBSTITUIDA');
    return {
      alertas: alerts.items || [],
      pendentes: todas.filter((item) => item.status_validacao === 'PENDENTE'),
      decididas: todas.filter((item) => ['VALIDADA', 'CORRIGIDA', 'DEVOLVIDA'].includes(item.status_validacao)).slice(0, 8),
      analise: todas.find((item) => !item.status_validacao) || null,
    };
  }

  const VALIDACAO_LABELS = {
    PENDENTE: 'Aguardando o gerente', VALIDADA: 'Validada', CORRIGIDA: 'Validada com correção', DEVOLVIDA: 'Devolvida',
  };

  function currentUser() {
    try { return JSON.parse(localStorage.getItem('sigp_auth') || '{}').user || ''; } catch { return ''; }
  }

  function renderDecisionCard(item) {
    const llm = item.dados?.analiseLLM || {};
    const discorda = llm.discordaDaRegra ? '<p class="backup-warn" role="status">A LLM discorda da regra do sistema. O status oficial é o da regra: confira antes de validar.</p>' : '';
    return `<article class="nfse-card" data-analise-id="${escapeHtml(item.id)}" style="margin-bottom:12px">
      <p class="hint">${escapeHtml(new Date(item.created_at).toLocaleString('pt-BR'))} · <strong>${escapeHtml(item.titulo || 'Análise')}</strong>${item.modelo ? ` · ${escapeHtml(item.modelo)}` : ''}</p>
      ${discorda}
      <div style="white-space:pre-wrap">${escapeHtml(item.conteudo)}</div>
      <div class="nfse-grid" style="margin-top:10px">
        <label class="full">Justificativa (obrigatória para corrigir ou devolver)
          <textarea class="f" data-role="justificativa" rows="2" maxlength="2000" placeholder="Ex.: valor pago confere com o comprovante; ou: falta a fatura do mês"></textarea>
        </label>
        <label class="full" data-role="correcao-wrap" hidden>Análise corrigida (vai para o executivo no lugar da original)
          <textarea class="f" data-role="correcao" rows="5" maxlength="8000">${escapeHtml(String(item.conteudo || '').split('\nDados do sistema:')[0].trim())}</textarea>
        </label>
      </div>
      <div class="task-add-row" style="margin-top:8px">
        <button class="primary small" type="button" data-decisao="validar">Validar</button>
        <button class="ghost small" type="button" data-decisao="corrigir">Corrigir</button>
        <button class="ghost small" type="button" data-decisao="devolver">Devolver</button>
        <span class="hint" data-role="decisao-status" aria-live="polite"></span>
      </div>
    </article>`;
  }

  function renderDecisions(extras) {
    const pendentes = extras?.pendentes || [];
    const decididas = extras?.decididas || [];
    const lista = pendentes.length
      ? pendentes.map(renderDecisionCard).join('')
      : '<div class="dash-empty">Nenhuma análise aguardando decisão. O n8n envia para cá os ciclos fechados (3 evidências) e as divergências, analisados pela LLM local.</div>';
    const historico = decididas.length
      ? `<h4 style="margin:14px 0 6px">Decididas recentemente</h4>${decididas.map((item) => `<div class="dash-row">
          <span><strong>${escapeHtml(VALIDACAO_LABELS[item.status_validacao] || item.status_validacao)}</strong> · ${escapeHtml(item.titulo || '')}</span>
          <span>${escapeHtml(item.validado_por || '')} · ${escapeHtml(item.validado_em ? new Date(item.validado_em).toLocaleString('pt-BR') : '')}</span>
        </div>`).join('')}`
      : '';
    return lista + historico;
  }

  // Validar / corrigir / devolver: grava no SIGp (auditoria) e o SIGp avisa o n8n, que gera o resumo executivo (SIE).
  async function decidir(container, button) {
    const card = button.closest('[data-analise-id]');
    const acao = button.dataset.decisao;
    const status = card.querySelector('[data-role="decisao-status"]');
    const correcaoWrap = card.querySelector('[data-role="correcao-wrap"]');
    if (acao === 'corrigir' && correcaoWrap.hidden) {
      correcaoWrap.hidden = false;
      status.textContent = 'Edite a análise, explique o motivo e clique em Corrigir de novo.';
      card.querySelector('[data-role="correcao"]').focus();
      return;
    }
    const justificativa = card.querySelector('[data-role="justificativa"]').value.trim();
    if (acao !== 'validar' && justificativa.length < 5) {
      status.textContent = 'Explique o motivo (mínimo 5 caracteres).';
      card.querySelector('[data-role="justificativa"]').focus();
      return;
    }
    card.querySelectorAll('[data-decisao]').forEach((b) => { b.disabled = true; });
    status.textContent = 'Gravando a decisão…';
    try {
      const base = (window.SIGP_CONFIG.apiUrl()).replace(/\/$/, '');
      const response = await fetch(`${base}/api/sig/decisoes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          analiseId: card.dataset.analiseId,
          acao,
          justificativa,
          conteudoCorrigido: acao === 'corrigir' ? card.querySelector('[data-role="correcao"]').value.trim() : '',
          usuario: currentUser(),
        }),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok || result.ok === false) throw new Error(result.error || `HTTP ${response.status}`);
      status.textContent = acao === 'devolver'
        ? 'Análise devolvida. Ela não segue para o executivo.'
        : 'Decisão gravada. O n8n vai gerar o resumo executivo para a aba SIE.';
      setTimeout(render, 1200);
    } catch (error) {
      status.textContent = `Não foi possível gravar: ${error.message}`;
      card.querySelectorAll('[data-decisao]').forEach((b) => { b.disabled = false; });
    }
  }

  const ALERT_LABELS = {
    VENCIDO: 'Vencido', VENCE_HOJE: 'Vence hoje', VENCE_EM_BREVE: 'Vence em breve',
    FATURA_AUSENTE: 'Fatura não disponível', AGUARDANDO_FATURA: 'Aguardando fatura', DIVERGENCIA: 'Divergência',
    PAGO: 'Paga', PAGO_COM_ATRASO: 'Paga com atraso',
    FATURA_NAO_RECEBIDA: 'Fatura não chegou', FATURA_NA_CAIXA: 'Fatura na caixa sem associar', LEITURA_GMAIL_PARADA: 'Leitura do Gmail parada',
  };

  function renderAlerts(extras) {
    const items = extras?.alertas || [];
    if (!items.length) return '<div class="dash-empty">Nenhum alerta no momento.</div>';
    const rows = items.slice(0, 15).map((item) => `<div class="dash-row" title="${escapeHtml(item.mensagem)}">
        <span><strong>${escapeHtml(ALERT_LABELS[item.status] || item.status)}</strong> · ${escapeHtml(item.local || '')}${item.provedor ? ` · ${escapeHtml(item.provedor)}` : ''}${item.numero ? ` · NF ${escapeHtml(item.numero)}` : ''}</span>
        <span>${escapeHtml(item.vencimento || '')}</span>
      </div>`).join('');
    const more = items.length > 15 ? `<p class="hint">+ ${items.length - 15} alerta(s). O n8n envia a lista completa diariamente.</p>` : '';
    return rows + more;
  }

  function renderAnalysis(extras) {
    const item = extras?.analise;
    if (!item) return '<div class="dash-empty">Nenhuma análise informativa recente (pendências e aguardando fatura aparecem aqui; ciclos fechados e divergências ficam em "Para decidir").</div>';
    return `<p class="hint">${escapeHtml(new Date(item.created_at).toLocaleString('pt-BR'))}${item.modelo ? ` · ${escapeHtml(item.modelo)}` : ''}</p>
      <div style="white-space:pre-wrap">${escapeHtml(item.conteudo)}</div>`;
  }

  function renderDashboard(data, extras = null) {
    const indicators = data.indicadores;
    const quality = data.qualidade;
    const qualityWarning = quality.gruposChaveDuplicada
      ? `<div class="backup-warn" role="status">${quality.notasAmbiguasExcluidas} registros em ${quality.gruposChaveDuplicada} grupo(s) com chave repetida foram excluídos dos indicadores até revisão.</div>`
      : '';
    return `
      <div class="vg-brand"><h2>SIG · Sistema de Informação Gerencial</h2></div>
      <p class="sub">Indicadores operacionais calculados pela API e pelo banco do SIGp. Os gráficos mostram valores lançados e pagamentos conciliáveis.</p>
      <p class="hint"><a class="note-file" href="${`${location.protocol}//${location.hostname}:5000/`}" target="_blank" rel="noopener">Painel de análises da IA (legado)</a> · histórico das conciliações recebidas do n8n e das análises da IA. Decisões registradas lá não alteram o SIGp; decida aqui.</p>
      <form class="sig-filters" id="sigFilters">
        <div><label for="sigInicio">De</label><input class="f" id="sigInicio" name="inicio" type="date" value="${escapeHtml(data.periodo.inicio)}"></div>
        <div><label for="sigFim">Até</label><input class="f" id="sigFim" name="fim" type="date" value="${escapeHtml(data.periodo.fim)}"></div>
        <div><label for="sigTipoLocal">Tipo de local</label><select class="f" id="sigTipoLocal" name="entidadeTipo">
          <option value="">Todos</option><option value="agencia">Agência</option><option value="rodoviaria">Rodoviária</option><option value="garagem">Garagem</option>
        </select></div>
        <div><label for="sigProvedor">Provedor</label><input class="f" id="sigProvedor" name="provedor" type="search" placeholder="Todos os provedores"></div>
        <div><label for="sigStatus">Conciliação</label><select class="f" id="sigStatus" name="status">
          <option value="">Todos os status</option><option value="MATCH">Conciliadas</option><option value="PENDENTE">Pendentes</option><option value="PAGO_PARCIAL">Pagas parcialmente</option><option value="AGUARDANDO_FATURA">Aguardando fatura</option><option value="DIVERGENCIA">Divergentes</option>
        </select></div>
        <div class="sig-filter-actions"><button class="primary small" type="submit">Aplicar filtros</button><button class="ghost small" id="sigClear" type="button">Limpar</button></div>
      </form>
      <div id="sigError" class="backup-warn" role="alert" hidden></div>
      ${qualityWarning}
      ${quality.notasSemDataEmissao ? `<p class="hint">${quality.notasSemDataEmissao} nota(s) sem data de emissão não entram no recorte de período.</p>` : ''}
      <div class="sig-kpis">
        <article class="dash-card"><h3>Valor lançado</h3><strong>${formatMoney(indicators.valorLancado)}</strong><span>${indicators.notasLancadas} nota(s)</span></article>
        <article class="dash-card"><h3>Valor pago no período</h3><strong>${formatMoney(indicators.valorPago)}</strong><span>${indicators.pagamentos} pagamento(s)</span></article>
        <article class="dash-card"><h3>Saldo pendente</h3><strong>${formatMoney(indicators.valorPendente)}</strong><span>${indicators.pendentes} pendência(s)</span></article>
        <article class="dash-card"><h3>Notas vencidas</h3><strong>${indicators.vencidas}</strong><span>com saldo em aberto</span></article>
        <article class="dash-card"><h3>Conciliações aprovadas</h3><strong>${indicators.conciliadas}</strong><span>status MATCH</span></article>
        <article class="dash-card"><h3>Divergências</h3><strong>${indicators.divergencias}</strong><span>requerem revisão</span></article>
        <article class="dash-card"><h3>Aguardando fatura</h3><strong>${indicators.aguardandoFatura || 0}</strong><span>lançada e paga conferem</span></article>
        <article class="dash-card"><h3>Sem fatura</h3><strong>${indicators.semFatura || 0}</strong><span>fatura ainda não disponível</span></article>
      </div>
      <div class="sig-chart-grid">
        <section class="nfse-card"><h3>Alertas</h3><div class="sig-status-list">${renderAlerts(extras)}</div></section>
        <section class="nfse-card"><h3>Análise gerencial (IA)</h3>${renderAnalysis(extras)}</section>
      </div>
      <section class="nfse-card" id="sigDecisoes"><h3>Para decidir (${(extras?.pendentes || []).length})</h3>
        <p class="hint">Análises da LLM local sobre ciclos fechados e divergências. Valide, corrija ou devolva: o que for validado segue para o executivo (SIE). O status da conciliação é sempre o da regra do sistema.</p>
        ${renderDecisions(extras)}
      </section>
      <div class="sig-chart-grid">
        <section class="nfse-card"><h3>Evolução mensal</h3><div class="sig-legend"><span><i class="sig-legend-launched"></i>Lançado</span><span><i class="sig-legend-paid"></i>Pago</span></div>
          <div class="sig-month-chart" role="img" aria-label="Valores mensais lançados e pagos">${renderMonthly(data.mensal)}</div></section>
        <section class="nfse-card"><h3>Valores por provedor</h3><div class="sig-ranked">${renderBars(data.porProvedor, 'valor')}</div></section>
        <section class="nfse-card"><h3>Valores por local</h3><div class="sig-ranked">${renderBars(data.porLocal, 'valor')}</div></section>
        <section class="nfse-card"><h3>Status de conciliação</h3><div class="sig-status-list">${Object.entries(data.status).map(([status, count]) => `<div class="dash-row"><span>${escapeHtml(status)}</span><strong>${count}</strong></div>`).join('') || '<div class="dash-empty">Sem documentos no período.</div>'}</div></section>
      </div>`;
  }

  function bindFilters(container, initial, activeFilters = {}, extras = null) {
    const form = container.querySelector('#sigFilters');
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const errorBox = container.querySelector('#sigError');
      errorBox.hidden = true;
      const apiUrl = window.SIGP_CONFIG.apiUrl();
      const appliedFilters = Object.fromEntries(new FormData(form).entries());
      try {
        const response = await fetch(`${apiUrl.replace(/\/$/, '')}/api/sig/resumo?${makeQuery(form)}`);
        const result = await response.json();
        if (!response.ok || !result.ok) throw new Error(result.error || `HTTP ${response.status}`);
        container.innerHTML = renderDashboard(result, extras);
        bindFilters(container, result, appliedFilters, extras);
      } catch (error) {
        errorBox.textContent = `Falha ao aplicar filtros: ${error.message || 'erro desconhecido'}.`;
        errorBox.hidden = false;
      }
    });
    form.querySelector('#sigTipoLocal').value = activeFilters.entidadeTipo || '';
    form.querySelector('#sigStatus').value = activeFilters.status || '';
    form.querySelector('#sigProvedor').value = activeFilters.provedor || '';
    form.querySelector('#sigInicio').value = activeFilters.inicio || initial.periodo.inicio;
    form.querySelector('#sigFim').value = activeFilters.fim || initial.periodo.fim;
    form.querySelector('#sigClear').addEventListener('click', () => {
      form.reset();
      form.querySelector('[name="inicio"]').value = initial.periodo.inicio;
      form.querySelector('[name="fim"]').value = initial.periodo.fim;
      form.requestSubmit();
    });
  }

  window.SIGP_SIG = { render };
})();
