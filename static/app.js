/* ════════════════════════════════════════════════════════
   Lucas_OS — app.js v2.0
   SPA hash-router + 7 tab modules + Canvas charts
   ════════════════════════════════════════════════════════ */

// ── Utils ─────────────────────────────────────────────
const $ = (id) => document.getElementById(id);
const WEEKDAYS = ['Dom','Seg','Ter','Qua','Qui','Sex','Sáb'];

function fmtDate(str) {
  if (!str) return '';
  const d = new Date(str.replace(' ', 'T'));
  return d.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
}

function dayLabel(str) {
  const d = new Date(str + 'T00:00:00');
  const today = new Date();
  today.setHours(0,0,0,0);
  const diff = Math.round((d - today) / 86400000);
  if (diff === 0) return 'HOJE';
  if (diff === 1) return 'AMANHÃ';
  if (diff < 7)  return d.toLocaleDateString('pt-BR', { weekday: 'long' }).toUpperCase();
  return d.toLocaleDateString('pt-BR', { day:'2-digit', month:'short' }).toUpperCase();
}

function isNow(startStr) {
  const s = new Date(startStr.replace(' ','T'));
  const now = new Date();
  return Math.abs(now - s) < 45 * 60 * 1000; // within 45 min
}

function formatMoney(val, unit) {
  if (unit === 'R$') return `R$ ${Number(val).toLocaleString('pt-BR')}`;
  if (unit === '%')  return `${val}%`;
  return `${val}`;
}

// ── Status Bar Clock ──────────────────────────────────
function updateClock() {
  const now = new Date();
  $('sb-time').textContent = now.toLocaleTimeString('pt-BR', { hour:'2-digit', minute:'2-digit' });
  $('sb-date').textContent = now.toLocaleDateString('pt-BR', { weekday:'short', day:'2-digit', month:'short' }).toUpperCase();
}
updateClock();
setInterval(updateClock, 10000);

// ── Router ────────────────────────────────────────────
const tabs = ['home','estudos','projetos','rotina','agenda','stats','financeiro'];
const loaded = {};

function navigate(tab) {
  if (!tabs.includes(tab)) tab = 'home';

  document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.tab === tab);
  });
  const section = document.getElementById('tab-' + tab);
  if (section) section.classList.add('active');

  if (!loaded[tab]) {
    loaded[tab] = true;
    renderTab(tab);
  }

  window.location.hash = tab;
}

document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => navigate(btn.dataset.tab));
});

// ── Boot ──────────────────────────────────────────────
async function boot() {
  // Always render HOME on load
  await renderTab('home');
  loaded['home'] = true;

  const hash = window.location.hash.replace('#','');
  navigate(tabs.includes(hash) ? hash : 'home');
}

async function renderTab(tab) {
  switch(tab) {
    case 'home':       await renderHome();       break;
    case 'estudos':    await renderEstudos();    break;
    case 'projetos':   await renderProjetos();   break;
    case 'rotina':     await renderRotina();     break;
    case 'agenda':     await renderAgenda();     break;
    case 'stats':      await renderStats();      break;
    case 'financeiro': await renderFinanceiro(); break;
  }
}

