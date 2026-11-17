// Aba "Assistente": conversa com a IA local sobre locais, provedores, contas, vencimentos, endereços e contatos.
// A API (backend/assistente.py) entende a pergunta, consulta só o que o perfil permite e devolve a resposta escrita
// a partir dos dados do sistema; relatórios vêm em PDF e CSV. 👍 ensina o assistente; "Ensinar um termo" cria vocabulário.
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
  const SUGESTOES = ['Quantas agências estão em atraso?', 'Quais contas vencem nos próximos dias?', 'Qual o endereço da agência de Itacaré?',
    'Qual o valor da conta de Itacaré?', 'Crie um relatório com a lista de agências', 'Gere um relatório das contas vencidas'];
  let conversa = [];
  let ligado = false;

  function balao(m) {
    if (m.autor === 'voce') return `<div class="ass-msg ass-voce"><div class="ass-texto">${esc(m.texto)}</div></div>`;
    if (m.pensando) return '<div class="ass-msg ass-ia" aria-busy="true"><div class="ass-texto ass-pensando">Pensando… (a IA local roda no computador; pode levar alguns segundos)</div></div>';
    const arquivos = (m.arquivos || []).map((a) => `<a class="ghost small" href="${esc(base() + a.url)}" ${a.formato === 'csv' ? `download="${esc(a.nome)}"` : 'target="_blank" rel="noopener"'}>⬇ ${a.formato === 'pdf' ? 'PDF' : 'Excel (CSV)'}</a>`).join(' ');
    const fonte = m.origem ? `<span class="hint">${m.origem === 'regra' ? 'entendido por regra' : m.origem === 'ia local' ? 'entendido pela IA local' : esc(m.origem)}${m.duracaoMs ? ` · ${(m.duracaoMs / 1000).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} s` : ''}</span>` : '';
    const avaliar = m.id && m.ferramenta ? `<span class="ass-avaliar" data-id="${esc(m.id)}">
        ${m.avaliado ? `<span class="hint">${m.avaliado === 'sim' ? 'Obrigado! Vou lembrar desse jeito de perguntar.' : 'Anotado para revisão.'}</span>`
          : '<button type="button" class="ghost small" data-util="1" aria-label="Resposta certa">👍</button><button type="button" class="ghost small" data-util="0" aria-label="Resposta errada">👎</button>'}</span>` : '';
    return `<div class="ass-msg ass-ia"><div class="ass-texto">${esc(m.texto).replace(/\n/g, '<br>')}</div>
      ${arquivos ? `<div class="task-add-row" style="margin-top:6px">${arquivos}</div>` : ''}
      <div class="ass-rodape">${fonte} ${avaliar}</div></div>`;
  }

  function desenhar() {
    const lista = document.getElementById('assConversa');
    if (!lista) return;
    lista.innerHTML = conversa.length ? conversa.map(balao).join('')
      : `<div class="hint" style="padding:8px">Pergunte em português, do seu jeito. Eu consulto os dados do sistema (com as permissões do seu perfil) e respondo; relatórios saem em PDF e Excel.</div>`;
    lista.scrollTop = lista.scrollHeight;
  }

  async function perguntar(texto) {
    const pergunta = String(texto || '').trim();
    if (!pergunta) return;
    conversa.push({ autor: 'voce', texto: pergunta }, { autor: 'ia', pensando: true });
    desenhar();
    const campo = document.getElementById('assPergunta');
    const botao = document.getElementById('assEnviar');
    campo.value = '';
    botao.disabled = true;
    try {
      const r = await api('/api/assistente/perguntar', { pergunta });
      conversa[conversa.length - 1] = { autor: 'ia', texto: r.resposta, arquivos: r.arquivos, origem: r.origem, id: r.id, ferramenta: r.ferramenta, duracaoMs: r.duracaoMs };
    } catch (e) {
      conversa[conversa.length - 1] = { autor: 'ia', texto: `Não consegui responder: ${e.message}` };
    } finally {
      botao.disabled = false;
      desenhar();
      campo.focus();
    }
  }

  function render() {
    const box = document.getElementById('view_assistente');
    if (!box) return;
    if (!ligado) {
      ligado = true;
      const podeEnsinar = !window.SIGP_ACESSO || window.SIGP_ACESSO.perfil === 'administrador' || (window.SIGP_ACESSO.permissoes || []).includes('assistente.ensinar');
      box.innerHTML = `
        <div class="vg-brand"><h2>Assistente</h2></div>
        <p class="sub">IA local (nada sai da rede). Os números vêm sempre do sistema; a IA só entende a pergunta. Clique em 👍 quando a resposta estiver certa: o assistente aprende esse jeito de perguntar.</p>
        <div class="ass-sugestoes" aria-label="Sugestões">${SUGESTOES.map((s) => `<button type="button" class="ghost small" data-sugestao="${esc(s)}">${esc(s)}</button>`).join('')}</div>
        <div id="assConversa" class="ass-conversa" role="log" aria-live="polite"></div>
        <form id="assForm" class="ass-form">
          <label for="assPergunta" class="sr-only">Pergunta</label>
          <input class="f" id="assPergunta" maxlength="500" autocomplete="off" placeholder="Ex.: quantas agências estão em atraso?">
          <button class="primary" type="submit" id="assEnviar">Perguntar</button>
        </form>
        ${podeEnsinar ? `<details class="nr-disc" style="margin-top:12px"><summary>Ensinar um termo ao assistente</summary><div class="nr-disc-body">
          <div class="hint">Ex.: "matriz" significa "Agência ITABUNA CENTRO"; "em débito" significa "vencida"; "terminal" significa "rodoviaria".</div>
          <form id="assTermoForm" class="nfse-grid" style="margin-top:6px">
            <label>Quando alguém disser<input class="f" id="assTermo" maxlength="60" required></label>
            <label>Quer dizer<input class="f" id="assSignifica" maxlength="80" required></label>
            <div class="task-add-row"><button class="ghost small" type="submit">Ensinar</button><span class="hint" id="assTermoStatus" role="status"></span></div>
          </form></div></details>` : ''}`;
      box.addEventListener('click', async (ev) => {
        const sug = ev.target.closest('[data-sugestao]');
        if (sug) { perguntar(sug.dataset.sugestao); return; }
        const util = ev.target.closest('[data-util]');
        if (util) {
          const id = util.closest('[data-id]').dataset.id;
          const m = conversa.find((x) => x.id === id);
          const sim = util.dataset.util === '1';
          let comentario = '';
          if (!sim) comentario = window.prompt('O que você esperava? (ajuda a melhorar o assistente)') || '';
          try { await api('/api/assistente/avaliar', { id, util: sim, comentario }); if (m) m.avaliado = sim ? 'sim' : 'nao'; } catch (e) { window.toast?.(e.message); }
          desenhar();
        }
      });
      box.querySelector('#assForm').addEventListener('submit', (ev) => { ev.preventDefault(); perguntar(box.querySelector('#assPergunta').value); });
      box.querySelector('#assTermoForm')?.addEventListener('submit', async (ev) => {
        ev.preventDefault();
        const status = box.querySelector('#assTermoStatus');
        try {
          const r = await api('/api/assistente/termos', { termo: box.querySelector('#assTermo').value, significa: box.querySelector('#assSignifica').value });
          status.textContent = `Aprendido: "${r.item.termo}" = "${r.item.significa}".`;
          ev.target.reset();
        } catch (e) { status.textContent = e.message; }
      });
    }
    desenhar();
    setTimeout(() => document.getElementById('assPergunta')?.focus(), 0);
  }

  window.SIGP_ASSISTENTE = { render, perguntar };
})();
