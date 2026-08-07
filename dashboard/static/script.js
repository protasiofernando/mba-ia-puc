// FGV Intelligence Center - Frontend Script
// ─────────────────────────────────────────

// ─── Ripple Effect ────────────────────────────────────────
document.addEventListener('click', function(e) {
  var btn = e.target.closest('.btn-primary');
  if (!btn) return;
  var r = document.createElement('span');
  r.className = 'ripple';
  var rect = btn.getBoundingClientRect();
  var size = Math.max(rect.width, rect.height);
  r.style.cssText = 'width:'+size+'px;height:'+size+'px;left:'+(e.clientX-rect.left-size/2)+'px;top:'+(e.clientY-rect.top-size/2)+'px;';
  btn.appendChild(r);
  setTimeout(function() { r.remove(); }, 600);
});

// ─── Utils ────────────────────────────────────────────────
function switchTab(name, btn) {
  document.querySelectorAll('.tab-content').forEach(function(t) { t.classList.remove('active'); });
  document.querySelectorAll('.nav-btn').forEach(function(b) { b.classList.remove('active'); });
  var el = document.getElementById(name);
  if (el) el.classList.add('active');
  if (btn) btn.classList.add('active');
  if (name === 'categorias')      loadResumoExecutivo();
  if (name === 'simulacao')     { atualizarModoSim(); loadPortalPreview(); }
  if (name === 'historico') {
    loadHistorico(1);
    loadGruposNaturais();
  }
}

function esc(t) {
  if (!t) return '';
  var d = document.createElement('div');
  d.textContent = String(t);
  return d.innerHTML;
}

function txt(id, v) {
  var e = document.getElementById(id);
  if (e) e.textContent = (v != null) ? v : '-';
}

function trunc(s, n) {
  return s && s.length > n ? s.substring(0, n) + '…' : (s || '');
}

function fmtNome(username) {
  if (!username) return '';
  return username
    .replace(/\./g, ' ')
    .replace(/\b\w/g, function(c) { return c.toUpperCase(); });
}

function fmtSolicitante(s) {
  var nome = fmtNome(s.nome);
  return s.dpto ? nome + ' (' + s.dpto + ')' : nome;
}

// Animated counter
function animateCount(el, target, suffix) {
  suffix = suffix || '';
  var start = 0;
  var duration = 900;
  var startTime = null;
  var isNum = !isNaN(parseFloat(target));
  if (!isNum) { el.textContent = target; return; }
  var end = parseFloat(target);
  function step(ts) {
    if (!startTime) startTime = ts;
    var progress = Math.min((ts - startTime) / duration, 1);
    var ease = 1 - Math.pow(1 - progress, 3);
    var cur = Math.round(end * ease);
    el.textContent = cur.toLocaleString('pt-BR') + suffix;
    if (progress < 1) requestAnimationFrame(step);
    else el.textContent = (Number.isInteger(end) ? end.toLocaleString('pt-BR') : end) + suffix;
  }
  requestAnimationFrame(step);
}

// ─── Dashboard ────────────────────────────────────────────
var _charts = {};

function initFiltroMes() {
  fetch('/api/meses')
    .then(function(r) { return r.json(); })
    .then(function(meses) {
      var sel = document.getElementById('filtroMes');
      if (!sel) return;
      meses.forEach(function(m) {
        var opt = document.createElement('option');
        opt.value = m;
        opt.textContent = m;
        sel.appendChild(opt);
      });
    });
}

function loadDash() {
  var sel = document.getElementById('filtroMes');
  var mes = sel ? sel.value : '';
  var url = '/api/dashboard' + (mes ? '?mes=' + mes : '');

  fetch(url)
    .then(function(r) { return r.json(); })
    .then(function(d) {
      // KPI row 1
      animateCount(document.getElementById('dbChamados'),   d.total_chamados);
      animateCount(document.getElementById('dbCategorias'), d.total_categorias);

      var ia = d.ia_resumo;
      if (ia) {
        animateCount(document.getElementById('dbNovasCats'), ia.categorias_recomendadas);
      }

      // KPI row 2 - operacional
      txt('dbTaxaResolucao',  d.taxa_resolucao);
      animateCount(document.getElementById('dbBacklog'),     d.backlog);
      animateCount(document.getElementById('dbFinalizados'), d.finalizados);

      // Distribuição por classificação sugerida
      _renderBar('chartCategorias',
        d.distribuicao_categorias.map(function(c) { return trunc(c.nome, 28); }),
        d.distribuicao_categorias.map(function(c) { return c.total; }),
        'Chamados', 'rgba(12,99,170,0.8)');

      // Tempo médio
      _renderBar('chartTempos',
        d.tempo_por_categoria.map(function(c) { return trunc(c.nome, 28); }),
        d.tempo_por_categoria.map(function(c) { return c.tempo; }),
        'Horas', 'rgba(12,99,170,0.8)');

      // Tendência mensal
      _renderBar('chartTendencia',
        d.tendencia_mensal.map(function(t) { return t.mes; }),
        d.tendencia_mensal.map(function(t) { return t.total; }),
        'Chamados', 'rgba(12,99,170,0.8)');

      // Top analistas
      _renderBarH('chartAnalistas',
        d.top_analistas.map(function(a) { return trunc(fmtNome(a.nome), 30); }),
        d.top_analistas.map(function(a) { return a.total; }),
        'Chamados', 'rgba(12,99,170,0.8)');

      // Top solicitantes
      _renderBarH('chartSolicitantes',
        d.top_solicitantes.map(function(a) { return trunc(fmtSolicitante(a), 38); }),
        d.top_solicitantes.map(function(a) { return a.total; }),
        'Chamados', 'rgba(12,99,170,0.8)');

      // Por departamento
      _renderBar('chartDepartamentos',
        d.por_departamento.map(function(a) { return trunc(a.nome, 22); }),
        d.por_departamento.map(function(a) { return a.total; }),
        'Chamados', 'rgba(12,99,170,0.8)');

      // Situações
      _renderDoughnut('chartSituacoes',
        d.distribuicao_situacoes.map(function(s) { return s.nome; }),
        d.distribuicao_situacoes.map(function(s) { return s.total; }));
    });
}