// ── HOME ─────────────────────────────────────────────
async function renderHome() {
  const [statusRes, manifestoRes, settingsRes] = await Promise.all([
    fetch('/api/status'),
    fetch('/api/manifesto'),
    fetch('/api/settings'),
  ]);
  const status    = await statusRes.json();
  const manifesto = await manifestoRes.json();
  const settings  = await settingsRes.json();

  const c = status.character;
  const s = status.stats;

  // Identity
  $('char-name').textContent  = c.name.toUpperCase();
  $('char-rank').textContent  = c.rank;
  $('char-level').textContent = `LVL ${c.level}`;
  $('streak-count').textContent = c.streak;

  // XP bar (animate after paint)
  setTimeout(() => {
    $('xp-fill').style.width = c.xp_percentage + '%';
    $('xp-label').textContent = `${c.level_xp.toLocaleString()} / ${c.next_level_xp.toLocaleString()} XP`;
  }, 100);

  // Quick stats
  $('qs-notes').textContent  = s.daily_notes_count;
  $('qs-active').textContent = s.active_quests;
  $('qs-done').textContent   = s.completed_quests;
  $('qs-habits').textContent = `${s.habits_today}/${s.habits_total}`;

  // Manifesto
  const ul = $('manifesto-list');
  ul.innerHTML = manifesto.lines.map(l => `<li class="manifesto-line">${l}</li>`).join('');

  // Calendar status
  const googleConfigured = !!settings.google_calendar_ical_url;
  const outlookConfigured = !!settings.outlook_calendar_ical_url;

  $('dot-google').className  = 'status-dot ' + (googleConfigured  ? 'online' : 'offline');
  $('label-google').textContent  = googleConfigured  ? 'conectado' : 'não config.';
  $('dot-outlook').className = 'status-dot ' + (outlookConfigured ? 'online' : 'offline');
  $('label-outlook').textContent = outlookConfigured ? 'conectado' : 'não config.';
}

// ── ESTUDOS ───────────────────────────────────────────
async function renderEstudos() {
  const res  = await fetch('/api/study-plan');
  const data = await res.json();

  if (data.error) {
    $('phases-grid').innerHTML = `<p class="text-muted mono">${data.error}</p>`;
    return;
  }

  $('sp-overall').textContent = `${data.overall_percentage}% OVERALL`;

  const grid = $('phases-grid');
  grid.innerHTML = data.phases.map(phase => {
    const fillClass = phase.percentage >= 90 ? 'done' : phase.percentage > 0 ? 'partial' : 'empty';
    const topicsHtml = phase.topics.slice(0,12).map(t =>
      `<li class="phase-topic ${t.done ? 'done' : 'pending'}">${t.text}</li>`
    ).join('');
    return `
      <div class="phase-card">
        <div class="phase-name mono">&gt; ${phase.name.toUpperCase()}</div>
        <div class="phase-bar-wrap">
          <div class="phase-bar"><div class="phase-fill ${fillClass}" style="width:${phase.percentage}%"></div></div>
          <div class="phase-pct">${phase.done}/${phase.total} tópicos — ${phase.percentage}%</div>
        </div>
        <ul class="phase-topics">${topicsHtml}</ul>
      </div>`;
  }).join('');
}

// ── PROJETOS ──────────────────────────────────────────
async function renderProjetos() {
  const [projRes, questRes] = await Promise.all([
    fetch('/api/projects'),
    fetch('/api/quests'),
  ]);
  const { projects } = await projRes.json();
  const quests       = await questRes.json();

  const board = $('projects-board');
  if (projects.length === 0) {
    board.innerHTML = `<p class="text-muted mono">Nenhum projeto encontrado em 01_Projetos/</p>`;
  } else {
    board.innerHTML = projects.map(p => `
      <div class="project-card">
        <div class="project-name">${p.name}</div>
        <div class="project-meta">
          <span class="project-tasks-open">⬜ ${p.active_tasks} abertas</span>
          <span class="project-tasks-done">✅ ${p.done_tasks} concluídas</span>
        </div>
      </div>`).join('');
  }

  const list = $('quests-active-list');
  if (quests.active.length === 0) {
    list.innerHTML = `<p class="text-muted mono">Sem tarefas abertas no vault.</p>`;
  } else {
    list.innerHTML = quests.active.slice(0, 30).map(q => `
      <div class="quest-item" data-id="${encodeURIComponent(q.id)}" onclick="toggleQuest(this)">
        <div class="quest-checkbox"></div>
        <div>
          <div class="quest-text">${q.text}</div>
          <div class="quest-category">${q.category} // ${q.file}</div>
        </div>
      </div>`).join('');
  }
}

async function toggleQuest(el) {
  const id = decodeURIComponent(el.dataset.id);
  el.style.opacity = '0.5';
  el.style.pointerEvents = 'none';
  try {
    const res  = await fetch('/api/quests/toggle', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ id })
    });
    const data = await res.json();
    if (data.status === 'success') {
      el.classList.toggle('done', data.new_state === 'completed');
      // Refresh XP on HOME if already loaded
      if (loaded['home']) { loaded['home'] = false; renderTab('home'); }
    }
  } finally {
    el.style.opacity   = '';
    el.style.pointerEvents = '';
  }
}

