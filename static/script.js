// FGV Intelligence Center — Frontend Script
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
  if (name === 'analise-ia')      loadAnaliseIA();
  if (name === 'simulacao')       atualizarModoSim();
  if (name === 'historico')       loadHistorico(1);
  if (name === 'grupos-naturais') loadGruposNaturais();
}

function esc(t) {
  if (!t) return '';
  var d = document.createElement('div');
  d.textContent = String(t);
  return d.innerHTML;
}

function txt(id, v) {
  var e = document.getElementById(id);
  if (e) e.textContent = (v != null) ? v : '—';
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

      // KPI row 2 — operacional
      txt('dbTaxaResolucao',  d.taxa_resolucao);
      animateCount(document.getElementById('dbBacklog'),     d.backlog);
      animateCount(document.getElementById('dbFinalizados'), d.finalizados);

      // Distribuição por categoria
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

// ─── Categorias ───────────────────────────────────────────
function loadCategorias() {
  fetch('/api/portfolio-final')
    .then(function(r) { return r.json(); })
    .then(function(finalPortfolio) {
      var hasFinal = finalPortfolio && finalPortfolio.length;
      var title = document.getElementById('portfolioAtivoTitulo');
      var badge = document.getElementById('portfolioAtivoBadge');
      var desc = document.getElementById('portfolioAtivoDescricao');
      var finalCard = document.getElementById('portfolioFinalCard');

      if (hasFinal) {
        if (title) title.textContent = 'Portfólio Final';
        if (badge) {
          badge.textContent = 'CURADORIA DA ÁREA';
          badge.style.color = '#b45309';
          badge.style.background = 'rgba(180,83,9,.1)';
          badge.style.borderColor = 'rgba(180,83,9,.3)';
        }
        if (desc) desc.textContent = 'Portfólio final definido pela área (Stage 7), com os chamados reclassificados. Clique em uma categoria para ver os campos obrigatórios a coletar.';
        renderPortfolioNovo(finalPortfolio);
        if (finalCard) finalCard.style.display = 'none';
      } else {
        if (title) title.textContent = 'Portfólio Recomendado';
        if (badge) {
          badge.textContent = 'AUTOMÁTICO';
          badge.style.color = 'var(--text-muted)';
          badge.style.background = 'var(--bg-glass)';
          badge.style.borderColor = 'var(--border)';
        }
        if (desc) desc.textContent = 'Recomendação gerada pelo pipeline a partir dos dados. Clique em uma categoria para ver os campos obrigatórios a coletar.';
        fetch('/api/portfolio-novo')
          .then(function(r) { return r.json(); })
          .then(renderPortfolioNovo);
        renderPortfolioFinal(finalPortfolio);
      }
    });
  fetch('/api/mapeamento-detalhado')
    .then(function(r) { return r.json(); })
    .then(renderTabelaCategorias);
}

function renderPortfolioNovo(portfolio)  { renderPortfolioCards(portfolio, 'portfolioNovoBody', 'cn'); }

function renderPortfolioFinal(portfolio) {
  var card = document.getElementById('portfolioFinalCard');
  if (portfolio && portfolio.length) {
    if (card) card.style.display = '';
    renderPortfolioCards(portfolio, 'portfolioFinalBody', 'cf');
  } else if (card) {
    card.style.display = 'none';
  }
}

function renderPortfolioCards(portfolio, elId, idPrefix) {
  var el = document.getElementById(elId);
  if (!el) return;
  if (!portfolio || !portfolio.length) { el.innerHTML = ''; return; }
  el.innerHTML = '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:.75rem;">' +
    portfolio.map(function(cat, i) {
      var tid = idPrefix + i;
      var cor = 'var(--fgv-navy)';
      var infos = (cat.informacoes_obrigatorias || cat.informacoes_necessarias || []).map(function(info) {
        return '<li style="font-size:.76rem;color:var(--text-muted);margin:.2rem 0;display:flex;gap:.4rem;align-items:flex-start;">' +
          '<svg width="9" height="9" viewBox="0 0 10 10" style="margin-top:.2em;flex-shrink:0;"><circle cx="5" cy="5" r="4" fill="' + cor + '" opacity=".6"/></svg>' +
          esc(info) + '</li>';
      }).join('');
      var vol = cat.volume_estimado || 0;
      var isObrig = cat.obrigatoria;
      return '<div style="padding:.9rem 1rem;border-left:3px solid '+cor+';background:var(--bg-glass);border-radius:0 var(--radius-sm) var(--radius-sm) 0;border:1px solid var(--border);border-left-width:3px;border-left-color:'+cor+';cursor:pointer;transition:all .18s;" class="portfolio-card" onclick="toggleCatNova(\''+tid+'\')">' +
        '<div style="display:flex;justify-content:space-between;align-items:center;">' +
        '<strong style="color:'+cor+';font-family:var(--font-display);font-size:.9rem;">'+esc(cat.nome)+'</strong>' +
        '<div style="display:flex;gap:.4rem;align-items:center;">' +
        (cat.encaminhamento ? '<span style="font-size:.62rem;background:rgba(180,83,9,.1);color:#b45309;border:1px solid rgba(180,83,9,.3);padding:.1rem .4rem;border-radius:999px;font-weight:700;">↗ ENCAMINHAR</span>' : (isObrig ? '<span style="font-size:.62rem;background:rgba(0,58,121,.08);color:var(--fgv-navy);border:1px solid rgba(0,58,121,.2);padding:.1rem .4rem;border-radius:999px;font-weight:700;">FIXO</span>' : '')) +
        '<span style="color:var(--text-muted);font-size:.75rem;">'+(vol||'—')+' tickets</span>' +
        '</div></div>' +
        '<p style="color:var(--text-secondary);font-size:.79rem;margin:.4rem 0 0;line-height:1.5;">'+esc(cat.descricao||'')+'</p>' +
        '<div id="'+tid+'" style="display:none;margin-top:.7rem;padding-top:.7rem;border-top:1px solid var(--border);">' +
        (infos?'<p style="font-size:.67rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--cyan);margin-bottom:.4rem;">Informações obrigatórias</p><ul style="list-style:none;margin:0;padding:0;">'+infos+'</ul>':'') +
        '<div style="display:flex;gap:.5rem;margin-top:.55rem;flex-wrap:wrap;">' +
        (cat.sla_sugerido?'<span style="font-size:.69rem;padding:.15rem .5rem;background:var(--bg-glass);border:1px solid var(--border);border-radius:999px;color:var(--text-muted);">SLA: '+esc(cat.sla_sugerido)+'</span>':'') +
        (cat.complexidade?'<span style="font-size:.69rem;padding:.15rem .5rem;background:var(--bg-glass);border:1px solid var(--border);border-radius:999px;color:var(--text-muted);">'+esc(cat.complexidade)+'</span>':'') +
        '</div></div></div>';
    }).join('') + '</div>';
}

function toggleCatNova(id) {
  var el = document.getElementById(id);
  if (el) el.style.display = el.style.display === 'none' ? '' : 'none';
}

function renderTabelaCategorias(rows) {
  var tbody = document.getElementById('catBody');
  if (!tbody) return;

  // Agrupa por categoria_atual
  var grupos = {};
  var ordem = [];
  rows.forEach(function(r) {
    if (!grupos[r.categoria_atual]) {
      grupos[r.categoria_atual] = [];
      ordem.push(r.categoria_atual);
    }
    grupos[r.categoria_atual].push(r);
  });

  var html = '';
  ordem.forEach(function(cat) {
    var linhas = grupos[cat];
    var first = linhas[0];
    var span = linhas.length;
    var inter = (first.media_interacoes != null && first.media_interacoes > 0) ? first.media_interacoes.toFixed(1) : '—';
    var tempo = first.tempo_medio_horas ? first.tempo_medio_horas.toFixed(0) + 'h' : '—';
    var taxa  = first.taxa_resolucao ? first.taxa_resolucao.toFixed(1) + '%' : '—';

    linhas.forEach(function(r, idx) {
      html += '<tr>';
      if (idx === 0) {
        var tdStyle = 'vertical-align:middle;' + (span > 1 ? 'border-bottom:2px solid var(--fgv-blue);' : '');
        html += '<td rowspan="'+span+'" style="'+tdStyle+'font-weight:500;">' + esc(cat) + '</td>';
        html += '<td rowspan="'+span+'" style="'+tdStyle+'text-align:center;font-family:var(--font-mono);color:var(--fgv-navy);">' + (first.total_categoria||0) + '</td>';
        html += '<td rowspan="'+span+'" style="'+tdStyle+'text-align:center;font-family:var(--font-mono);color:var(--fgv-navy);">' + inter + '</td>';
        html += '<td rowspan="'+span+'" style="'+tdStyle+'text-align:center;font-family:var(--font-mono);color:var(--fgv-navy);">' + tempo + '</td>';
        html += '<td rowspan="'+span+'" style="'+tdStyle+'text-align:center;font-family:var(--font-mono);color:var(--fgv-navy);">' + taxa + '</td>';
      }
      html += '<td style="color:var(--fgv-navy);font-size:.82rem;">' + esc(r.nova_categoria) + '</td>';
      html += '<td style="text-align:center;font-family:var(--font-mono);color:var(--fgv-navy);">' + r.chamados + '</td>';
      html += '</tr>';
    });
  });
  tbody.innerHTML = html;
}

// ─── Simulação ────────────────────────────────────────────
var _simExemplos = {
  1: { d: 'Preciso de permissão de leitura ao bucket AWS S3 para acessar os dados do projeto PGD. Sou pesquisador e o orientador já aprovou o acesso.' },
  2: { d: 'Preciso instalar a biblioteca pandas versão 2.0 no servidor de análise compartilhado do laboratório.' },
  3: { d: 'O sistema de consultas está indisponível desde esta manhã, retornando HTTP 500. Afeta todos os usuários do setor de pesquisa.' },
  4: { d: 'O alerta de espaço em disco disparou no servidor de arquivos da pesquisa. Está com menos de 10% livre e precisa de ampliação ou limpeza urgente.' }
};

function simExemplo(n) {
  var ex = _simExemplos[n];
  if (!ex) return;
  document.getElementById('simDescricao').value = ex.d;
}

function _setBadge(el, disponivel) {
  if (!el) return;
  el.textContent  = disponivel ? 'disponível' : 'indisponível';
  el.style.background = disponivel ? 'rgba(59,174,150,.15)' : 'rgba(155,10,81,.12)';
  el.style.color      = disponivel ? '#3bae96' : '#9b0a51';
}

function atualizarModoSim() {
  // Verifica ambos os status sempre que a aba é aberta ou o modo muda
  fetch('/api/ollama-status').then(function(r) { return r.json(); }).then(function(d) {
    _setBadge(document.getElementById('llmStatusBadge'), d.disponivel);
  });
  fetch('/api/openai-status').then(function(r) { return r.json(); }).then(function(d) {
    _setBadge(document.getElementById('openaiStatusBadge'), d.disponivel);
    if (d.modelo) window._openaiModelo = d.modelo;
  });
}

function limparSimulacao() {
  document.getElementById('simDescricao').value = '';
  var wrap = document.getElementById('simResultWrap');
  if (wrap) wrap.classList.remove('has-result');
  document.getElementById('simResultado').innerHTML =
    '<div class="empty-state"><p>Descreva o chamado e clique em <strong>Classificar Chamado</strong>.</p></div>';
}

function executarSimulacao() {
  var descricao = document.getElementById('simDescricao').value.trim();
  var resEl     = document.getElementById('simResultado');
  var wrap      = document.getElementById('simResultWrap');
  var modoEl = document.querySelector('input[name="simModo"]:checked');
  var modo   = modoEl ? modoEl.value : 'llm';

  if (!descricao) { alert('Descreva o chamado antes de classificar.'); return; }

  wrap.classList.remove('has-result');
  var openaiModelo = window._openaiModelo || 'OpenAI';
  var msgLoading = modo === 'openai'
    ? 'Consultando OpenAI (' + openaiModelo + ')…'
    : 'Consultando LLM local (gemma4:26b-q8)… pode levar até 15 segundos.';

  resEl.innerHTML =
    '<div class="sim-loading">' +
    '<div class="sim-dots"><span></span><span></span><span></span></div>' +
    '<p>' + msgLoading + '</p>' +
    '</div>';

  var endpoint = modo === 'openai' ? '/api/simular-openai' : '/api/simular-llm';

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

    wrap.classList.add('has-result');

    var confTexto = d.confianca || '';
    var conf  = confTexto === 'alta' ? 90 : confTexto === 'media' ? 60 : confTexto === 'baixa' ? 30 : 50;
    var cor   = conf >= 65 ? 'var(--fgv-turquesa)' : conf >= 35 ? 'var(--fgv-blue)' : 'var(--fgv-vinho)';
    var bgCor = conf >= 65 ? 'rgba(59,174,150,.1)'  : conf >= 35 ? 'rgba(0,139,201,.1)'  : 'rgba(155,10,81,.1)';
    var bdCor = conf >= 65 ? 'rgba(59,174,150,.35)' : conf >= 35 ? 'rgba(0,139,201,.35)' : 'rgba(155,10,81,.35)';

    var modoLabel = modo === 'openai'
      ? 'OPENAI · ' + (window._openaiModelo || 'OpenAI')
      : 'LLM LOCAL · gemma4:26b-q8';

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
      '<div class="sim-cat-name">' + esc(d.categoria) + '</div>' +
      '<span class="sim-cat-badge" style="background:'+bgCor+';color:'+cor+';border:1px solid '+bdCor+';">Confiança: ' + (confTexto || '—') + '</span>' +
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

// ─── Análise IA ───────────────────────────────────────────
function loadAnaliseIA() {
  Promise.all([
    fetch('/api/analise-resumo').then(function(r)        { return r.ok ? r.json() : null; }),
    fetch('/api/interacoes-categorias').then(function(r) { return r.ok ? r.json() : null; })
  ]).then(function(results) {
    var resumo     = results[0];
    var interacoes = results[1];

    if (!resumo || resumo.erro) {
      document.getElementById('iaAguardando').style.display = '';
      return;
    }
    document.getElementById('iaResultado').style.display  = '';
    document.getElementById('iaAguardando').style.display = 'none';
    document.getElementById('iaHeroCards').style.display  = '';

    animateCount(document.getElementById('iaTickets'),  resumo.total_tickets, '');
    animateCount(document.getElementById('iaCatAtual'), resumo.categorias_atuais, '');
    animateCount(document.getElementById('iaCatNova'),  resumo.categorias_recomendadas, '');

    if (resumo.usando_curadoria) {
      txt('iaCatNovaLabel', 'Categorias Finais');
      txt('iaPortfolioNovoTitulo', 'Final Curado');
    } else {
      txt('iaCatNovaLabel', 'Categorias Recomendadas');
      txt('iaPortfolioNovoTitulo', 'Recomendado');
    }

    var metr = resumo.metricas_interacoes;
    if (metr) {
      animateCount(document.getElementById('iaMultiplas'), metr.pct_multiplas, '%');
      txt('iaDireto', metr.pct_diretos + '%');
    } else {
      txt('iaMultiplas', '—');
      txt('iaDireto', '—');
    }

    var diag = document.getElementById('iaDiagnostico');
    if (diag) diag.textContent = resumo.analise_geral || '';

    _renderComparacao(resumo);
    _renderInteracoes(interacoes || []);
  });
}

// ─── Grupos Naturais ───────────────────────────────��──────
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
  if (elAtual && resumo.categorias_atuais_volume) {
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
    elNovo.innerHTML = resumo.portfolio_otimizado.map(function(cat,i){
      var cor = 'var(--fgv-navy)';
      var infos = (cat.informacoes_obrigatorias||[]).map(function(info){
        return '<li style="font-size:.73rem;color:var(--text-muted);margin:.18rem 0;">'+esc(info)+'</li>';
      }).join('');
      return '<div class="portfolio-card" style="border-left-color:'+cor+'" onclick="togglePortNew(\'pn'+i+'\')">' +
        '<div style="display:flex;justify-content:space-between;">' +
        '<strong style="color:'+cor+';font-size:.86rem;font-family:var(--font-display);">'+esc(cat.nome)+'</strong>' +
        '<span style="color:var(--text-muted);font-size:.73rem;">'+(cat.volume_estimado||'—')+' tickets</span>' +
        '</div>' +
        '<p style="color:var(--text-secondary);font-size:.78rem;margin:.28rem 0 0;line-height:1.5;">'+esc(cat.descricao||'')+'</p>' +
        '<div id="pn'+i+'" style="display:none;margin-top:.6rem;padding-top:.6rem;border-top:1px solid var(--border);">' +
        (infos?'<ul style="list-style:none;padding:0;margin:0 0 .35rem;">'+infos+'</ul>':'') +
        '<span style="font-size:.68rem;color:var(--text-muted);">SLA: '+esc(cat.sla_sugerido||'—')+'</span>' +
        '</div></div>';
    }).join('');
  }
}

function togglePortNew(id) {
  var el = document.getElementById(id);
  if (el) el.style.display = el.style.display==='none'?'':'none';
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
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-muted);padding:1.2rem;">Dados não disponíveis — knowledge_base.db não encontrado.</td></tr>';
    return;
  }
  tbody.innerHTML = dados.map(function(row) {
    var pctDir = row.total ? (row.diretos   / row.total * 100).toFixed(1) : '—';
    var pctMul = row.total ? (row.multiplos / row.total * 100).toFixed(1) : '—';
    var tDir   = row.t_medio_direto   != null ? row.t_medio_direto   : null;
    var tMul   = row.t_medio_multiplo != null ? row.t_medio_multiplo : null;
    var red    = _calcReducaoTempo(tDir, tMul);
    return '<tr>' +
      '<td>' + esc(row.categoria || '') + '</td>' +
      '<td style="text-align:right;font-family:var(--font-mono);">' + (row.total || 0) + '</td>' +
      '<td style="text-align:right;font-family:var(--font-mono);">' + (row.diretos || 0) +
        ' <span style="color:var(--text-muted);font-size:.72rem;">(' + pctDir + '%)</span></td>' +
      '<td style="text-align:right;font-family:var(--font-mono);">' + (row.multiplos || 0) +
        ' <span style="color:var(--text-muted);font-size:.72rem;">(' + pctMul + '%)</span></td>' +
      '<td style="text-align:right;font-family:var(--font-mono);">' + (tDir != null ? tDir : '—') + '</td>' +
      '<td style="text-align:right;font-family:var(--font-mono);">' + (tMul != null ? tMul : '—') + '</td>' +
      '<td style="text-align:right;font-family:var(--font-mono);color:var(--fgv-navy);font-weight:600;">' +
        (red != null ? red.toFixed(1) + '%' : '—') + '</td>' +
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
        aviso.textContent = 'Dados do pipeline (03_clusters.json) não disponíveis localmente. Copie o arquivo do HPC após a execução para ver os grupos naturais.';
        tbody.parentElement.parentElement.insertAdjacentElement('beforebegin', aviso);
      }

      tbody.innerHTML = d.tickets.map(function(t) {
        var desc = t.descricao ? trunc(t.descricao, 120) : '—';
        var llm    = t.categoria_llm || '—';
        var llmCor = t.categoria_llm ? 'var(--fgv-navy)' : 'var(--text-muted)';
        var conf   = t.confianca_llm || '—';
        var confCor = conf === 'alta' ? 'var(--fgv-turquesa)' : conf === 'media' ? 'var(--fgv-medio)' : 'var(--text-muted)';
        return '<tr>' +
          '<td style="font-family:var(--font-mono);font-size:.78rem;white-space:nowrap;color:var(--fgv-navy);">' + esc(t.chave||'') + '</td>' +
          '<td>' +
            '<div style="font-weight:500;color:var(--fgv-navy);font-size:.84rem;">' + esc(t.titulo||'') + '</div>' +
            '<div style="font-size:.76rem;color:var(--text-muted);margin-top:.15rem;">' + esc(desc) + '</div>' +
          '</td>' +
          '<td style="font-size:.8rem;color:var(--text-secondary);">' + esc(t.tipo_solicitacao||'—') + '</td>' +
          '<td style="font-size:.8rem;font-weight:500;color:'+llmCor+';">' + esc(llm) + '</td>' +
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
loadCategorias();