function _renderBar(id, labels, data, label, color) {
  var ctx = document.getElementById(id);
  if (!ctx) return;
  if (_charts[id]) _charts[id].destroy();
  _charts[id] = new Chart(ctx, {
    type: 'bar',
    data: { labels: labels, datasets: [{ label: label, data: data, backgroundColor: color, borderRadius: 5, borderSkipped: false }] },
    options: {
      responsive: true,
      animation: { duration: 800, easing: 'easeOutQuart' },
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#6b82a0', font: { size: 12, family: "'Inter', sans-serif" } }, grid: { color: 'rgba(0,58,121,.05)' } },
        y: { ticks: { color: '#6b82a0', font: { size: 12 } }, grid: { color: 'rgba(0,58,121,.06)' } }
      }
    }
  });
}

function _renderBarH(id, labels, data, label, color) {
  var ctx = document.getElementById(id);
  if (!ctx) return;
  if (_charts[id]) _charts[id].destroy();
  _charts[id] = new Chart(ctx, {
    type: 'bar',
    data: { labels: labels, datasets: [{ label: label, data: data, backgroundColor: color, borderRadius: 4, borderSkipped: false }] },
    options: {
      indexAxis: 'y',
      responsive: true,
      animation: { duration: 800 },
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#6b82a0', font: { size: 12 } }, grid: { color: 'rgba(0,58,121,.05)' }, beginAtZero: true },
        y: { ticks: { color: '#6b82a0', font: { size: 12 } }, grid: { display: false } }
      }
    }
  });
}

function _renderDoughnut(id, labels, data) {
  var ctx = document.getElementById(id);
  if (!ctx) return;
  if (_charts[id]) _charts[id].destroy();
  var colors = ['rgba(0,139,201,.85)','rgba(0,58,121,.85)','rgba(59,174,150,.85)',
                'rgba(253,219,81,.9)','rgba(155,10,81,.85)','rgba(156,100,162,.85)'];
  _charts[id] = new Chart(ctx, {
    type: 'doughnut',
    data: { labels: labels, datasets: [{ data: data, backgroundColor: colors, borderWidth: 2, borderColor: '#ffffff' }] },
    options: {
      responsive: true,
      animation: { animateRotate: true, duration: 900 },
      plugins: { legend: { position: 'right', labels: { color: '#1e3a6b', font: { size: 12, family: "'Inter', sans-serif" }, padding: 14 } } }
    }
  });
}

// ─── Classificação Sugerida ───────────────────────────────
function loadCategorias() {
  fetch('/api/mapeamento-detalhado')
    .then(function(r) { return r.json(); })
    .then(renderTabelaCategorias);
}

function renderTabelaCategorias(rows) {
  var tbody = document.getElementById('catBody');
  if (!tbody) return;
  if (!rows || !rows.length) {
    tbody.innerHTML = '<tr><td colspan="3" style="text-align:center;color:var(--text-muted);padding:1.2rem;">Mapeamento não disponível.</td></tr>';
    return;
  }

  var grupos = {};
  rows.forEach(function(r) {
    var nova = r.nova_categoria || 'A definir';
    if (!grupos[nova]) {
      grupos[nova] = {
        nome: nova,
        grupo: r.grupo_novo || '',
        total: 0,
        linhas: []
      };
    }
    if (!grupos[nova].grupo && r.grupo_novo) grupos[nova].grupo = r.grupo_novo;
    grupos[nova].total += r.chamados || 0;
    grupos[nova].linhas.push(r);
  });

  var html = '';
  Object.keys(grupos)
    .map(function(k) { return grupos[k]; })
    .sort(function(a, b) { return b.total - a.total || a.nome.localeCompare(b.nome); })
    .forEach(function(grupo) {
    var linhas = grupo.linhas.sort(function(a, b) {
      return (b.chamados || 0) - (a.chamados || 0) || (a.categoria_atual || '').localeCompare(b.categoria_atual || '');
    });
    var span = linhas.length;

    linhas.forEach(function(r, idx) {
      html += '<tr>';
      if (idx === 0) {
        var tdStyle = 'vertical-align:middle;' + (span > 1 ? 'border-bottom:2px solid var(--fgv-blue);' : '');
        html += '<td rowspan="'+span+'" style="'+tdStyle+'min-width:260px;">' +
          (grupo.grupo ? '<div style="font-size:.7rem;text-transform:uppercase;letter-spacing:.04em;color:var(--text-muted);font-weight:700;margin-bottom:.2rem;">' + esc(grupo.grupo) + '</div>' : '') +
          '<div style="font-weight:600;color:var(--fgv-navy);">' + esc(grupo.nome) + '</div>' +
          '<div style="font-size:.74rem;color:var(--text-muted);margin-top:.2rem;">' + span + ' tipos de chamado atuais · ' + grupo.total + ' chamados</div>' +
          '</td>';
      }
      html += '<td style="font-size:.82rem;color:var(--text-secondary);">' + esc(r.categoria_atual) + '</td>';
      html += '<td style="text-align:center;font-family:var(--font-mono);color:var(--fgv-navy);">' + r.chamados + '</td>';
      html += '</tr>';
    });
  });
  tbody.innerHTML = html;
}

// ─── Prévia do Portal ───────────────────────────────────────
function _setBadge(el, disponivel) {
  if (!el) return;
  el.textContent  = disponivel ? 'disponível' : 'indisponível';
  el.style.background = disponivel ? 'rgba(59,174,150,.15)' : 'rgba(155,10,81,.12)';
  el.style.color      = disponivel ? '#3bae96' : '#9b0a51';
}

