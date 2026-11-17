// Configurações > Perfis e permissões. O administrador (chave do .env) cria grupos, usuários e ajustes individuais;
// os demais veem o próprio perfil. A regra vale na API (backend/acesso.py); aqui a tela só esconde as abas sem permissão.
(() => {
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const api = async (caminho, opcoes = {}) => {
    const r = await fetch(`${window.SIGP_CONFIG.apiUrl()}${caminho}`, {
      ...opcoes, headers: { 'Content-Type': 'application/json', ...(opcoes.headers || {}) },
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok || j.ok === false) throw new Error(j.error || `A API respondeu HTTP ${r.status}.`);
    return j;
  };
  const dataHora = (v) => (v ? new Date(v).toLocaleString('pt-BR') : '—');
  let dados = { catalogo: [], grupos: [], usuarios: [], auditoria: [] };
  const abertos = new Set();

  // ---------------------------------------------------------------- perfil ativo na tela
  async function aplicar() {
    let eu;
    try { eu = await api('/api/acesso/eu'); } catch (e) { return null; }
    window.SIGP_ACESSO = eu;
    document.querySelectorAll('.tab[data-view]').forEach((tab) => {
      tab.hidden = Array.isArray(eu.abas) && !eu.abas.includes(tab.dataset.view);
    });
    const ativa = document.querySelector('.tab.active');
    if (ativa && ativa.hidden) document.querySelector('.tab[data-view]:not([hidden])')?.click();
    let chip = document.getElementById('perfilAtivo');
    const barra = document.querySelector('header .tabs');
    if (!chip && barra) {
      chip = document.createElement('span');
      chip.id = 'perfilAtivo';
      chip.className = 'perfil-chip';
      barra.appendChild(chip);
    }
    if (chip) {
      chip.textContent = eu.perfil === 'administrador' ? (eu.usuario ? `${eu.usuario} · Administrador` : 'Administrador') : eu.perfil === 'usuario' ? `${eu.usuario || eu.nome} · ${eu.grupo}` : '';
      chip.hidden = !chip.textContent;
    }
    return eu;
  }

  // ---------------------------------------------------------------- partes da tela
  const nomeFunc = () => Object.fromEntries(dados.catalogo.flatMap((a) => a.funcionalidades.map((f) => [f.id, f])));

  function caixasPermissoes(selecionadas, prefixo) {
    return dados.catalogo.map((a) => `<details class="nr-disc"${abertos.has(`${prefixo}:${a.area}`) ? ' open' : ''} data-abre="${esc(`${prefixo}:${a.area}`)}">
      <summary>${esc(a.area)} <span class="hint">${a.funcionalidades.filter((f) => selecionadas.includes(f.id)).length}/${a.funcionalidades.length}</span></summary>
      <div class="nr-disc-body perm-lista">${a.funcionalidades.map((f) => `<label class="perm-item"><input type="checkbox" data-perm="${esc(f.id)}"${selecionadas.includes(f.id) ? ' checked' : ''}>
        <span>${esc(f.nome)}</span> <code class="hint">${esc(f.id)}</code></label>`).join('')}</div></details>`).join('');
  }

  function ajustesUsuario(u) {
    const grupo = dados.grupos.find((g) => g.id === u.grupoId) || { permissoes: [] };
    return dados.catalogo.map((a) => `<details class="nr-disc"${abertos.has(`aj:${u.id}:${a.area}`) ? ' open' : ''} data-abre="${esc(`aj:${u.id}:${a.area}`)}">
      <summary>${esc(a.area)}</summary>
      <div class="nr-disc-body perm-lista">${a.funcionalidades.map((f) => {
        const herda = grupo.permissoes.includes(f.id);
        const atual = u.ajustes[f.id] === true ? 'permitir' : u.ajustes[f.id] === false ? 'negar' : '';
        const efetiva = u.permissoes.includes(f.id);
        return `<div class="perm-ajuste"><span class="${efetiva ? 'perm-sim' : 'perm-nao'}" aria-label="${efetiva ? 'permitido' : 'negado'}">${efetiva ? '✓' : '✗'}</span>
          <span>${esc(f.nome)}</span>
          <select class="f" data-ajuste="${esc(f.id)}" aria-label="Ajuste de ${esc(f.nome)}">
            <option value=""${atual === '' ? ' selected' : ''}>Herdar do grupo (${herda ? 'permitido' : 'negado'})</option>
            <option value="permitir"${atual === 'permitir' ? ' selected' : ''}>Permitir só para este usuário</option>
            <option value="negar"${atual === 'negar' ? ' selected' : ''}>Negar só para este usuário</option>
          </select></div>`;
      }).join('')}</div></details>`).join('');
  }

  const opcoesGrupo = (sel) => dados.grupos.map((g) => `<option value="${esc(g.id)}"${g.id === sel ? ' selected' : ''}>${esc(g.nome)}</option>`).join('');
  // Perfis de uma pessoa: Administrador (tudo) ou um dos grupos.
  const opcoesPerfil = (sel) => `<option value="admin"${sel === 'admin' ? ' selected' : ''}>Administrador (todas as permissões)</option>${opcoesGrupo(sel)}`;
  const pessoas = () => dados.usuarios.filter((u) => u.tipo === 'pessoa');
  const integracoes = () => dados.usuarios.filter((u) => u.tipo !== 'pessoa');
  function situacao(u) {
    if (!u.ativo) return '<span class="perm-nao">desativado</span>';
    if (u.bloqueadoAte && u.bloqueadoAte > new Date().toISOString()) return '<span class="perm-nao">bloqueado por tentativas</span>';
    if (u.trocarSenha) return '<span class="hint">aguardando a troca da senha temporária</span>';
    return 'ativo';
  }

  function blocoUsuarios() {
    const linhaPessoa = (u) => `<details class="nr-disc perm-usuario" data-usuario="${esc(u.id)}" data-abre="usr:${esc(u.id)}"${abertos.has(`usr:${u.id}`) ? ' open' : ''}>
      <summary><b>${esc(u.nome)}</b> · <code>${esc(u.usuario)}</code> · ${esc(u.grupoNome)} · ${situacao(u)}
        <span class="hint">último acesso ${esc(dataHora(u.ultimoUso))}</span></summary>
      <div class="nr-disc-body">
        <div class="nfse-grid">
          <label>Nome<input class="f" data-campo="nome" maxlength="80" value="${esc(u.nome)}"></label>
          <label>Perfil<select class="f" data-campo="grupoId">${opcoesPerfil(u.grupoId)}</select></label>
          <label class="perm-check"><input type="checkbox" data-campo="ativo"${u.ativo ? ' checked' : ''}> Usuário ativo</label>
        </div>
        ${u.grupoId === 'admin' ? '' : `<details class="nr-disc"><summary>Ajustes individuais (opcional)</summary><div class="nr-disc-body">
          <div class="hint" style="margin:4px 0 8px">Valem só para esta pessoa, por cima do perfil.</div>${ajustesUsuario(u)}</div></details>`}
        <div class="task-add-row" style="margin-top:8px">
          <button class="primary small" type="button" data-acao="salvar-usuario">Salvar</button>
          <button class="ghost small" type="button" data-acao="redefinir-senha">Redefinir senha</button>
          <span class="hint">Gera uma senha temporária; a pessoa troca no próximo acesso.</span>
        </div>
      </div></details>`;
    const linhaIntegracao = (u) => `<details class="nr-disc perm-usuario" data-usuario="${esc(u.id)}" data-abre="usr:${esc(u.id)}"${abertos.has(`usr:${u.id}`) ? ' open' : ''}>
      <summary><b>${esc(u.nome)}</b> · ${esc(u.grupoNome)} · ${u.ativo ? 'ativa' : '<span class="perm-nao">desativada</span>'}
        <span class="hint">chave ${esc(u.chavePrefixo)}… · último uso ${esc(dataHora(u.ultimoUso))}</span></summary>
      <div class="nr-disc-body">
        <div class="nfse-grid">
          <label>Nome<input class="f" data-campo="nome" maxlength="80" value="${esc(u.nome)}"></label>
          <label>Grupo de permissões<select class="f" data-campo="grupoId">${opcoesGrupo(u.grupoId)}</select></label>
          <label class="perm-check"><input type="checkbox" data-campo="ativo"${u.ativo ? ' checked' : ''}> Integração ativa</label>
        </div>
        <details class="nr-disc"><summary>Ajustes individuais (opcional)</summary><div class="nr-disc-body">${ajustesUsuario(u)}</div></details>
        <div class="task-add-row" style="margin-top:8px">
          <button class="primary small" type="button" data-acao="salvar-usuario">Salvar</button>
          <button class="ghost small" type="button" data-acao="nova-chave">Gerar nova chave</button>
          <span class="hint">A chave antiga deixa de valer na hora.</span>
        </div>
      </div></details>`;
    return `${pessoas().map(linhaPessoa).join('') || '<div class="dash-empty">Nenhuma pessoa ainda.</div>'}
      <div class="perm-novo">
        <b>Adicionar usuário</b>
        <div class="nfse-grid">
          <label>Nome<input class="f" id="permNovoNome" maxlength="80" placeholder="ex.: Maciel Lopes"></label>
          <label>Nome de usuário<input class="f" id="permNovoUsuario" maxlength="40" placeholder="ex.: maciel.lopes" autocomplete="off"></label>
          <label>Perfil<select class="f" id="permNovoGrupo">${opcoesPerfil('grp-operador')}</select></label>
        </div>
        <div class="task-add-row" style="margin-top:8px"><button class="primary small" type="button" data-acao="criar-usuario">Adicionar e gerar senha temporária</button>
          <span class="hint">No primeiro acesso a pessoa é obrigada a trocar a senha.</span></div>
      </div>
      <div id="permChaveNova" role="alert"></div>
      <details class="nr-disc" data-abre="sec:integracoes"${abertos.has('sec:integracoes') ? ' open' : ''}><summary>Integrações com chave de API <span class="hint">${integracoes().length} · para outro sistema ou automação; pessoas não usam chave</span></summary>
        <div class="nr-disc-body">
          <div class="perm-fixo"><b>Chave do servidor</b> · administrador · fixa <span class="hint">SIGP_API_KEY do .env: usada pelo n8n e no primeiro acesso; não vai para o navegador</span></div>
          ${integracoes().map(linhaIntegracao).join('')}
          <div class="perm-novo"><b>Nova integração</b>
            <div class="nfse-grid">
              <label>Nome<input class="f" id="permNovaIntNome" maxlength="80" placeholder="ex.: Sistema financeiro"></label>
              <label>Grupo de permissões<select class="f" id="permNovaIntGrupo">${opcoesGrupo('grp-integracao')}</select></label>
            </div>
            <div class="task-add-row" style="margin-top:8px"><button class="ghost small" type="button" data-acao="criar-integracao">Criar integração e gerar chave</button></div>
          </div>
        </div></details>`;
  }

  function blocoGrupos() {
    const linhas = dados.grupos.map((g) => `<details class="nr-disc" data-grupo="${esc(g.id)}" data-abre="grp:${esc(g.id)}"${abertos.has(`grp:${g.id}`) ? ' open' : ''}>
      <summary><b>${esc(g.nome)}</b>${g.padrao ? ' · padrão' : ''} <span class="hint">${g.permissoes.length} permissão(ões) · ${g.usuarios} usuário(s)</span></summary>
      <div class="nr-disc-body">
        <div class="nfse-grid">
          <label>Nome<input class="f" data-campo="nome" maxlength="80" value="${esc(g.nome)}"></label>
          <label class="full">Descrição<input class="f" data-campo="descricao" maxlength="300" value="${esc(g.descricao)}"></label>
        </div>
        ${caixasPermissoes(g.permissoes, `grp:${g.id}`)}
        <div class="task-add-row" style="margin-top:8px">
          <button class="primary small" type="button" data-acao="salvar-grupo">Salvar grupo</button>
          ${g.padrao ? '' : '<button class="ghost small" type="button" data-acao="excluir-grupo">Excluir grupo</button>'}
        </div>
      </div></details>`).join('');
    return `${linhas}
      <div class="perm-novo"><b>Novo grupo</b>
        <div class="nfse-grid">
          <label>Nome<input class="f" id="permGrupoNome" maxlength="80" placeholder="ex.: Financeiro"></label>
          <label>Começar com as permissões de<select class="f" id="permGrupoBase"><option value="">nenhuma</option>${opcoesGrupo('')}</select></label>
        </div>
        <div class="task-add-row" style="margin-top:8px"><button class="primary small" type="button" data-acao="criar-grupo">Criar grupo</button></div>
      </div>`;
  }

  function blocoCatalogo() {
    const cab = dados.grupos.map((g) => `<th>${esc(g.nome)}</th>`).join('');
    return dados.catalogo.map((a) => `<h4 class="pia-sub">${esc(a.area)}</h4>
      <div class="pia-table-wrap"><table class="pia-table perm-tabela"><thead><tr><th>Funcionalidade</th><th>Abas</th><th>Administrador</th>${cab}</tr></thead><tbody>
      ${a.funcionalidades.map((f) => `<tr><td>${esc(f.nome)}<div class="hint"><code>${esc(f.id)}</code> · ${f.rotas.map(esc).join(' · ')}</div></td>
        <td>${esc(f.abas.join(', ') || '—')}</td><td class="perm-sim">✓</td>
        ${dados.grupos.map((g) => (g.permissoes.includes(f.id) ? '<td class="perm-sim">✓</td>' : '<td class="perm-nao">—</td>')).join('')}</tr>`).join('')}
      </tbody></table></div>`).join('');
  }

  function blocoAuditoria() {
    const nomes = nomeFunc();
    if (!dados.auditoria.length) return '<div class="dash-empty">Nada registrado ainda.</div>';
    return `<div class="pia-table-wrap"><table class="pia-table"><thead><tr><th>Quando</th><th>Quem</th><th>Ação</th><th>Funcionalidade</th><th>Resultado</th></tr></thead><tbody>
      ${dados.auditoria.map((i) => `<tr><td>${esc(dataHora(i.em))}</td><td>${esc(i.usuario)}</td><td><code>${esc(i.metodo)} ${esc(i.rota)}</code></td>
        <td>${esc(nomes[i.funcionalidade]?.nome || i.funcionalidade || '—')}</td>
        <td class="${i.resultado === 'permitido' ? 'perm-sim' : 'perm-nao'}">${esc(i.resultado)} (${i.status})</td></tr>`).join('')}
      </tbody></table></div>`;
  }

  // ---------------------------------------------------------------- desenho e ações
  async function render(alvo) {
    const box = typeof alvo === 'string' ? document.getElementById(alvo) : alvo;
    if (!box) return;
    const eu = await aplicar();
    if (!box.dataset.trocaLigada) {
      box.dataset.trocaLigada = '1';
      box.addEventListener('click', (ev) => {
        if (ev.target.closest('[data-trocar-senha]')) window.SIGP_LOGIN?.trocarSenha();
      });
    }
    if (!eu || eu.perfil !== 'administrador') {
      let catalogo = [];
      try { catalogo = (await api('/api/acesso/catalogo')).areas; } catch (e) { catalogo = []; }
      const minhas = new Set(eu?.permissoes || []);
      box.innerHTML = `<div class="hint">Você entrou como <b>${esc(eu?.nome || 'visitante')}</b>${eu?.usuario ? ` (<code>${esc(eu.usuario)}</code>)` : ''}${eu?.grupo ? `, perfil ${esc(eu.grupo)}` : ''}. Só o administrador altera perfis e permissões.
          <button class="ghost small" type="button" data-trocar-senha>Trocar minha senha</button></div>
        ${catalogo.length ? catalogo.map((a) => `<details class="nr-disc"><summary>${esc(a.area)}</summary><div class="nr-disc-body perm-lista">
          ${a.funcionalidades.map((f) => `<div><span class="${minhas.has(f.id) ? 'perm-sim' : 'perm-nao'}">${minhas.has(f.id) ? '✓' : '✗'}</span> ${esc(f.nome)}</div>`).join('')}</div></details>`).join('')
          : '<div class="hint">Peça ao administrador a lista das suas permissões.</div>'}`;
      return;
    }
    try {
      const [catalogo, grupos, usuarios, auditoria] = await Promise.all([
        api('/api/acesso/catalogo'), api('/api/acesso/grupos'), api('/api/acesso/usuarios'), api('/api/acesso/auditoria?limite=60'),
      ]);
      dados = { catalogo: catalogo.areas, grupos: grupos.items, usuarios: usuarios.items, auditoria: auditoria.items };
    } catch (erro) {
      box.innerHTML = `<div class="backup-warn" role="alert">Não foi possível carregar perfis e permissões: ${esc(erro.message)}</div>`;
      return;
    }
    const aberto = (k, padrao) => (abertos.has(k) || (padrao && !abertos.has(`-${k}`)) ? ' open' : '');
    box.innerHTML = `
      <details class="nr-list cfg-grupo" data-abre="sec:usuarios"${aberto('sec:usuarios', true)}><summary><span class="nr-list-title">Usuários</span><span class="nr-count">${pessoas().length}</span><span class="hint">quem entra no sistema: nome de usuário, perfil e senha</span></summary><div class="cfg-corpo">${blocoUsuarios()}</div></details>
      <details class="nr-list cfg-grupo" data-abre="sec:grupos"${aberto('sec:grupos')}><summary><span class="nr-list-title">Grupos de permissão</span><span class="nr-count">${dados.grupos.length}</span><span class="hint">conjuntos de permissões; crie ou ajuste</span></summary><div class="cfg-corpo">${blocoGrupos()}</div></details>
      <details class="nr-list cfg-grupo" data-abre="sec:catalogo"${aberto('sec:catalogo')}><summary><span class="nr-list-title">Funcionalidades do sistema</span><span class="nr-count">${dados.catalogo.reduce((n, a) => n + a.funcionalidades.length, 0)}</span><span class="hint">tudo o que pode ser liberado, e quem tem</span></summary><div class="cfg-corpo">${blocoCatalogo()}</div></details>
      <details class="nr-list cfg-grupo" data-abre="sec:auditoria"${aberto('sec:auditoria')}><summary><span class="nr-list-title">Auditoria de acesso</span><span class="hint">últimas gravações e recusas</span></summary><div class="cfg-corpo">${blocoAuditoria()}</div></details>
      <div class="task-add-row"><button class="ghost small" type="button" data-trocar-senha>Trocar minha senha</button>
        <span class="hint" data-perm-status role="status" aria-live="polite"></span></div>`;
    ligar(box);
  }

  const status = (box, texto) => { const s = box.querySelector('[data-perm-status]'); if (s) s.textContent = texto; };

  function mostrarChave(box, nome, chave) {
    const alvo = box.querySelector('#permChaveNova');
    alvo.innerHTML = `<div class="perm-chave"><b>Chave de ${esc(nome)}</b> (aparece só agora; o sistema guarda apenas um resumo dela):
      <code data-chave>${esc(chave)}</code> <button class="ghost small" type="button" data-acao="copiar-chave">Copiar</button>
      <div class="hint">Configure no outro sistema (cabeçalho X-API-Key). Não use em navegador.</div></div>`;
  }
  function mostrarSenha(box, u, senha) {
    const alvo = box.querySelector('#permChaveNova');
    alvo.innerHTML = `<div class="perm-chave"><b>Acesso de ${esc(u.nome)}</b> (a senha aparece só agora):
      usuário <code>${esc(u.usuario)}</code> · senha temporária <code data-chave>${esc(senha)}</code>
      <button class="ghost small" type="button" data-acao="copiar-chave">Copiar senha</button>
      <div class="hint">Entregue à pessoa por um canal seguro. No primeiro acesso ela é obrigada a trocar a senha.</div></div>`;
  }

  function ligar(box) {
    if (box.dataset.ligado) return;
    box.dataset.ligado = '1';
    box.addEventListener('toggle', (ev) => {
      const k = ev.target.dataset?.abre;
      if (!k) return;
      if (ev.target.open) { abertos.add(k); abertos.delete(`-${k}`); } else { abertos.delete(k); abertos.add(`-${k}`); }
    }, true);
    box.addEventListener('click', async (ev) => {
      const botao = ev.target.closest('[data-acao]');
      if (!botao) return;
      const acao = botao.dataset.acao;
      try {
        if (acao === 'copiar-chave') {
          await navigator.clipboard.writeText(box.querySelector('[data-chave]').textContent);
          status(box, 'Copiado.');
          return;
        }
        botao.disabled = true;
        if (acao === 'criar-usuario') {
          const r = await api('/api/acesso/usuarios', { method: 'POST', body: JSON.stringify({
            tipo: 'pessoa', nome: box.querySelector('#permNovoNome').value.trim(),
            usuario: box.querySelector('#permNovoUsuario').value.trim(), grupoId: box.querySelector('#permNovoGrupo').value }) });
          await render(box);
          mostrarSenha(box, r.item, r.senhaTemporaria);
          status(box, `Usuário ${r.item.usuario} adicionado.`);
          return;
        }
        if (acao === 'criar-integracao') {
          const r = await api('/api/acesso/usuarios', { method: 'POST', body: JSON.stringify({
            tipo: 'integracao', nome: box.querySelector('#permNovaIntNome').value.trim(), grupoId: box.querySelector('#permNovaIntGrupo').value }) });
          abertos.add('sec:integracoes');
          await render(box);
          mostrarChave(box, r.item.nome, r.chave);
          status(box, `Integração ${r.item.nome} criada.`);
          return;
        }
        if (acao === 'redefinir-senha') {
          const id = botao.closest('[data-usuario]').dataset.usuario;
          if (!window.confirm('Gerar uma senha temporária? A senha atual deixa de valer e as sessões abertas desta pessoa são encerradas.')) return;
          const r = await api(`/api/acesso/usuarios/${encodeURIComponent(id)}/redefinir-senha`, { method: 'POST' });
          await render(box);
          mostrarSenha(box, r.item, r.senhaTemporaria);
          return;
        }
        if (acao === 'salvar-usuario' || acao === 'nova-chave') {
          const el = botao.closest('[data-usuario]');
          const id = el.dataset.usuario;
          if (acao === 'nova-chave') {
            if (!window.confirm('Gerar uma nova chave? A chave atual deixa de funcionar na hora.')) return;
            const r = await api(`/api/acesso/usuarios/${encodeURIComponent(id)}/nova-chave`, { method: 'POST' });
            await render(box);
            mostrarChave(box, r.item.nome, r.chave);
            return;
          }
          const ajustes = {};
          el.querySelectorAll('[data-ajuste]').forEach((s) => { if (s.value) ajustes[s.dataset.ajuste] = s.value === 'permitir'; });
          await api(`/api/acesso/usuarios/${encodeURIComponent(id)}`, { method: 'PUT', body: JSON.stringify({
            nome: el.querySelector('[data-campo="nome"]').value, grupoId: el.querySelector('[data-campo="grupoId"]').value,
            ativo: el.querySelector('[data-campo="ativo"]').checked, ajustes }) });
          await render(box);
          status(box, 'Usuário salvo. As permissões valem a partir da próxima ação dele.');
          return;
        }
        if (acao === 'salvar-grupo' || acao === 'excluir-grupo') {
          const el = botao.closest('[data-grupo]');
          const id = el.dataset.grupo;
          if (acao === 'excluir-grupo') {
            if (!window.confirm('Excluir este grupo?')) return;
            await api(`/api/acesso/grupos/${encodeURIComponent(id)}`, { method: 'DELETE' });
          } else {
            const permissoes = [...el.querySelectorAll('[data-perm]:checked')].map((c) => c.dataset.perm);
            await api(`/api/acesso/grupos/${encodeURIComponent(id)}`, { method: 'PUT', body: JSON.stringify({
              nome: el.querySelector('[data-campo="nome"]').value, descricao: el.querySelector('[data-campo="descricao"]').value, permissoes }) });
          }
          await render(box);
          status(box, acao === 'excluir-grupo' ? 'Grupo excluído.' : 'Grupo salvo. Vale na hora para todos os usuários dele.');
          return;
        }
        if (acao === 'criar-grupo') {
          const base = dados.grupos.find((g) => g.id === box.querySelector('#permGrupoBase').value);
          await api('/api/acesso/grupos', { method: 'POST', body: JSON.stringify({
            nome: box.querySelector('#permGrupoNome').value, descricao: base ? `Baseado em ${base.nome}` : '', permissoes: base ? base.permissoes : [] }) });
          abertos.add('sec:grupos');
          await render(box);
          status(box, 'Grupo criado. Abra-o para escolher as permissões.');
        }
      } catch (erro) {
        status(box, erro.message);
      } finally {
        botao.disabled = false;
      }
    });
  }

  window.SIGP_PERMISSOES = { render, aplicar };
})();
