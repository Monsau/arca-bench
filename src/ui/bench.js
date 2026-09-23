(async function () {
  // Portal-aware API base. Priority: the composed document (portal
  // /module/<key> page) injects window.__ARCA_MODULE_BASE__; standalone
  // dev behind the Suite proxy uses the /m/<module-key>/ location prefix.
  // The browser never carries a token — the portal attaches the SSO Bearer
  // server-side on every proxied call.
  const _injected = window.__ARCA_MODULE_BASE__;
  const _pm = window.location.pathname.match(/^\/m\/([^/]+)\//);
  const API = (_injected || (_pm ? '/m/' + _pm[1] + '/' : '/')) + 'api/v1';

  async function getJSON(path) {
    const r = await fetch(path);
    if (!r.ok) throw new Error(r.statusText);
    return r.json();
  }

  async function postJSON(path, body) {
    const r = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(r.statusText);
    return r.json();
  }

  async function loadTests() {
    const data = await getJSON(`${API}/tests`);
    const list = document.getElementById('tests-list');
    list.innerHTML = '';
    data.tests.forEach(t => {
      const li = document.createElement('li');
      li.textContent = `${t.name} (${t.category}) — ${t.id}`;
      list.appendChild(li);
    });
  }

  // Shared-skin tag classes per run status.
  const RUN_STATUS_TAG = {
    completed: 'tag ok',
    failed: 'tag error',
    started: 'tag state-submitted',
  };

  function fmtDuration(ms) {
    if (ms == null || !isFinite(ms) || ms < 0) return '—';
    if (ms < 1000) return `${Math.round(ms)} ms`;
    return `${(ms / 1000).toFixed(1)} s`;
  }

  // Column sparkline of recent run durations, drawn only from the real
  // /runs payload (started_at/completed_at on completed runs).
  function runDurationsSvg(runs, maxRuns = 12) {
    const timed = runs
      .filter(r => r.started_at && r.completed_at)
      .slice(0, maxRuns)
      .map(r => ({
        id: r.run_id,
        status: r.status,
        ms: new Date(r.completed_at) - new Date(r.started_at),
      }))
      .filter(d => d.ms >= 0);
    if (timed.length < 2) return ''; // not enough real timing data
    const max = Math.max(...timed.map(d => d.ms)) || 1;
    const colW = 22;
    const height = 56;
    const width = timed.length * colW + 8;
    const bars = timed.map((d, i) => {
      const h = Math.max(2, (d.ms / max) * (height - 18));
      const x = 4 + i * colW + 3;
      const y = height - 12 - h;
      const fill = d.status === 'failed' ? 'var(--error)'
        : d.status === 'completed' ? 'var(--accent-primary)' : 'var(--text-tertiary)';
      return `<rect x="${x}" y="${y.toFixed(1)}" width="${colW - 6}" height="${h.toFixed(1)}" rx="2" fill="${fill}">` +
        `<title>${d.id.slice(0, 8)}… · ${d.status} · ${fmtDuration(d.ms)}</title></rect>`;
    }).join('');
    return `<div class="muted">Recent run durations</div>` +
      `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Recent run durations">` +
      `${bars}<text x="4" y="${height - 2}" fill="var(--text-tertiary)" font-size="8" font-family="inherit">max ${fmtDuration(max)}</text></svg>`;
  }

  async function loadRuns() {
    const data = await getJSON(`${API}/runs`);
    const tbody = document.querySelector('#runs-table tbody');
    tbody.innerHTML = '';
    data.runs.forEach(r => {
      const duration = r.completed_at
        ? fmtDuration(new Date(r.completed_at) - new Date(r.started_at))
        : '—';
      const row = document.createElement('tr');
      row.innerHTML = `
        <td>${r.target}</td>
        <td><span class="${RUN_STATUS_TAG[r.status] || 'tag'}">${r.status}</span></td>
        <td>${duration}</td>
        <td>${new Date(r.started_at).toLocaleString()}</td>
        <td class="muted">${r.run_id}</td>
      `;
      row.onclick = () => loadRunDetails(r.run_id);
      tbody.appendChild(row);
    });
    document.getElementById('run-durations').innerHTML = runDurationsSvg(data.runs);
  }

  // Horizontal bar chart for a {dimension: score 0..1} map (scorecards).
  function barsSvg(dimensions) {
    const entries = Object.entries(dimensions || {});
    if (!entries.length) return '';
    const rowH = 24;
    const labelW = 150;
    const valueW = 44;
    const width = 460;
    const barW = width - labelW - valueW - 16;
    const height = entries.length * rowH + 4;
    const rows = entries.map(([name, raw], i) => {
      const v = Math.max(0, Math.min(1, Number(raw) || 0));
      const y = i * rowH + 6;
      const barH = 12;
      return `
      <text x="${labelW - 8}" y="${y + barH - 1}" text-anchor="end"
            fill="var(--text-secondary)" font-size="10"
            font-family="inherit">${name}</text>
      <rect x="${labelW}" y="${y}" width="${barW}" height="${barH}" rx="3"
            fill="var(--bg-hover)" />
      <rect x="${labelW}" y="${y}" width="${(v * barW).toFixed(1)}" height="${barH}" rx="3"
            fill="var(--accent-primary)" />
      <text x="${labelW + barW + 8}" y="${y + barH - 1}"
            fill="var(--text-primary)" font-size="10" font-weight="600"
            font-family="inherit">${v.toFixed(2)}</text>`;
    }).join('');
    return `<div class="bar-chart"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Scorecard dimension bars">${rows}</svg></div>`;
  }

  // Field table that lists every key of a flat object — no payload field
  // is ever dropped from the view.
  function fieldsTable(obj) {
    const rows = Object.entries(obj || {}).map(([k, v]) => `
      <tr><td class="muted">${k}</td><td>${v == null ? '—' : v}</td></tr>`).join('');
    return `<table>${rows}</table>`;
  }

  // Structured scorecard view: SVG dimension bars + every payload field.
  function renderScorecard(scorecard) {
    const view = document.getElementById('scorecard-view');
    if (!scorecard || scorecard.error || scorecard.dimensions == null) {
      view.textContent = 'Scorecard not available for this run.';
      return;
    }
    view.innerHTML = `
      <div class="muted">Overall ${(Number(scorecard.overall) || 0).toFixed(2)} · target ${scorecard.target}</div>
      ${barsSvg(scorecard.dimensions)}
      <details><summary class="muted">All fields</summary>${fieldsTable(scorecard)}</details>
    `;
  }

  // Structured report view: the report content is a JSON document string;
  // parse it and render panels, keeping every field visible (raw fallback
  // preserves anything unexpected).
  function renderReport(report) {
    const view = document.getElementById('report-view');
    if (!report || report.error || !report.content) {
      view.textContent = 'Report not available for this run.';
      return;
    }
    let payload = null;
    try { payload = JSON.parse(report.content); } catch (e) { /* keep raw fallback */ }
    if (!payload || typeof payload !== 'object') {
      view.innerHTML = `<pre class="message raw">${report.content}</pre>`;
      return;
    }
    const remediations = Array.isArray(payload.remediations) ? payload.remediations : [];
    const remRows = remediations.map(r => `
      <tr>
        <td class="severity-${r.severity}">${r.severity}</td>
        <td>${r.finding}</td>
        <td>${r.action}</td>
        <td class="muted">${r.test_case_id}</td>
      </tr>`).join('');
    view.innerHTML = `
      <div class="muted">Run ${payload.run_id} · target ${payload.target} · status ${payload.status}</div>
      ${payload.scorecard ? barsSvg(payload.scorecard.dimensions) : ''}
      <h2>Remediations</h2>
      <table>
        <thead><tr><th>Severity</th><th>Finding</th><th>Action</th><th>Test case</th></tr></thead>
        <tbody>${remRows || '<tr><td colspan="4">No remediations</td></tr>'}</tbody>
      </table>
      <details><summary class="muted">Report envelope fields</summary>${fieldsTable(report)}</details>
    `;
  }

  async function loadRunDetails(runId) {
    const [scorecard, report] = await Promise.all([
      getJSON(`${API}/scorecards/${runId}`).catch(() => ({ error: 'not found' })),
      getJSON(`${API}/runs/${runId}/report?format=json`).catch(() => ({ error: 'not found' })),
    ]);
    renderScorecard(scorecard);
    renderReport(report);
  }

  document.getElementById('register-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    await postJSON(`${API}/tests`, {
      name: fd.get('name'),
      category: fd.get('category'),
    });
    e.target.reset();
    await loadTests();
  });

  document.getElementById('run-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    await postJSON(`${API}/runs`, {
      target: fd.get('target'),
      suite: fd.get('suite').split(',').map(s => s.trim()).filter(Boolean),
    });
    e.target.reset();
    await loadRuns();
  });

  await loadTests();
  await loadRuns();
})();