function atualizarModoSim() {
  // Verifica o status do motor de simulação (Azure OpenAI) ao abrir a aba
  fetch('/api/openai-status').then(function(r) { return r.json(); }).then(function(d) {
    var dot = document.getElementById('openaiStatusDot');
    var txt = document.getElementById('openaiStatusText');
    if (dot) dot.className = 'pp-dot' + (d.disponivel ? '' : ' off');
    if (txt) txt.textContent = d.disponivel
      ? 'Respostas geradas por IA com base no catálogo'
      : 'Assistente de IA indisponível no momento';
    if (d.modelo) window._openaiModelo = d.modelo;
  });
}

function limparSimulacao() {
  document.getElementById('simDescricao').value = '';
  var r = document.getElementById('simResultado');
  if (r) r.innerHTML = '';
}

function executarSimulacao() {
  var descricao = document.getElementById('simDescricao').value.trim();
  var resEl     = document.getElementById('simResultado');
  if (!descricao) { alert('Descreva o chamado antes de classificar.'); return; }

  var openaiModelo = window._openaiModelo || 'OpenAI';

  resEl.innerHTML =
    '<div class="sim-loading">' +
    '<div class="sim-dots"><span></span><span></span><span></span></div>' +
    '<p>Consultando Azure OpenAI (' + openaiModelo + ')…</p>' +
    '</div>';

  var endpoint = '/api/simular-openai';

  fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ descricao: descricao })
  })
  .then(function(r) { return r.json(); })
  .then(function(d) {
    if (d.erro) {
      resEl.innerHTML = '<div class="empty-state"><p style="color:var(--rose);">'+esc(d.erro)+'</p></div>';
      return;
    }

    var confTexto = d.confianca || '';
    var grupoTexto = d.grupo || d.grupo_novo || '';
    var conf  = confTexto === 'alta' ? 90 : confTexto === 'media' ? 60 : confTexto === 'baixa' ? 30 : 50;
    var cor   = conf >= 65 ? 'var(--fgv-turquesa)' : conf >= 35 ? 'var(--fgv-blue)' : 'var(--fgv-vinho)';
    var bgCor = conf >= 65 ? 'rgba(59,174,150,.1)'  : conf >= 35 ? 'rgba(0,139,201,.1)'  : 'rgba(155,10,81,.1)';
    var bdCor = conf >= 65 ? 'rgba(59,174,150,.35)' : conf >= 35 ? 'rgba(0,139,201,.35)' : 'rgba(155,10,81,.35)';

    var modoLabel = 'AZURE OPENAI · ' + (window._openaiModelo || 'OpenAI');

    var infosHtml = (d.informacoes_necessarias || []).map(function(info, i) {
      return '<li class="sim-field" style="animation-delay:' + (i * 0.07) + 's">' +
        '<span class="sim-check">' +
        '<svg class="check-icon" viewBox="0 0 12 10"><polyline points="1 5 4.5 8.5 11 1"/></svg>' +
        '</span>' + esc(info) + '</li>';
    }).join('');

    var textoSugeridoHtml = '';
    if (d.texto_sugerido) {
      var tEsc = esc(d.texto_sugerido).replace(/\b([A-Z][A-Z0-9_]{2,})\b/g,
        '<span style="background:rgba(0,139,201,.13);color:var(--fgv-blue);padding:.05rem .3rem;border-radius:3px;font-weight:700;font-size:.79rem;font-style:normal;">$1</span>');
      textoSugeridoHtml =
        '<div style="margin-bottom:.8rem;">' +
        '<div style="font-size:.63rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--text-muted);margin-bottom:.3rem;">Texto sugerido do chamado</div>' +
        '<div style="background:rgba(0,58,121,.03);border:1px solid var(--border);border-left:3px solid var(--fgv-blue);border-radius:0 6px 6px 0;padding:.65rem .85rem;font-size:.82rem;color:var(--fgv-navy);line-height:1.75;">' +
        tEsc +
        '</div>' +
        '</div>';
    }

    resEl.innerHTML =
      '<div class="sim-result">' +

      '<div style="font-size:.7rem;font-weight:700;color:var(--fgv-blue);letter-spacing:.06em;margin-bottom:.6rem;">' + modoLabel + '</div>' +

      '<div class="sim-cat-header">' +
      '<div>' +
      (grupoTexto ? '<div style="font-size:.68rem;text-transform:uppercase;letter-spacing:.05em;color:var(--text-muted);font-weight:700;margin-bottom:.1rem;">' + esc(grupoTexto) + '</div>' : '') +
      '<div class="sim-cat-name">' + esc(d.categoria) + '</div>' +
      '</div>' +
      '<span class="sim-cat-badge" style="background:'+bgCor+';color:'+cor+';border:1px solid '+bdCor+';">Confiança: ' + (confTexto || '-') + '</span>' +
      '</div>' +

      (d.justificativa ? '<p class="sim-desc" style="border-left:3px solid var(--fgv-blue);padding-left:.7rem;margin-top:.6rem;">'+esc(d.justificativa)+'</p>' : '') +

      (infosHtml ?
        '<div class="sim-fields-heading">Informações a coletar</div>' +
        '<ul class="sim-fields">' + infosHtml + '</ul>'
        : '') +

      '<div class="sim-meta">' +
      (d.sla_sugerido ? '<div class="sim-meta-pill">SLA: <strong>'+esc(d.sla_sugerido)+'</strong></div>' : '') +
      (d.complexidade  ? '<div class="sim-meta-pill">Complexidade: <strong>'+esc(d.complexidade)+'</strong></div>' : '') +
      '</div>' +

      (d.titulo_sugerido || d.texto_sugerido ?
        '<div style="margin-top:.9rem;padding-top:.8rem;border-top:1px solid var(--border);">' +
        '<div style="font-size:.63rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--text-muted);margin-bottom:.5rem;">Como abrir este chamado</div>' +
        (d.titulo_sugerido ?
          '<div style="font-size:.78rem;font-weight:700;color:var(--fgv-navy);margin-bottom:.45rem;">' + esc(d.titulo_sugerido) + '</div>'
          : '') +
        textoSugeridoHtml +
        '</div>'
        : '') +

      '</div>';
  })
  .catch(function() {
    resEl.innerHTML = '<div class="empty-state"><p style="color:var(--rose);">Erro ao classificar. Verifique se o servidor está rodando.</p></div>';
  });
}