// ── ROTINA ────────────────────────────────────────────
async function renderRotina() {
  const res  = await fetch('/api/habits');
  const data = await res.json();

  $('rotina-streak-count').textContent = data.streak;

  const table = $('habits-table');
  const habits = data.habits_list;

  // Header row: label + weekday columns from first week
  const firstWeek = data.weeks[0];
  let headerHtml = `<thead><tr><th class="ht-label">Hábito</th>`;
  firstWeek.forEach(day => {
    headerHtml += `<th>${day.weekday.toUpperCase()}</th>`;
  });
  headerHtml += `</tr></thead>`;

  // Body: one row per habit, columns = all days across 4 weeks
  let bodyHtml = '<tbody>';
  habits.forEach(habit => {
    bodyHtml += `<tr><td class="ht-label">${habit}</td>`;
    data.weeks.forEach(week => {
      week.forEach(day => {
        const done    = day.habits[habit];
        const today   = day.is_today ? ' ht-today' : '';
        const status  = done ? ' ht-done' : !day.has_note ? ' ht-norecord' : '';
        const icon    = done ? '✓' : day.has_note ? '✗' : '';
        bodyHtml += `<td class="${status}${today}">${icon}</td>`;
      });
    });
    bodyHtml += '</tr>';
  });
  bodyHtml += '</tbody>';

  table.innerHTML = headerHtml + bodyHtml;
}

// ── AGENDA ────────────────────────────────────────────
async function renderAgenda() {
  const res    = await fetch('/api/calendar');
  const events = await res.json();

  const timeline = $('events-timeline');
  if (events.length === 0) {
    timeline.innerHTML = `<p class="text-muted mono">Nenhum evento encontrado.</p>`;
    return;
  }

  // Group by day label
  const groups = {};
  events.forEach(ev => {
    const dateKey = ev.start.split(' ')[0];
    if (!groups[dateKey]) groups[dateKey] = [];
    groups[dateKey].push(ev);
  });

  timeline.innerHTML = Object.entries(groups).map(([dateKey, evs]) => {
    const label = dayLabel(dateKey);
    const cards = evs.map(ev => {
      const srcClass = ev.source && ev.source.toLowerCase().includes('outlook') ? 'source-outlook' : '';
      const nowBadge = isNow(ev.start) ? `<span class="event-now-badge">NOW</span>` : '';
      const joinBtn  = ev.meeting_url
        ? `<a class="event-join-btn" href="${ev.meeting_url}" target="_blank" rel="noopener">JOIN</a>`
        : '';
      return `
        <div class="event-card ${srcClass}">
          <div class="event-summary">${ev.summary} ${nowBadge}</div>
          <div class="event-meta">
            <span>${ev.all_day ? 'Dia inteiro' : ev.start.split(' ')[1]}</span>
            <span class="text-muted">${ev.source}</span>
            ${joinBtn}
          </div>
        </div>`;
    }).join('');
    return `<div class="event-group-label">${label}</div>${cards}`;
  }).join('');
}

// ── STATS (Canvas charts) ─────────────────────────────
async function renderStats() {
  const res  = await fetch('/api/stats');
  const data = await res.json();
  const series = data.series;

  if (!series || series.length === 0) {
    $('xp-chart').parentElement.innerHTML += `<p class="text-muted mono">Sem dados suficientes ainda.</p>`;
    return;
  }

  drawLineChart($('xp-chart'), series.map(s => s.xp), '#60a5fa', 'XP');
  drawBarChart($('habit-chart'), series.map(s => s.habits_pct), '#22d3a0', '%');
}

