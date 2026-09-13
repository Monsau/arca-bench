(async function () {
  const API = '/api/v1';

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

  async function loadRuns() {
    const data = await getJSON(`${API}/runs`);
    const list = document.getElementById('runs-list');
    list.innerHTML = '';
    data.runs.forEach(r => {
      const li = document.createElement('li');
      li.textContent = `${r.target}: ${r.status} — ${r.run_id}`;
      li.onclick = () => loadRunDetails(r.run_id);
      list.appendChild(li);
    });
  }

  async function loadRunDetails(runId) {
    const [scorecard, report] = await Promise.all([
      getJSON(`${API}/scorecards/${runId}`).catch(() => ({ error: 'not found' })),
      getJSON(`${API}/runs/${runId}/report?format=json`).catch(() => ({ error: 'not found' })),
    ]);
    document.getElementById('scorecard-view').textContent = JSON.stringify(scorecard, null, 2);
    document.getElementById('report-view').textContent = JSON.stringify(report, null, 2);
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