/* ===== Portal preview (padrão Jira: grupos -> chamados -> formulário) ===== */
var _ppData = null;      // [{nome, registros, chamados:[...]}]
var _ppAtivo = 0;
var _ppCarregado = false;

function loadPortalPreview() {
  if (_ppCarregado) return;
  fetch('/api/analise-resumo')
    .then(function(r) { return r.ok ? r.json() : null; })
    .then(function(resumo) {
      var side = document.getElementById('ppSide');
      var grid = document.getElementById('ppGrid');
      if (!side || !grid) return;
      if (!resumo || resumo.erro || !(resumo.portfolio_otimizado || []).length) {
        side.innerHTML = '';
        grid.innerHTML = '<p style="color:var(--pp-muted);font-size:.85rem;">Catálogo disponível após executar o pipeline.</p>';
        return;
      }
      var ordem = (resumo.grupos_logicos || []).map(function(g) { return g.nome; });
      var mapa = {};
      (resumo.portfolio_otimizado || []).forEach(function(c) {
        var g = c.grupo || 'Outros';
        (mapa[g] = mapa[g] || []).push(c);
      });
      if (!ordem.length) ordem = Object.keys(mapa);
      Object.keys(mapa).forEach(function(g) { if (ordem.indexOf(g) < 0) ordem.push(g); });
      _ppData = ordem.filter(function(g) { return mapa[g]; }).map(function(g) {
        return { nome: g, chamados: mapa[g],
          registros: mapa[g].reduce(function(s, c) { return s + (c.volume_estimado || 0); }, 0) };
      });
      _ppAtivo = 0;
      _ppCarregado = true;
      ppRenderSide();
      ppRenderGrid();
    });
}

function ppRenderSide() {
  var side = document.getElementById('ppSide');
  if (!side || !_ppData) return;
  side.innerHTML = _ppData.map(function(g, i) {
    return '<div class="pp-cs' + (i === _ppAtivo ? ' active' : '') + '" onclick="ppSelectGroup(' + i + ')">' +
      '<span>' + esc(g.nome) + '</span>' +
      '<span class="pp-cs-n">' + g.chamados.length + '</span>' +
    '</div>';
  }).join('');
}

function ppSelectGroup(i) {
  _ppAtivo = i;
  ppRenderSide();
  ppRenderGrid();
}

function _ppIcon() {
  return '<svg viewBox="0 0 24 24"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M9 13h6M9 16.5h4"/></svg>';
}

function ppRenderGrid() {
  var grid = document.getElementById('ppGrid');
  if (!grid || !_ppData) return;
  var g = _ppData[_ppAtivo];
  if (!g) { grid.innerHTML = ''; return; }
  grid.innerHTML = g.chamados.map(function(c, ci) {
    var desc = c.descricao || c.quando_usar || '';
    return '<div class="pp-rt" onclick="ppOpenChamado(' + _ppAtivo + ',' + ci + ')">' +
      '<div class="pp-rt-ico">' + _ppIcon() + '</div>' +
      '<div><div class="pp-rt-t">' + esc(c.nome) + '</div>' +
      (desc ? '<div class="pp-rt-d">' + esc(desc) + '</div>' : '') + '</div>' +
    '</div>';
  }).join('');
}

function _ppPortalNome() {
  var e = document.querySelector('.pp-assist-title');
  return e ? e.textContent.trim() : 'Portal';
}
function _ppPrefixo() {
  var ini = (_ppPortalNome().match(/[A-Za-zÀ-ÿ]+/g) || [])
    .map(function(w) { return w.charAt(0); }).join('').toUpperCase().slice(0, 4);
  return ini || 'CH';
}

function ppOpenChamado(gi, ci) {
  var g = _ppData && _ppData[gi]; if (!g) return;
  var c = g.chamados[ci]; if (!c) return;
  var campos = (c.informacoes_obrigatorias || []).map(function(info, i) {
    return '<div class="pp-jfield">' +
      '<label class="pp-jlabel">' + esc(info) + ' <span class="pp-req">*</span></label>' +
      '<input type="text" id="pp-f' + i + '" placeholder="' + esc(info) + '">' +
    '</div>';
  }).join('');
  var rodape = [];
  if (c.sla_sugerido) rodape.push('SLA sugerido: ' + esc(c.sla_sugerido));
  if (c.complexidade) rodape.push('Complexidade: ' + esc(c.complexidade));
  document.getElementById('ppModal').innerHTML =
    '<div class="pp-modal-head">' +
      '<span class="pp-mh-ico">' + _ppIcon() + '</span>' +
      '<div class="pp-mh-t"><h3>' + esc(c.nome) + '</h3>' +
        '<div class="pp-mh-sub">' + esc(g.nome) + ' &middot; Portal ' + esc(_ppPortalNome()) + '</div></div>' +
      '<button class="pp-close" onclick="ppCloseModal()"><svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg></button>' +
    '</div>' +
    '<div class="pp-modal-body"><div class="pp-modal-body-inner" id="ppBody">' +
      (c.quando_usar ? '<div class="pp-callout"><div class="pp-callout-h">Quando usar este chamado</div>' +
        '<div class="pp-callout-b">' + esc(c.quando_usar) + '</div></div>' : '') +
      '<div class="pp-reqnote">Os campos obrigatórios estão marcados com asterisco <b class="pp-req">*</b></div>' +
      '<div class="pp-jfield"><label class="pp-jlabel">Resumo <span class="pp-req">*</span></label>' +
        '<input type="text" id="pp-resumo" placeholder="Título breve do chamado"></div>' +
      campos +
      '<div class="pp-jfield"><label class="pp-jlabel">Detalhes</label>' +
        '<textarea id="pp-detalhes" placeholder="Descreva o pedido com o máximo de contexto."></textarea></div>' +
      (rodape.length ? '<div class="pp-jhelp">' + rodape.join(' &middot; ') + '</div>' : '') +
    '</div></div>' +
    '<div class="pp-modal-foot">' +
      '<button class="pp-btn-cancelar" onclick="ppCloseModal()">Cancelar</button>' +
      '<button class="pp-btn-criar" onclick="ppSubmitChamado()">Criar</button>' +
    '</div>';
  document.getElementById('ppOverlay').classList.add('on');
  document.body.style.overflow = 'hidden';
}

