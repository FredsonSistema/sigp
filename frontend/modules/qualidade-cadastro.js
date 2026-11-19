// Configurações > Qualidade do cadastro: o que falta ou está inconsistente e as correções com prévia.
// 1) Unificar nomes de provedor  2) Dia de vencimento (com sugestão das faturas)  3) Unidade inválida.
// A API faz backup do banco antes de cada correção e o nome novo é calculado no servidor (backend/correcoes_cadastro.py).
(() => {
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const base = () => window.SIGP_CONFIG.apiUrl();
  const api = async (caminho, corpo) => {
    const r = await fetch(`${base()}${caminho}`, {
      method: corpo === undefined ? 'GET' : 'POST', headers: { 'Content-Type': 'application/json' },
      body: corpo === undefined ? undefined : JSON.stringify(corpo),
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok || j.ok === false) throw new Error(j.error || `A API respondeu HTTP ${r.status}.`);
    return j;
  };
  let box = null;
  let dados = { previa: null, qualidade: null };
  let filtroDias = 'todos';

  const pode = () => !window.SIGP_ACESSO || window.SIGP_ACESSO.perfil === 'administrador'
    || (window.SIGP_ACESSO.permissoes || []).includes('locais.editar');

  // Traz para este navegador o que a API corrigiu (sem gravar de volta), para a próxima edição não desfazer.
  async function atualizarNavegador(itens, desativadas = []) {
    const porLocal = new Map();
    itens.forEach((i) => porLocal.set(i.localId, i));
    const locais = (await api('/api/locais?inativos=1')).items || [];
    for (const l of locais) {
      if (porLocal.has(l.id)) await window.SIGP_API.refreshLocationProviders(l.tipo, l.id, { trocarNome: true });
    }
    for (const d of desativadas) {
      for (const k of ['ti_agencias_v1', 'ti_rodoviarias_v1', 'ti_garagens_v1']) {
        try {
          const lista = JSON.parse(localStorage.getItem(k) || '[]');
          if (Array.isArray(lista) && lista.some((x) => String(x.id) === String(d.localId))) {
            localStorage.setItem(k, JSON.stringify(lista.filter((x) => String(x.id) !== String(d.localId))));
          }
        } catch (e) { /* lista inválida: a API já desativou */ }
      }
    }
  }

  function resumo() {
    const q = dados.qualidade;
    if (!q) return '';
    if (!q.total) return '<div class="hint">✅ Nada a corrigir no cadastro.</div>';
    const itens = Object.entries(q.resumo).sort((a, b) => b[1] - a[1])
      .map(([nome, n]) => `<span class="qc-chip"><b>${n}</b> ${esc(nome.toLowerCase())}</span>`).join('');
    return `<div class="qc-chips" aria-label="Resumo da qualidade">${itens}</div>
      <div class="hint">Total: ${q.total} ponto(s). Os que dá para corrigir aqui estão abaixo; os demais (endereço, responsável) se corrigem no cadastro de cada local.</div>`;
  }

  function blocoUnificar() {
    const grupos = dados.previa.unificar;
    if (!grupos.length) return '<div class="hint">✅ Nenhum provedor com nomes diferentes.</div>';
    return `<div class="hint">O mesmo provedor escrito de jeitos diferentes conta como provedores distintos nas respostas e nos relatórios. O plano (ex.: 200MB+IP) é mantido no nome.</div>
      ${grupos.map((g, gi) => `<fieldset class="qc-grupo"><legend><label><input type="checkbox" data-qc-grupo="${gi}" checked> <b>${esc(g.provedor)}</b></label>
        <span class="hint">variantes: ${g.variantes.map((v) => esc(v.nome)).join(' · ')}</span></legend>
        <ul>${g.itens.map((i) => `<li>${esc(i.unidade)}: <code>${esc(i.de)}</code> → <code>${esc(i.para)}</code></li>`).join('')}</ul></fieldset>`).join('')}
      <div class="task-add-row"><button type="button" class="primary small" data-qc-acao="unificar">Unificar selecionados</button>
        <span class="hint" data-qc-status="unificar" role="status"></span></div>`;
  }

  function blocoDias() {
    const lista = dados.previa.vencimento;
    if (!lista.length) return '<div class="hint">✅ Todos os provedores têm dia de vencimento.</div>';
    const visiveis = filtroDias === 'sugestao' ? lista.filter((v) => v.sugestao) : lista;
    return `<div class="hint">O dia de vencimento alimenta os alertas e o assistente. Sugestão vem das faturas já recebidas para o local; confira antes de salvar. Deixe em branco o que não souber.</div>
      <div class="task-add-row"><label>Mostrar <select class="f" data-qc-filtro>
        <option value="todos"${filtroDias === 'todos' ? ' selected' : ''}>todos (${lista.length})</option>
        <option value="sugestao"${filtroDias === 'sugestao' ? ' selected' : ''}>só com sugestão (${lista.filter((v) => v.sugestao).length})</option></select></label>
        ${lista.some((v) => v.sugestao) ? '<button type="button" class="ghost small" data-qc-acao="usar-sugestoes">Usar todas as sugestões</button>' : ''}</div>
      <div class="pia-table-wrap qc-dias"><table class="pia-table"><thead><tr><th>Unidade</th><th>Provedor</th><th>Dia</th><th>Sugestão</th></tr></thead><tbody>
      ${visiveis.map((v) => `<tr><td>${esc(v.unidade)}</td><td>${esc(v.provedor)}</td>
        <td><label class="sr-only" for="qcDia${esc(v.localId)}${esc(v.provedorId)}">Dia de vencimento de ${esc(v.provedor)} em ${esc(v.unidade)}</label>
          <input class="f qc-dia" type="number" min="1" max="31" inputmode="numeric" id="qcDia${esc(v.localId)}${esc(v.provedorId)}"
            data-local="${esc(v.localId)}" data-provedor="${esc(v.provedorId)}" data-indice="${v.indice}" data-sugestao="${v.sugestao || ''}"></td>
        <td>${v.sugestao ? `<b>dia ${v.sugestao}</b><div class="hint">${esc(v.fonte)}</div>` : '<span class="hint">sem faturas para sugerir</span>'}</td></tr>`).join('')}
      </tbody></table></div>
      <div class="task-add-row"><button type="button" class="primary small" data-qc-acao="dias">Salvar dias preenchidos</button>
        <span class="hint" data-qc-status="dias" role="status"></span></div>`;
  }

  function blocoInvalidas() {
    const lista = dados.previa.unidadesInvalidas;
    if (!lista.length) return '<div class="hint">✅ Nenhuma unidade inválida.</div>';
    return `<div class="hint">Nome que parece cabeçalho de planilha importado por engano. Desativar tira da lista e das contagens; o histórico fica guardado.</div>
      <ul>${lista.map((u) => `<li>${esc(u.unidade)} <span class="hint">(${u.provedores} provedor(es))</span>
        <button type="button" class="ghost small" data-qc-acao="desativar" data-local="${esc(u.localId)}">Desativar</button></li>`).join('')}</ul>
      <span class="hint" data-qc-status="desativar" role="status"></span>`;
  }

  function desenhar() {
    if (!pode()) { box.innerHTML = '<div class="hint">Seu perfil não pode corrigir o cadastro (permissão "Criar e editar locais").</div>'; return; }
    const p = dados.previa;
    box.innerHTML = `${resumo()}
      <details class="nr-disc"${p.unificar.length ? ' open' : ''}><summary>Unificar nomes de provedor <span class="hint">${p.resumo.unificar} cadastro(s)</span></summary><div class="nr-disc-body">${blocoUnificar()}</div></details>
      <details class="nr-disc"><summary>Dia de vencimento <span class="hint">${p.resumo.vencimento} sem dia · ${p.resumo.vencimentoComSugestao} com sugestão</span></summary><div class="nr-disc-body">${blocoDias()}</div></details>
      <details class="nr-disc"${p.unidadesInvalidas.length ? ' open' : ''}><summary>Unidades inválidas <span class="hint">${p.resumo.unidadesInvalidas}</span></summary><div class="nr-disc-body">${blocoInvalidas()}</div></details>`;
  }

  async function carregar() {
    const [previa, qualidade] = await Promise.all([api('/api/cadastro/correcoes'), api('/api/base-conhecimento/qualidade')]);
    dados = { previa, qualidade };
  }

  async function render(alvo) {
    box = typeof alvo === 'string' ? document.getElementById(alvo) : alvo;
    if (!box) return;
    if (!pode()) { desenhar(); return; }
    try { await carregar(); desenhar(); } catch (e) { box.innerHTML = `<div class="hint">Não foi possível ler a qualidade do cadastro: ${esc(e.message)}</div>`; return; }
    if (box.dataset.ligado) return;
    box.dataset.ligado = '1';
    box.addEventListener('change', (ev) => {
      if (ev.target.matches('[data-qc-filtro]')) {
        const abertos = [...box.querySelectorAll('details')].map((d) => d.open);
        filtroDias = ev.target.value; desenhar();
        box.querySelectorAll('details').forEach((d, i) => { d.open = abertos[i]; });
      }
    });
    box.addEventListener('click', async (ev) => {
      const b = ev.target.closest('[data-qc-acao]');
      if (!b) return;
      const acao = b.dataset.qcAcao;
      const status = box.querySelector(`[data-qc-status="${acao === 'usar-sugestoes' ? 'dias' : acao}"]`);
      if (acao === 'usar-sugestoes') {
        box.querySelectorAll('.qc-dia').forEach((i) => { if (i.dataset.sugestao && !i.value) i.value = i.dataset.sugestao; });
        if (status) status.textContent = 'Sugestões preenchidas. Confira e clique em "Salvar dias preenchidos".';
        return;
      }
      try {
        b.disabled = true;
        let r = null;
        if (acao === 'unificar') {
          const itens = [...box.querySelectorAll('[data-qc-grupo]:checked')].flatMap((c) => dados.previa.unificar[Number(c.dataset.qcGrupo)].itens);
          if (!itens.length) { status.textContent = 'Selecione pelo menos um provedor.'; return; }
          if (!window.confirm(`Unificar ${itens.length} cadastro(s) de provedor? O sistema faz backup do banco antes.`)) return;
          r = await api('/api/cadastro/correcoes/unificar', { itens });
          await atualizarNavegador(r.itens);
        } else if (acao === 'dias') {
          const itens = [...box.querySelectorAll('.qc-dia')].filter((i) => i.value).map((i) => ({
            localId: i.dataset.local, provedorId: i.dataset.provedor, indice: Number(i.dataset.indice), dia: Number(i.value) }));
          const ruim = itens.find((i) => !(i.dia >= 1 && i.dia <= 31));
          if (ruim) { status.textContent = 'Use um dia de 1 a 31.'; return; }
          if (!itens.length) { status.textContent = 'Preencha pelo menos um dia.'; return; }
          if (!window.confirm(`Salvar o dia de vencimento de ${itens.length} provedor(es)? O sistema faz backup do banco antes.`)) return;
          r = await api('/api/cadastro/correcoes/vencimento', { itens });
          await atualizarNavegador(r.itens);
        } else if (acao === 'desativar') {
          if (!window.confirm('Desativar esta unidade? Ela sai das listas e das contagens; o histórico fica guardado.')) return;
          r = await api('/api/cadastro/correcoes/desativar', { localId: b.dataset.local });
          await atualizarNavegador([], r.itens);
        }
        await carregar();
        desenhar();
        const texto = `Pronto: ${r.aplicados} alteração(ões). Backup antes: ${r.backup}. Recarregue a página (F5) para ver nas outras abas.`;
        const msg = box.querySelector(`[data-qc-status="${acao}"]`);
        if (msg) msg.textContent = texto;
        window.toast?.(texto, 6000);
      } catch (e) {
        if (status) status.textContent = e.message;
      } finally {
        b.disabled = false;
      }
    });
  }

  window.SIGP_QUALIDADE_CADASTRO = { render };
})();