function drawLineChart(canvas, values, color, label) {
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0,0,W,H);

  const pad = { t:10, r:10, b:30, l:50 };
  const cW = W - pad.l - pad.r;
  const cH = H - pad.t - pad.b;

  const max = Math.max(...values) || 1;
  const step = cW / (values.length - 1);

  // Grid lines
  ctx.strokeStyle = 'rgba(59,130,246,0.1)';
  ctx.lineWidth = 1;
  for (let i=0; i<=4; i++) {
    const y = pad.t + (cH/4)*i;
    ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(W-pad.r, y); ctx.stroke();
    ctx.fillStyle = 'rgba(100,116,139,0.8)';
    ctx.font = '10px JetBrains Mono, monospace';
    ctx.textAlign = 'right';
    ctx.fillText(Math.round(max*(1-i/4)), pad.l-6, y+4);
  }

  // Gradient fill
  const gradient = ctx.createLinearGradient(0, pad.t, 0, H-pad.b);
  gradient.addColorStop(0, color + '55');
  gradient.addColorStop(1, color + '00');

  ctx.beginPath();
  values.forEach((v, i) => {
    const x = pad.l + i * step;
    const y = pad.t + cH - (v/max)*cH;
    i === 0 ? ctx.moveTo(x,y) : ctx.lineTo(x,y);
  });
  const lastX = pad.l + (values.length-1)*step;
  ctx.lineTo(lastX, H-pad.b); ctx.lineTo(pad.l, H-pad.b);
  ctx.closePath();
  ctx.fillStyle = gradient; ctx.fill();

  // Line
  ctx.beginPath();
  ctx.strokeStyle = color; ctx.lineWidth = 2;
  values.forEach((v, i) => {
    const x = pad.l + i * step;
    const y = pad.t + cH - (v/max)*cH;
    i === 0 ? ctx.moveTo(x,y) : ctx.lineTo(x,y);
  });
  ctx.stroke();
}

function drawBarChart(canvas, values, color, label) {
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0,0,W,H);

  const pad = { t:10, r:10, b:30, l:50 };
  const cW = W - pad.l - pad.r;
  const cH = H - pad.t - pad.b;
  const barW = Math.max(2, cW / values.length - 2);

  values.forEach((v, i) => {
    const x = pad.l + i * (cW / values.length);
    const barH = (v/100) * cH;
    const y = pad.t + cH - barH;
    ctx.fillStyle = v > 70 ? color : v > 30 ? '#3b82f6' : '#1d4ed8';
    ctx.beginPath();
    ctx.roundRect(x, y, barW, barH, 2);
    ctx.fill();
  });

  // Y axis labels
  ctx.fillStyle = 'rgba(100,116,139,0.8)';
  ctx.font = '10px JetBrains Mono, monospace';
  ctx.textAlign = 'right';
  ['100%','75%','50%','25%','0%'].forEach((lbl, i) => {
    const y = pad.t + (cH/4)*i;
    ctx.fillText(lbl, pad.l-6, y+4);
  });
}

// ── FINANCEIRO ────────────────────────────────────────
async function renderFinanceiro() {
  const res  = await fetch('/api/financial');
  const data = await res.json();

  const grid = $('financial-grid');
  grid.innerHTML = (data.financial_goals || []).map((g, idx) => {
    const pct = g.target > 0 ? Math.min(100, Math.round((g.current/g.target)*100)) : 0;
    return `
      <div class="financial-card card">
        <div class="financial-label mono">${g.label}</div>
        <div class="financial-value">${formatMoney(g.current, g.unit)}</div>
        <div class="financial-target text-muted">meta: ${formatMoney(g.target, g.unit)}</div>
        <div class="financial-bar-wrap">
          <div class="financial-bar">
            <div class="financial-fill" style="width:${pct}%"></div>
          </div>
          <div class="financial-pct">${pct}% COMPLETO</div>
        </div>
      </div>`;
  }).join('');

  const list = $('career-list');
  list.innerHTML = (data.career_goals || []).map(g => `
    <div class="career-item ${g.done ? 'done' : ''}">
      <span class="career-check">${g.done ? '✅' : '⬜'}</span>
      <span class="career-label">${g.label}</span>
    </div>`).join('');
}

// ── Init ──────────────────────────────────────────────
window.addEventListener('load', boot);
window.addEventListener('hashchange', () => {
  const tab = window.location.hash.replace('#','');
  if (tabs.includes(tab)) navigate(tab);
});