function ppCloseModal() {
  document.getElementById('ppOverlay').classList.remove('on');
  document.body.style.overflow = '';
}

function ppSubmitChamado() {
  var body = document.getElementById('ppBody');
  if (!body) return;
  var invalido = false;
  body.querySelectorAll('#pp-resumo, input[id^="pp-f"]').forEach(function(el) {
    if (!el.value.trim()) { el.style.borderColor = '#de350b'; el.style.boxShadow = '0 0 0 1px #de350b'; invalido = true; }
    else { el.style.borderColor = ''; el.style.boxShadow = ''; }
  });
  if (invalido) return;
  body.innerHTML = '<div class="pp-success"><div class="pp-sc-ic">' +
    '<svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg></div>' +
    '<h3>Chamado registrado</h3>' +
    '<p>Este é um protótipo do portal. Em produção, o chamado entraria na fila do grupo correspondente.</p>' +
    '<span class="pp-proto">' + ppGenProto() + '</span></div>';
  var foot = document.querySelector('#ppModal .pp-modal-foot');
  if (foot) foot.innerHTML = '<button class="pp-btn-criar" onclick="ppCloseModal()">Fechar</button>';
}

var _ppSeq = 100;
function ppGenProto() {
  var d = new Date();
  var p = function(n) { return n < 10 ? '0' + n : n; };
  _ppSeq++;
  return _ppPrefixo() + '-' + d.getFullYear() + '-' + p(d.getMonth() + 1) + p(d.getDate()) + '-' + _ppSeq;
}

// ─── Resumo executivo ─────────────────────────────────────
function loadResumoExecutivo() {
  fetch('/api/analise-resumo')
    .then(function(r) { return r.ok ? r.json() : null; })
    .then(function(resumo) {
    if (!resumo || resumo.erro) {
      var aguardando = document.getElementById('iaAguardando');
      var resultado = document.getElementById('iaResultado');
      var hero = document.getElementById('iaHeroCards');
      if (aguardando) aguardando.style.display = '';
      if (resultado) resultado.style.display = 'none';
      if (hero) hero.style.display = 'none';
      _renderConsolidacao([]);
      return;
    }
    document.getElementById('iaResultado').style.display = '';
    document.getElementById('iaAguardando').style.display = 'none';
    document.getElementById('iaHeroCards').style.display = '';

    animateCount(document.getElementById('iaTickets'),  resumo.total_tickets, '');
    animateCount(document.getElementById('iaCatAtual'), resumo.categorias_atuais, '');
    animateCount(document.getElementById('iaCatNova'),  resumo.categorias_recomendadas, '');
    animateCount(document.getElementById('iaGrupos'),    resumo.grupos_logicos_total || resumo.grupos_naturais || 0, '');

    if (resumo.usando_curadoria) {
      txt('iaCatNovaLabel', 'Tipos de Chamado Finais');
      txt('iaPortfolioNovoTitulo', 'Catálogo final curado');
    } else {
      txt('iaCatNovaLabel', 'Tipos de Chamado Sugeridos');
      txt('iaPortfolioNovoTitulo', 'Catálogo sugerido');
    }

    _renderDiagnostico(resumo.diagnostico);

    _renderComparacao(resumo);
    _renderConsolidacao(resumo.consolidacao || []);
  });
}

// Diagnóstico (Painel Executivo): lead + KPIs de insight + ações.
function _renderDiagnostico(d) {
  d = d || {};
  var leadEl = document.getElementById('iaDiagLead');
  if (leadEl) {
    var lead = d.lead || '';
    var dest = d.lead_destaque || '';
    if (dest && lead.indexOf(dest) > -1) {
      leadEl.innerHTML = esc(lead).replace(esc(dest), '<span class="hl">' + esc(dest) + '</span>');
    } else {
      leadEl.textContent = lead;
    }
  }
  var kpisEl = document.getElementById('iaDiagKpis');
  if (kpisEl) kpisEl.innerHTML = (d.kpis || []).map(function(k) {
    return '<div class="diag-kpi ' + esc(k.cor || 'blue') + '">' +
      '<div class="diag-kpi-num">' + esc(k.valor) + '</div>' +
      '<div class="diag-kpi-label">' + esc(k.label) + '</div>' +
    '</div>';
  }).join('');
  var acoesEl = document.getElementById('iaDiagAcoes');
  if (acoesEl) acoesEl.innerHTML = (d.acoes || []).map(function(a) {
    var ci = a.indexOf(':');
    var html = ci > -1 ? '<b>' + esc(a.slice(0, ci)) + '</b>' + esc(a.slice(ci)) : esc(a);
    return '<li>' + html + '</li>';
  }).join('');
}

function loadInteracoes() {
  fetch('/api/interacoes-categorias')
    .then(function(r) { return r.ok ? r.json() : null; })
    .then(function(dados) { _renderInteracoes(dados || []); });
}

// ─── Grupos Identificados pela IA ──────────────────────────
var _gnCarregado = false;
function loadGruposNaturais() {
  if (_gnCarregado) return;
  fetch('/api/analise-clusters')
    .then(function(r) { return r.ok ? r.json() : null; })
    .then(function(data) {
      if (!data || data.erro) {
        document.getElementById('gnResultado').style.display  = 'none';
        document.getElementById('gnAguardando').style.display = '';
        return;
      }
      _gnCarregado = true;
      _renderClusters(data);
    });
}


function _renderComparacao(resumo) {
  if (document.getElementById('iaNAtual')) {
    txt('iaNAtual', resumo.categorias_atuais || Object.keys(resumo.categorias_atuais_volume || {}).length);
  }
  var elAtual = document.getElementById('iaCatAtualLista');
  if (elAtual && resumo.grupos_atuais && resumo.grupos_atuais.length) {
    elAtual.innerHTML = resumo.grupos_atuais.map(function(g) {
      var linhas = (g.classificacoes || []).map(function(c) {
        var pct = c.percentual != null ? String(c.percentual).replace('.', ',') : '-';
        return '<div class="cat-row"><span class="cat-row-name">'+esc(c.nome)+'</span><span class="cat-row-value">'+(c.volume||0)+' ('+pct+'%)</span></div>';
      }).join('');
      return '<div style="margin-bottom:1.1rem;">' +
        '<div style="display:flex;justify-content:space-between;align-items:baseline;margin:.2rem 0 .5rem;border-bottom:2px solid var(--fgv-navy);padding-bottom:.28rem;">' +
        '<strong style="color:var(--fgv-navy);font-size:.8rem;text-transform:uppercase;letter-spacing:.04em;">'+esc(g.nome)+'</strong>' +
        '<span style="color:var(--text-muted);font-size:.72rem;">'+(g.classificacoes||[]).length+' tipos de chamado · '+(g.total||0)+' chamados</span>' +
        '</div>' + linhas + '</div>';
    }).join('');
  } else if (elAtual && resumo.categorias_atuais_volume) {
    var sorted = Object.entries(resumo.categorias_atuais_volume).sort(function(a,b){return b[1]-a[1];});
    var total  = sorted.reduce(function(s,e){return s+e[1];},0);
    elAtual.innerHTML = sorted.map(function(e){
      var pct = (e[1]/total*100).toFixed(1);
      return '<div class="cat-row"><span class="cat-row-name">'+esc(e[0])+'</span><span class="cat-row-value">'+e[1]+' ('+pct+'%)</span></div>';
    }).join('');
  }

  var elNovo = document.getElementById('iaPortfolioNovo');
  if (document.getElementById('iaNNova')) txt('iaNNova', (resumo.portfolio_otimizado||[]).length);
  if (elNovo && resumo.portfolio_otimizado) {
    var cor = 'var(--fgv-navy)';
    // Monta um card de chamado (request type). i garante ids únicos entre grupos.
    function _cardChamado(cat, i) {
      var infos = (cat.informacoes_obrigatorias||[]).map(function(info){
        return '<li style="font-size:.73rem;color:var(--text-muted);margin:.18rem 0;">'+esc(info)+'</li>';
      }).join('');
      return '<div class="portfolio-card" style="border-left-color:'+cor+'" onclick="togglePortNew(\'pn'+i+'\')">' +
        '<div style="display:flex;justify-content:space-between;">' +
        '<strong style="color:'+cor+';font-size:.86rem;font-family:var(--font-display);">'+esc(cat.nome)+'</strong>' +
        '<span style="color:var(--text-muted);font-size:.73rem;">'+(cat.volume_estimado||'-')+' chamados</span>' +
        '</div>' +
        '<p style="color:var(--text-secondary);font-size:.78rem;margin:.28rem 0 0;line-height:1.5;">'+esc(cat.descricao||'')+'</p>' +
        '<div id="pn'+i+'" style="display:none;margin-top:.6rem;padding-top:.6rem;border-top:1px solid var(--border);">' +
        (infos?'<ul style="list-style:none;padding:0;margin:0 0 .35rem;">'+infos+'</ul>':'') +
        '<span style="font-size:.68rem;color:var(--text-muted);">SLA: '+esc(cat.sla_sugerido||'-')+'</span>' +
        '</div></div>';
    }
    // Agrupa os chamados por AGRUPADOR lógico (campo 'grupo'); fallback quando ausente.
    var ordemGrupos = [], porGrupo = {};
    resumo.portfolio_otimizado.forEach(function(cat){
      var g = cat.grupo || 'Outros';
      if (!porGrupo[g]) { porGrupo[g] = []; ordemGrupos.push(g); }
      porGrupo[g].push(cat);
    });
    var i = 0;
    elNovo.innerHTML = ordemGrupos.map(function(g){
      var volG = porGrupo[g].reduce(function(s,c){ return s + (c.volume_estimado||0); }, 0);
      var cards = porGrupo[g].map(function(cat){ return _cardChamado(cat, i++); }).join('');
      return '<div style="margin-bottom:1.1rem;">' +
        '<div style="display:flex;justify-content:space-between;align-items:baseline;margin:.2rem 0 .5rem;border-bottom:2px solid var(--fgv-navy);padding-bottom:.28rem;">' +
        '<strong style="color:var(--fgv-navy);font-size:.8rem;text-transform:uppercase;letter-spacing:.04em;">'+esc(g)+'</strong>' +
        '<span style="color:var(--text-muted);font-size:.72rem;">'+porGrupo[g].length+' tipos de chamado · '+volG+' chamados</span>' +
        '</div>' + cards + '</div>';
    }).join('');
  }
}

function togglePortNew(id) {
  var el = document.getElementById(id);
  if (el) el.style.display = el.style.display==='none'?'':'none';
}

// Visão organizacional "catálogo novo -> catálogo atual": cada tipo de chamado
// proposto e os tipos de chamado atuais que ele consolida, por grupo de chamados.
function _renderConsolidacao(consolidacao) {
  var el = document.getElementById('iaConsolidacao');
  if (!el) return;
  if (!consolidacao || !consolidacao.length) {
    el.innerHTML = '<p style="color:var(--text-muted);font-size:.8rem;">Sem dados de consolidação disponíveis.</p>';
    return;
  }
  el.innerHTML = consolidacao.map(function(g) {
    var linhas = (g.chamados || []).map(function(c) {
      var origens = c.origens || [];
      var chips = origens.length
        ? origens.map(function(o){ return '<span class="consol-old">' + esc(o.nome) + ' <span class="consol-old-vol">(' + (o.volume || 0) + ')</span></span>'; }).join('')
        : '<span class="consol-old consol-old-vazio">(tipo novo, sem equivalente no cat&aacute;logo atual)</span>';
      var meta = origens.length
        ? origens.length + ' tipo(s) atual(is) &middot; ' + (c.volume || 0) + ' chamados hist&oacute;ricos'
        : 'tipo novo';
      return '<div class="consol-row">' +
        '<div class="consol-to">' +
          '<strong>' + esc(c.novo) + '</strong>' +
          '<span class="consol-to-meta">' + meta + '</span>' +
        '</div>' +
        '<div class="consol-arrow">&#8594;</div>' +
        '<div class="consol-from">' + chips + '</div>' +
      '</div>';
    }).join('');
    return '<div class="consol-group">' +
      '<div class="consol-group-head">' +
        '<strong>Grupo de Chamado: ' + esc(g.grupo) + '</strong>' +
        '<span>' + (g.chamados || []).length + ' tipos de chamado · ' + (g.volume || 0) + ' chamados históricos</span>' +
      '</div>' + linhas + '</div>';
  }).join('');
}

function _renderClusters(data) {
  var el = document.getElementById('iaClusters');
  if (!el) return;
  var clusters = (data.clusters||[]).slice(0,25);
  el.innerHTML = '<div class="clusters-grid">' +
    clusters.map(function(c,i){
      var pct = (c.volume_percentual||0).toFixed(1);
      var catTop = Object.entries(c.distribuicao_categorias_atuais||{}).sort(function(a,b){return b[1]-a[1];})[0];
      var infos = (c.informacoes_necessarias||[]).slice(0,3);
      var infosHtml = infos.map(function(s){
        return '<li style="margin:.17rem 0;line-height:1.4;">'+esc(s)+'</li>';
      }).join('');
      return '<div class="cluster-card">' +
        '<div style="display:flex;justify-content:space-between;margin-bottom:.32rem;">' +
        '<span style="font-size:.66rem;background:rgba(0,139,201,.1);color:var(--fgv-blue);padding:.1rem .4rem;border-radius:999px;">Grupo '+(i+1)+'</span>' +
        '<span style="color:var(--fgv-blue);font-weight:700;font-size:.78rem;font-family:var(--font-mono);">'+(c.total_tickets||0)+' ('+pct+'%)</span>' +
        '</div>' +
        '<strong style="display:block;color:var(--fgv-navy);font-size:.86rem;margin-bottom:.25rem;">'+esc(c.nome||'Grupo sem rótulo')+'</strong>' +
        (catTop?'<div style="font-size:.68rem;color:var(--text-muted);margin-bottom:.32rem;">↳ '+esc(catTop[0])+'</div>':'') +
        '<p style="margin:.2rem 0;color:var(--text-secondary);font-size:.74rem;line-height:1.45;">'+esc(c.descricao||'')+'</p>' +
        (c.quando_usar?'<p style="margin:.25rem 0;color:var(--text-muted);font-size:.72rem;line-height:1.45;">Usar quando: '+esc(c.quando_usar)+'</p>':'') +
        (infosHtml?'<ul style="margin:.35rem 0 0;padding-left:.85rem;color:var(--text-secondary);font-size:.72rem;">'+infosHtml+'</ul>':'') +
        '</div>';
    }).join('') + '</div>';
}

function _calcReducaoTempo(tDir, tMul) {
  if (tDir == null || tMul == null || tMul <= 0 || tDir >= tMul) return null;
  return (tMul - tDir) / tMul * 100;
}

function _renderInteracoes(dados) {
  var tbody = document.getElementById('iaInteracoesBody');
  if (!tbody) return;
  if (!dados || !dados.length) {
    tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;color:var(--text-muted);padding:1.2rem;">Dados não disponíveis - knowledge_base.db não encontrado.</td></tr>';
    return;
  }
  tbody.innerHTML = dados.map(function(row) {
    var pctDir = row.total ? (row.diretos   / row.total * 100).toFixed(1) : '-';
    var pctMul = row.total ? (row.multiplos / row.total * 100).toFixed(1) : '-';
    var tDir   = row.t_medio_direto   != null ? row.t_medio_direto   : null;
    var tMul   = row.t_medio_multiplo != null ? row.t_medio_multiplo : null;
    var tMed   = row.tempo_medio_horas != null ? row.tempo_medio_horas : null;
    var inter  = row.media_interacoes != null ? row.media_interacoes : null;
    var taxa   = row.taxa_resolucao != null ? row.taxa_resolucao : null;
    var red    = _calcReducaoTempo(tDir, tMul);
    return '<tr>' +
      '<td>' + esc(row.categoria || '') + '</td>' +
      '<td style="text-align:right;font-family:var(--font-mono);">' + (row.total || 0) + '</td>' +
      '<td style="text-align:right;font-family:var(--font-mono);">' + (inter != null ? Number(inter).toFixed(1) : '-') + '</td>' +
      '<td style="text-align:right;font-family:var(--font-mono);">' + (tMed != null ? tMed : '-') + '</td>' +
      '<td style="text-align:right;font-family:var(--font-mono);">' + (taxa != null ? taxa + '%' : '-') + '</td>' +
      '<td style="text-align:right;font-family:var(--font-mono);">' + (row.diretos || 0) +
        ' <span style="color:var(--text-muted);font-size:.72rem;">(' + pctDir + '%)</span></td>' +
      '<td style="text-align:right;font-family:var(--font-mono);">' + (row.multiplos || 0) +
        ' <span style="color:var(--text-muted);font-size:.72rem;">(' + pctMul + '%)</span></td>' +
      '<td style="text-align:right;font-family:var(--font-mono);">' + (tDir != null ? tDir : '-') + '</td>' +
      '<td style="text-align:right;font-family:var(--font-mono);">' + (tMul != null ? tMul : '-') + '</td>' +
      '<td style="text-align:right;font-family:var(--font-mono);color:var(--fgv-navy);font-weight:600;">' +
        (red != null ? red.toFixed(1) + '%' : '-') + '</td>' +
      '</tr>';
  }).join('');
}

// ─── Histórico ────────────────────────────────────────────
var _histPage = 1;

function loadHistorico(page) {
  _histPage = page || 1;
  var busca = (document.getElementById('histBusca') || {}).value || '';
  var url = '/api/historico?page=' + _histPage + '&limit=50&q=' + encodeURIComponent(busca);
  var tbody = document.getElementById('histBody');
  if (tbody) tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:2rem;color:var(--text-muted);">Carregando…</td></tr>';

  fetch(url)
    .then(function(r) { return r.json(); })
    .then(function(d) {
      var tot = document.getElementById('histTotal');
      if (tot) tot.textContent = d.total.toLocaleString('pt-BR') + ' chamados';

      if (!tbody) return;
      if (!d.tickets.length) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:2rem;color:var(--text-muted);">Nenhum chamado encontrado.</td></tr>';
        return;
      }

      var semDados = !d.tem_dados_pipeline;
      if (semDados) {
        var aviso = document.createElement('div');
        aviso.style.cssText = 'background:rgba(253,219,81,.12);border:1px solid rgba(253,219,81,.4);border-radius:8px;padding:.7rem 1rem;font-size:.82rem;color:var(--fgv-navy);margin-bottom:.75rem;';
        aviso.textContent = 'Dados do pipeline (03_clusters.json) não disponíveis. Rode as etapas 1-3 do pipeline com o Claude para ver os grupos identificados pela IA.';
        tbody.parentElement.parentElement.insertAdjacentElement('beforebegin', aviso);
      }

      tbody.innerHTML = d.tickets.map(function(t) {
        var desc = t.descricao ? trunc(t.descricao, 120) : '-';
        var llm    = t.categoria_llm || '-';
        var grupoLlm = t.grupo_llm || '';
        var llmCor = t.categoria_llm ? 'var(--fgv-navy)' : 'var(--text-muted)';
        var conf   = t.confianca_llm || '-';
        var confCor = conf === 'alta' ? 'var(--fgv-turquesa)' : conf === 'media' ? 'var(--fgv-medio)' : 'var(--text-muted)';
        return '<tr>' +
          '<td style="font-family:var(--font-mono);font-size:.78rem;white-space:nowrap;color:var(--fgv-navy);">' + esc(t.chave||'') + '</td>' +
          '<td>' +
            '<div style="font-weight:500;color:var(--fgv-navy);font-size:.84rem;">' + esc(t.titulo||'') + '</div>' +
            '<div style="font-size:.76rem;color:var(--text-muted);margin-top:.15rem;">' + esc(desc) + '</div>' +
          '</td>' +
          '<td style="font-size:.8rem;color:var(--text-secondary);">' + esc(t.tipo_solicitacao||'-') + '</td>' +
          '<td style="font-size:.8rem;color:'+llmCor+';">' +
            (grupoLlm ? '<div style="font-size:.7rem;text-transform:uppercase;letter-spacing:.04em;color:var(--text-muted);font-weight:700;">' + esc(grupoLlm) + '</div>' : '') +
            '<div style="font-weight:500;">' + esc(llm) + '</div>' +
          '</td>' +
          '<td style="text-align:center;font-size:.78rem;color:'+confCor+';font-weight:600;">' + esc(conf) + '</td>' +
          '</tr>';
      }).join('');

      // Paginação
      var pag = document.getElementById('histPag');
      if (pag) {
        var totalPag = Math.ceil(d.total / d.limit);
        var html = '';
        var start = Math.max(1, _histPage - 2);
        var end   = Math.min(totalPag, _histPage + 2);
        if (_histPage > 1) html += '<button class="btn-ghost" onclick="loadHistorico(' + (_histPage-1) + ')" style="padding:.3rem .7rem;font-size:.78rem;">‹</button>';
        for (var p = start; p <= end; p++) {
          var active = p === _histPage ? 'background:var(--fgv-navy);color:#fff;border-color:var(--fgv-navy);' : '';
          html += '<button class="btn-ghost" onclick="loadHistorico('+p+')" style="padding:.3rem .7rem;font-size:.78rem;'+active+'">'+p+'</button>';
        }
        if (_histPage < totalPag) html += '<button class="btn-ghost" onclick="loadHistorico(' + (_histPage+1) + ')" style="padding:.3rem .7rem;font-size:.78rem;">›</button>';
        pag.innerHTML = html;
      }
    });
}

// ─── Init ─────────────────────────────────────────────────
initFiltroMes();
loadDash();
loadInteracoes();
loadCategorias();
loadResumoExecutivo();
