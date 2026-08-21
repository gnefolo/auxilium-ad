document.addEventListener('DOMContentLoaded', () => {
  // In locale punta al backend locale; in produzione va sostituito con l'URL reale
  // del servizio Render (es. https://auxilium-backend.onrender.com/api).
  const API_BASE = (location.hostname === 'localhost' || location.hostname === '127.0.0.1')
    ? 'http://127.0.0.1:8005/api'
    : 'https://auxilium-backend-lq7s.onrender.com/api';

  // ------------------------------------------------------------------
  // Autenticazione
  // ------------------------------------------------------------------
  const TOKEN_KEY = 'auxilium_token';
  const getToken = () => localStorage.getItem(TOKEN_KEY);
  const setToken = (t) => localStorage.setItem(TOKEN_KEY, t);
  const clearToken = () => localStorage.removeItem(TOKEN_KEY);

  function showLogin() {
    document.getElementById('loginScreen').style.display = 'flex';
    document.getElementById('appRoot').style.display = 'none';
  }

  function showApp() {
    document.getElementById('loginScreen').style.display = 'none';
    document.getElementById('appRoot').style.display = 'flex';
  }

  async function apiFetch(url, options = {}) {
    const token = getToken();
    const headers = Object.assign({}, options.headers || {}, token ? { Authorization: `Bearer ${token}` } : {});
    const res = await fetch(url, Object.assign({}, options, { headers }));
    if (res.status === 401) {
      clearToken();
      showLogin();
      throw new Error('Sessione non valida, effettua di nuovo il login.');
    }
    return res;
  }

  document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = document.getElementById('loginUsername').value;
    const password = document.getElementById('loginPassword').value;
    const errorEl = document.getElementById('loginError');
    errorEl.textContent = '';
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      if (!res.ok) {
        errorEl.textContent = 'Credenziali non valide.';
        return;
      }
      const data = await res.json();
      setToken(data.token);
      showApp();
      initDashboard();
    } catch (err) {
      errorEl.textContent = 'Impossibile contattare il server. Riprova.';
    }
  });

  if (getToken()) {
    showApp();
  } else {
    showLogin();
  }

  // Palette Auxilium per i grafici (coerente con style.css)
  const COLOR_GREEN = '#8DB600';
  const COLOR_GREEN_D = '#2D7A18';
  const COLOR_NAVY = '#003A70';
  const COLOR_MUTED = '#4A5468';
  const COLOR_GRID = '#EDF0F5';

  Chart.defaults.color = COLOR_MUTED;
  Chart.defaults.font.family = "'Open Sans', sans-serif";

  const apiStatusDot = document.getElementById('apiStatusDot');
  const apiStatusText = document.getElementById('apiStatusText');
  const pageTitle = document.getElementById('pageTitle');
  const pageSubtitle = document.getElementById('pageSubtitle');

  const PAGE_META = {
    overview: ['Executive Overview', 'Sintesi delle performance aziendali aggiornata in tempo reale.'],
    gare: ['Gare & Appalti', 'Storico commesse dell\'Elenco Servizi Auxilium, 2015-2024.'],
    footprint: ['Footprint (SAM)', 'Bilanci e impatto macroeconomico diretto, indiretto e indotto, per entità.'],
    sroi: ['SROI', 'SROI delle commesse attive di Auxilium, per cluster di servizio, e qualità dei dati di monitoraggio disponibili.'],
    sroicalc: ['Calcolo SROI', 'Stima lo SROI di un NUOVO progetto/bando per la Relazione Tecnica: benefici allineati al cluster, deadweight, attribution e drop-off (metodologia SROI Network).'],
    territorio: ['Territorio', 'Mappa dei siti e valore delle commesse per territorio, dati reali dell\'Elenco Servizi.'],
    anomalie: ['Anomalie', 'Deviazioni statistiche reali rispetto alla media storica delle commesse.'],
    relazione: ['Genera Relazione', 'Bozza di Relazione Tecnica con track record, impatto SAM e KPI di monitoraggio per un profilo di bando.'],
    settings: ['Impostazioni', 'Stato del progetto, fonti dei dati e limiti metodologici.'],
  };

  let sroiClusterChartInstance = null;
  let financeChartInstance = null;
  let samChartInstance = null;
  let relSamChartInstance = null;

  let currentServiceRevenueData = [];
  let allServiceRevenueRows = null; // cache per pagina "Gare & Appalti"
  let allServices = null; // cache /api/services (per liste cluster)
  let allEntities = null; // cache /api/entities
  let allSites = null; // cache /api/sites

  function formatEUR(value) {
    if (value === null || value === undefined) return 'N/D';
    return new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(value);
  }

  function formatPct(value) {
    if (value === null || value === undefined) return 'N/D';
    return `${(value * 100).toFixed(1)}%`;
  }

  function formatNumber(value, decimals = 0) {
    if (value === null || value === undefined) return 'N/D';
    return new Intl.NumberFormat('it-IT', { maximumFractionDigits: decimals }).format(value);
  }

  // ------------------------------------------------------------------
  // Navigazione tra pagine
  // ------------------------------------------------------------------
  function showPage(pageKey) {
    document.querySelectorAll('.page').forEach(el => el.classList.remove('active'));
    document.getElementById(`page-${pageKey}`).classList.add('active');

    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
    document.querySelector(`.nav-item[data-page="${pageKey}"]`).classList.add('active');

    const [title, subtitle] = PAGE_META[pageKey];
    pageTitle.textContent = title;
    pageSubtitle.textContent = subtitle;

    if (pageKey === 'gare') loadGarePage();
    if (pageKey === 'footprint') loadFootprintPage();
    if (pageKey === 'sroi') loadSroiPage();
    if (pageKey === 'relazione') loadRelazionePage();
    if (pageKey === 'sroicalc') loadSroiCalcPage();
    if (pageKey === 'territorio') loadTerritorioPage();
    if (pageKey === 'anomalie') loadAnomaliePage();
  }

  document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      showPage(item.dataset.page);
    });
  });

  // ------------------------------------------------------------------
  // Dati condivisi (entità, servizi/cluster, siti)
  // ------------------------------------------------------------------
  async function ensureEntities() {
    if (allEntities) return allEntities;
    const res = await apiFetch(`${API_BASE}/entities`);
    allEntities = await res.json();
    return allEntities;
  }

  async function ensureServices() {
    if (allServices) return allServices;
    const res = await apiFetch(`${API_BASE}/services`);
    allServices = await res.json();
    return allServices;
  }

  async function ensureSites() {
    if (allSites) return allSites;
    const res = await apiFetch(`${API_BASE}/sites`);
    allSites = await res.json();
    return allSites;
  }

  function distinctClusters(services) {
    return [...new Set(services.map(s => s.ServiceCluster))].sort();
  }

  // ------------------------------------------------------------------
  // PAGE: Overview
  // ------------------------------------------------------------------
  async function fetchOverview() {
    try {
      const kpiRes = await apiFetch(`${API_BASE}/kpis`);
      if (!kpiRes.ok) throw new Error('API Error');
      const kpiData = await kpiRes.json();
      updateKPIs(kpiData);

      const impactRes = await apiFetch(`${API_BASE}/impact`);
      const impactData = await impactRes.json();
      updateOverviewImpact(impactData);

      apiStatusDot.classList.add('connected');
      apiStatusText.textContent = 'Live Data Connected';
    } catch (error) {
      console.error('Failed to fetch overview data:', error);
      apiStatusDot.classList.remove('connected');
      apiStatusText.textContent = 'Connection Failed';
    }
  }

  function setAlertState(cardId, level) {
    const card = document.getElementById(cardId);
    card.classList.remove('alert-warn', 'alert-critical');
    if (level) card.classList.add(level);
  }

  function updateKPIs(data) {
    if (!data.year) {
      document.getElementById('valRevenue').textContent = 'N/D';
      return;
    }
    document.getElementById('valRevenue').textContent = data.totalServiceRevenue.value;
    document.getElementById('trendRevenue').textContent = data.totalServiceRevenue.trend;
    const revenueTrendPct = parseFloat(data.totalServiceRevenue.trend);
    setAlertState('kpiCardRevenue', revenueTrendPct < -5 ? 'alert-warn' : null);

    document.getElementById('valMargin').textContent = data.operatingMargin.value;
    document.getElementById('trendMargin').textContent = data.operatingMargin.note || data.operatingMargin.trend;
    const marginPct = parseFloat(data.operatingMargin.value);
    setAlertState('kpiCardMargin', marginPct < 0 ? 'alert-critical' : (marginPct < 2 ? 'alert-warn' : null));

    document.getElementById('valTenders').textContent = data.activeContracts.value;
    document.getElementById('trendTenders').textContent = 'commesse attive ' + data.year;

    document.getElementById('valWinRate').textContent = data.committenti.value;
    document.getElementById('trendWinRate').textContent = 'enti committenti ' + data.year;
  }

  function updateOverviewImpact(data) {
    const clusters = [...(data.clusters || [])].sort((a, b) => b.investmentCostEUR - a.investmentCostEUR);
    const labels = clusters.map(c => c.cluster);
    const values = clusters.map(c => c.investmentCostEUR);

    if (sroiClusterChartInstance) sroiClusterChartInstance.destroy();
    const ctx = document.getElementById('sroiChart').getContext('2d');
    sroiClusterChartInstance = new Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: 'Valore commesse EUR',
          data: values,
          backgroundColor: COLOR_GREEN,
          borderRadius: 6,
          maxBarThickness: 28,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: 'y',
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: (c) => formatEUR(c.parsed.x) } },
        },
        scales: {
          x: { beginAtZero: true, grid: { color: COLOR_GRID }, border: { display: false } },
          y: { grid: { display: false }, border: { display: false } },
        },
      },
    });

    const top = clusters.slice(0, 5);
    const totalValue = clusters.reduce((s, c) => s + c.investmentCostEUR, 0);
    const list = document.getElementById('topClustersList');
    list.innerHTML = top.map((c, i) => `
      <div class="stat-row ranked">
        <span class="stat-label"><span class="rank-badge">${i + 1}</span>${c.cluster}</span>
        <span class="stat-value accent">${formatEUR(c.investmentCostEUR)}</span>
      </div>
    `).join('') + `
      <div class="stat-row">
        <span class="stat-label">Totale (${data.year})</span>
        <span class="stat-value">${formatEUR(totalValue)}</span>
      </div>
    `;
  }

  // ------------------------------------------------------------------
  // PAGE: Gare & Appalti
  // ------------------------------------------------------------------
  async function loadGarePage() {
    const yearSelect = document.getElementById('filterYear');
    const clusterSelect = document.getElementById('filterCluster');
    const statusSelect = document.getElementById('filterStatus');

    if (!allServiceRevenueRows) {
      const res = await apiFetch(`${API_BASE}/service-revenue`);
      allServiceRevenueRows = await res.json();

      const years = [...new Set(allServiceRevenueRows.map(r => r.year))].sort((a, b) => b - a);
      yearSelect.innerHTML = '<option value="">Tutti gli anni</option>' +
        years.map(y => `<option value="${y}">${y}</option>`).join('');
      yearSelect.value = years[0] || '';

      const services = await ensureServices();
      const clusters = distinctClusters(services);
      clusterSelect.innerHTML = '<option value="">Tutti</option>' +
        clusters.map(c => `<option value="${c}">${c}</option>`).join('');

      [yearSelect, clusterSelect, statusSelect].forEach(sel => sel.addEventListener('change', renderGareTable));
    }
    renderGareTable();
  }

  function renderGareTable() {
    const year = document.getElementById('filterYear').value;
    const cluster = document.getElementById('filterCluster').value;
    const status = document.getElementById('filterStatus').value;

    let rows = allServiceRevenueRows || [];
    if (year) rows = rows.filter(r => String(r.year) === String(year));
    if (cluster) rows = rows.filter(r => r.cluster === cluster);
    if (status) rows = rows.filter(r => r.status === status);
    rows = [...rows].sort((a, b) => b.revenueEUR - a.revenueEUR);

    currentServiceRevenueData = rows;

    const tbody = document.getElementById('gareBody');
    tbody.innerHTML = '';
    if (rows.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="text-center">Nessuna commessa per i filtri selezionati</td></tr>';
      return;
    }
    rows.forEach(r => {
      const statusClass = r.status === 'In essere' ? 'win' : 'eval';
      const row = document.createElement('tr');
      row.innerHTML = `
        <td style="font-family: var(--font-mono); color: var(--text-muted)">${r.site}</td>
        <td style="font-weight: 600">${r.contractName}<br><span style="color: var(--text-muted); font-size: 0.85em; font-weight: 400;">${r.enteCommittente}</span></td>
        <td style="font-family: var(--font-mono)">${formatEUR(r.revenueEUR)}</td>
        <td>${r.regione || ''}</td>
        <td><span class="status-badge ${statusClass}">${r.status}</span></td>
        <td style="font-family: var(--font-mono); color: var(--green-d)">${r.cluster}</td>
      `;
      tbody.appendChild(row);
    });
  }

  // ------------------------------------------------------------------
  // PAGE: Footprint (SAM)
  // ------------------------------------------------------------------
  let benchmarkRadarChartInstance = null;

  async function loadFootprintPage() {
    const entitySelect = document.getElementById('entitySelect');
    if (!entitySelect.dataset.loaded) {
      const entities = await ensureEntities();
      entitySelect.innerHTML = entities.map(e => `<option value="${e.EntityKey}">${e.EntityName}</option>`).join('');
      entitySelect.dataset.loaded = '1';
      entitySelect.addEventListener('change', () => {
        loadEntityFootprint(entitySelect.value);
        loadBenchmark(entitySelect.value);
      });

      document.getElementById('simulatorToggle').addEventListener('click', () => {
        const body = document.getElementById('simulatorBody');
        const open = body.style.display !== 'none';
        body.style.display = open ? 'none' : 'block';
        document.getElementById('simulatorChevron').textContent = open ? '▼ Apri' : '▲ Chiudi';
      });
      document.getElementById('simRunBtn').addEventListener('click', runScenarioSimulation);

      loadEntityFootprint(entitySelect.value);
      loadBenchmark(entitySelect.value);
    }
  }

  async function runScenarioSimulation() {
    const amount = parseFloat(document.getElementById('simAmount').value) || 0;
    const branch = document.getElementById('simBranch').value;
    const res = await apiFetch(`${API_BASE}/sam/simulate?amount_eur=${amount}&branch_code=${branch}`);
    const data = await res.json();
    document.getElementById('simResults').innerHTML = `
      <div class="stat-row"><span class="stat-label">Output attivato — Tipo I</span><span class="stat-value">${formatEUR(data.type1_leontief.deltaOutputEUR)}</span></div>
      <div class="stat-row"><span class="stat-label">Output attivato — Tipo II (con indotto)</span><span class="stat-value accent">${formatEUR(data.type2_sam.deltaOutputEUR)}</span></div>
      <div class="stat-row"><span class="stat-label">Valore Aggiunto attivato — Tipo I</span><span class="stat-value">${formatEUR(data.type1_leontief.deltaValueAddedEUR)}</span></div>
      <div class="stat-row"><span class="stat-label">Valore Aggiunto attivato — Tipo II</span><span class="stat-value accent">${formatEUR(data.type2_sam.deltaValueAddedEUR)}</span></div>
      <div class="stat-row"><span class="stat-label">Posti equivalenti — Tipo I / Tipo II</span><span class="stat-value">${formatNumber(data.type1_leontief.deltaJobsEquivalent, 1)} / ${formatNumber(data.type2_sam.deltaJobsEquivalent, 1)}</span></div>
      <div class="stat-row"><span class="stat-label">Moltiplicatore Tipo I / Tipo II</span><span class="stat-value">${data.type1_leontief.outputMultiplier.toFixed(2)}x / ${data.type2_sam.outputMultiplier.toFixed(2)}x</span></div>
    `;
  }

  async function loadBenchmark(entityKey) {
    const res = await apiFetch(`${API_BASE}/sam/benchmark?entity_key=${entityKey}&year=2025`);
    const data = await res.json();
    document.getElementById('benchmarkNote').textContent = data.sourceNote || '';

    const rows = [
      { label: 'Ricavi per FTE', fmt: formatEUR, key: 'ricaviPerFTE' },
      { label: 'Costo personale / Ricavi', fmt: formatPct, key: 'costoPersonalePctRicavi' },
      { label: 'Margine EBITDA (proxy)', fmt: formatPct, key: 'margineEbitdaPctRicavi' },
      { label: 'Valore Aggiunto / Ricavi', fmt: formatPct, key: 'valoreAggiuntoPctRicavi' },
      { label: 'FTE per M€ ricavi', fmt: (v) => formatNumber(v, 1), key: 'ftePerMilioneRicavi' },
    ];

    document.getElementById('benchmarkTableBody').innerHTML = rows.map(r => {
      const a = data.auxilium[r.key];
      const s = data.sector[r.key];
      const delta = (a !== null && a !== undefined && s) ? ((a - s) / s) * 100 : null;
      const deltaHtml = delta !== null ? `<span style="color:${delta >= 0 ? 'var(--green-d)' : 'var(--red-d)'}">${delta >= 0 ? '+' : ''}${delta.toFixed(1)}%</span>` : 'N/D';
      return `<tr><td style="font-weight:600">${r.label}</td><td>${a !== null && a !== undefined ? r.fmt(a) : 'N/D'}</td><td>${s !== null && s !== undefined ? r.fmt(s) : 'N/D'}</td><td>${deltaHtml}</td></tr>`;
    }).join('');

    if (benchmarkRadarChartInstance) benchmarkRadarChartInstance.destroy();
    const normalize = (key) => {
      const s = data.sector[key];
      return s ? (data.auxilium[key] / s) * 100 : 0;
    };
    const ctx = document.getElementById('benchmarkRadarChart').getContext('2d');
    benchmarkRadarChartInstance = new Chart(ctx, {
      type: 'radar',
      data: {
        labels: rows.map(r => r.label),
        datasets: [
          { label: 'Settore = 100', data: rows.map(() => 100), borderColor: COLOR_NAVY, backgroundColor: 'transparent', pointRadius: 0 },
          { label: 'Auxilium', data: rows.map(r => normalize(r.key)), borderColor: COLOR_GREEN, backgroundColor: 'rgba(141,182,0,0.2)' },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: { r: { beginAtZero: true, grid: { color: COLOR_GRID } } },
      },
    });
  }

  async function loadEntityFootprint(entityKey) {
    const year = 2025;
    document.getElementById('financeYearBadge').textContent = `Bilancio ${year}`;

    const [financeRes, samRes] = await Promise.all([
      apiFetch(`${API_BASE}/finance?entity_key=${entityKey}&year=${year}`),
      apiFetch(`${API_BASE}/sam/footprint?entity_key=${entityKey}&year=${year}`),
    ]);
    const financeRows = await financeRes.json();
    const samData = await samRes.json();

    renderFinance(financeRows);
    renderSam(samData);
  }

  function financeValue(rows, category) {
    const row = rows.find(r => r.costCategory === category);
    if (!row) return null;
    return row.revenueEUR !== null ? row.revenueEUR : row.costEUR;
  }

  function renderFinance(rows) {
    const b6 = financeValue(rows, 'B6_MateriePrime') || 0;
    const b7 = financeValue(rows, 'B7_Servizi') || 0;
    const b8 = financeValue(rows, 'B8_GodimentoBeniTerzi') || 0;
    const salari = financeValue(rows, 'B9_Personale_Salari') || 0;
    const oneriSociali = financeValue(rows, 'B9_Personale_OneriSociali') || 0;
    const tfr = (financeValue(rows, 'B9_Personale_TFR') || 0) + (financeValue(rows, 'B9_Personale_TFR_Altri') || 0);
    const b10 = financeValue(rows, 'B10_Ammortamenti') || 0;
    const b14 = financeValue(rows, 'B14_OneriDiversi') || 0;
    const valoreProduzione = financeValue(rows, 'A_ValoreProduzione');
    const totaleCostiB = financeValue(rows, 'Totale_CostiProduzione_B');
    const risultato = financeValue(rows, 'Risultato_Esercizio');

    if (financeChartInstance) financeChartInstance.destroy();
    const ctx = document.getElementById('financeChart').getContext('2d');
    financeChartInstance = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: ['Materie prime', 'Servizi', 'Godimento beni terzi', 'Salari', 'Oneri sociali', 'TFR', 'Ammortamenti', 'Oneri diversi'],
        datasets: [{
          label: 'Costo EUR',
          data: [b6, b7, b8, salari, oneriSociali, tfr, b10, b14],
          backgroundColor: COLOR_NAVY,
          borderRadius: 6,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: (c) => formatEUR(c.parsed.y) } },
        },
        scales: {
          y: { beginAtZero: true, grid: { color: COLOR_GRID } },
          x: { grid: { display: false } },
        },
      },
    });

    const summary = document.getElementById('financeSummary');
    summary.innerHTML = `
      <div class="stat-row"><span class="stat-label">Valore della produzione</span><span class="stat-value accent">${formatEUR(valoreProduzione)}</span></div>
      <div class="stat-row"><span class="stat-label">Totale costi (voce B)</span><span class="stat-value">${formatEUR(totaleCostiB)}</span></div>
      <div class="stat-row"><span class="stat-label">Risultato d'esercizio</span><span class="stat-value">${formatEUR(risultato)}</span></div>
      <div class="stat-row"><span class="stat-label">Margine operativo</span><span class="stat-value accent">${valoreProduzione && totaleCostiB !== null ? formatPct((valoreProduzione - totaleCostiB) / valoreProduzione) : 'N/D'}</span></div>
    `;
  }

  function renderSam(data) {
    const note = document.getElementById('samMethodNote');
    if (data.error) {
      note.textContent = data.error;
      document.getElementById('samSummary').innerHTML = '';
      if (samChartInstance) { samChartInstance.destroy(); samChartInstance = null; }
      return;
    }
    note.textContent = (data.impact && data.impact.methodologyNote) || '';

    const direct = data.direct;
    const total = data.total;

    if (samChartInstance) samChartInstance.destroy();
    const ctx = document.getElementById('samChart').getContext('2d');
    const labels = ['Diretto', 'Totale Tipo I (+fornitori)', 'Totale Tipo II (+indotto famiglie)'];
    const outputSeries = [direct.outputEUR, total ? total.type1_leontief.outputEUR : null, total ? total.type2_sam.outputEUR : null];
    const vaSeries = [direct.valueAddedEUR, total ? total.type1_leontief.valueAddedEUR : null, total ? total.type2_sam.valueAddedEUR : null];

    samChartInstance = new Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: [
          { label: 'Output EUR', data: outputSeries, backgroundColor: COLOR_GREEN, borderRadius: 6 },
          { label: 'Valore Aggiunto EUR', data: vaSeries, backgroundColor: COLOR_NAVY, borderRadius: 6 },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${formatEUR(c.parsed.y)}` } },
        },
        scales: {
          y: { beginAtZero: true, grid: { color: COLOR_GRID } },
          x: { grid: { display: false } },
        },
      },
    });

    const directBox = document.getElementById('samDirectStats');
    const indirectBox = document.getElementById('samIndirectStats');
    const inducedBox = document.getElementById('samInducedStats');

    directBox.innerHTML = `
      <div class="stat-row"><span class="stat-label">Output</span><span class="stat-value">${formatEUR(direct.outputEUR)}</span></div>
      <div class="stat-row"><span class="stat-label">Valore Aggiunto</span><span class="stat-value">${formatEUR(direct.valueAddedEUR)}</span></div>
      <div class="stat-row"><span class="stat-label">Dipendenti (esatto)</span><span class="stat-value">${formatNumber(direct.employees)}</span></div>
    `;

    if (!total) {
      indirectBox.innerHTML = '<div class="stat-row"><span class="stat-label">Nessuna spesa intermedia registrata.</span></div>';
      inducedBox.innerHTML = '<div class="stat-row"><span class="stat-label">Non calcolabile.</span></div>';
      return;
    }

    indirectBox.innerHTML = `
      <div class="stat-row"><span class="stat-label">Output attivato</span><span class="stat-value">${formatEUR(data.impact.type1_leontief.deltaOutputEUR)}</span></div>
      <div class="stat-row"><span class="stat-label">Valore Aggiunto attivato</span><span class="stat-value">${formatEUR(data.impact.type1_leontief.deltaValueAddedEUR)}</span></div>
      <div class="stat-row"><span class="stat-label">Posti equivalenti</span><span class="stat-value">${formatNumber(total.type1_leontief.jobsEquivalent_indirectOnly, 1)}</span></div>
      <div class="stat-row"><span class="stat-label">Moltiplicatore output</span><span class="stat-value">${data.impact.type1_leontief.outputMultiplier.toFixed(2)}x</span></div>
    `;

    inducedBox.innerHTML = `
      <div class="stat-row"><span class="stat-label">Output indotto puro</span><span class="stat-value">${formatEUR(data.impact.inducedEffectOnly.deltaOutputEUR)}</span></div>
      <div class="stat-row"><span class="stat-label">Valore Aggiunto indotto puro</span><span class="stat-value">${formatEUR(data.impact.inducedEffectOnly.deltaValueAddedEUR)}</span></div>
      <div class="stat-row"><span class="stat-label">Posti equivalenti (Tot. Tipo II)</span><span class="stat-value">${formatNumber(total.type2_sam.jobsEquivalent_indirectPlusInduced, 1)}</span></div>
      <div class="stat-row"><span class="stat-label">Moltiplicatore output Tipo II</span><span class="stat-value accent">${data.impact.type2_sam.outputMultiplier.toFixed(2)}x</span></div>
    `;
  }

  // ------------------------------------------------------------------
  // PAGE: SROI
  // ------------------------------------------------------------------
  function kpiStatusBadge(status) {
    const cls = status === 'calcolabile_oggi' ? 'kpi-ok' : 'kpi-pending';
    const label = status === 'calcolabile_oggi' ? 'Calcolabile oggi' : 'Richiede monitoraggio';
    return `<span class="status-badge ${cls}">${label}</span>`;
  }

  function fillKpiTable(tbodySelector, items, cols) {
    const tbody = document.querySelector(`${tbodySelector} tbody`);
    tbody.innerHTML = items.map(item => `
      <tr>
        <td style="font-weight:600">${item.nome}</td>
        <td style="font-family: var(--font-mono); color: var(--text-muted)">${item.unita || ''}</td>
        <td style="color: var(--text-muted); font-size: 0.9em">${cols === 'target' ? (item.targetRiferimento || '-') : item.definizione}</td>
        <td>${kpiStatusBadge(item.status)}</td>
      </tr>
    `).join('');
  }

  async function loadSroiPage() {
    const clusterSelect = document.getElementById('clusterSelect');
    if (!clusterSelect.dataset.loaded) {
      const services = await ensureServices();
      const clusters = distinctClusters(services);
      clusterSelect.innerHTML = clusters.map(c => `<option value="${c}">${c}</option>`).join('');
      clusterSelect.dataset.loaded = '1';
      clusterSelect.addEventListener('change', () => loadClusterSroi(clusterSelect.value));

      document.getElementById('outcomeSaveBtn').addEventListener('click', saveOutcome);

      loadClusterSroi(clusterSelect.value);
    }
  }

  const SROI_YEAR = 2024;

  async function loadClusterSroi(cluster) {
    const res = await apiFetch(`${API_BASE}/sroi/framework?cluster=${cluster}&year=${SROI_YEAR}`);
    const data = await res.json();
    renderSroi(data);
  }

  const CONFIDENCE_BADGE_CLASS = { ALTA: 'kpi-ok', MEDIA: 'prep', BASSA: 'kpi-pending' };

  function confidenceBadge(level) {
    const cls = CONFIDENCE_BADGE_CLASS[level] || 'kpi-pending';
    return `<span class="status-badge ${cls}">${level || 'N/D'}</span>`;
  }

  function benefitRowHtml(b) {
    return `
      <tr class="benefit-ref-row" data-benefit-index="${b.benefitIndex}">
        <td>
          <div style="font-weight:600;">${escapeHtml(b.title)}</div>
          <div style="font-size:11px; color: var(--text-muted);">${escapeHtml(b.category)} · ${escapeHtml(b.unit)}</div>
          <div style="font-size:10.5px; color: var(--text-muted); margin-top:2px;">${escapeHtml(b.source)}</div>
        </td>
        <td style="color: var(--text-muted); font-size:0.9em;">${escapeHtml(b.stakeholder || '-')}</td>
        <td style="font-family: var(--font-mono);">${formatEUR(b.proxyValueEUR)}</td>
        <td>${confidenceBadge(b.confidence)}</td>
        <td><input type="number" class="benefit-qty-input" min="0" step="any" value="${b.quantity || ''}" placeholder="0"></td>
        <td class="benefit-net-cell" style="font-weight:700;">${formatEUR(b.netValueEUR)}</td>
      </tr>
    `;
  }

  function computeBenefitRowsTotal(rows) {
    return rows.reduce((sum, b) => sum + computeBenefitNetValueClient(
      b.quantity, b.proxyValueEUR, 1, b.deadweightPct, b.attributionPct, b.dropoffPct
    ), 0);
  }

  function renderIndicatorQuality(q) {
    const box = document.getElementById('indicatorQualityBar');
    box.innerHTML = `
      <div class="quality-meter">
        <div class="quality-meter-label">Qualità catalogo KPI</div>
        <div class="quality-meter-track"><div class="quality-meter-fill" style="width:${q.kpiCatalogPct}%"></div></div>
        <div class="quality-meter-value">${q.kpiCatalogComputable}/${q.kpiCatalogTotal} calcolabili oggi (${q.kpiCatalogPct.toFixed(0)}%)</div>
      </div>
      <div class="quality-meter">
        <div class="quality-meter-label">Benefici con quantità reale inserita</div>
        <div class="quality-meter-track"><div class="quality-meter-fill" style="width:${q.benefitsPct}%"></div></div>
        <div class="quality-meter-value">${q.benefitsWithData}/${q.benefitsTotal} benefici (${q.benefitsPct.toFixed(0)}%)</div>
      </div>
    `;
  }

  let currentBenefitRows = [];

  function renderSroi(data) {
    const banner = document.getElementById('sroiBanner');
    const calculated = data.sroiRatio !== null && data.sroiRatio !== undefined;
    banner.classList.toggle('calculated', calculated);
    banner.querySelector('.sroi-banner-value').textContent = calculated ? `${data.sroiRatio.toFixed(4)}x` : 'N/D';
    document.getElementById('sroiBannerNote').textContent = data.sroiStatus || '';

    renderIndicatorQuality(data.indicatorQuality);

    const e = data.economics;
    document.getElementById('sroiEconomics').innerHTML = `
      <div class="stat-row"><span class="stat-label">Valore commesse (${e.year})</span><span class="stat-value accent">${formatEUR(e.valoreCommesseEUR)}</span></div>
      <div class="stat-row"><span class="stat-label">Crescita YoY</span><span class="stat-value">${formatPct(e.crescitaYoY)}</span></div>
      <div class="stat-row"><span class="stat-label">Commesse attive / concluse</span><span class="stat-value">${e.numeroCommesseAttive} / ${e.numeroCommesseConcluse}</span></div>
      <div class="stat-row"><span class="stat-label">Enti committenti</span><span class="stat-value">${e.numeroEntiCommittenti}</span></div>
      <div class="stat-row"><span class="stat-label">Valore medio commessa</span><span class="stat-value">${formatEUR(e.valoreMedioCommessaEUR)}</span></div>
      <div class="stat-row"><span class="stat-label">Costo per utente</span><span class="stat-value">${data.costoPerUtenteEUR !== null ? formatEUR(data.costoPerUtenteEUR) : 'N/D'}</span></div>
      <div class="stat-row"><span class="stat-label">Costo per ora erogata</span><span class="stat-value">${data.costoPerOraErogataEUR !== null ? formatEUR(data.costoPerOraErogataEUR) : 'N/D'}</span></div>
      <div class="stat-row"><span class="stat-label">Piano individuale di riferimento</span><span class="stat-value muted">${data.kpiCatalog.individualPlanLabel || '-'}</span></div>
    `;

    // Precompila il form con quanto già inserito
    document.getElementById('outcomeUsers').value = data.outcome.usersServed ?? '';
    document.getElementById('outcomeHours').value = data.outcome.hoursDelivered ?? '';
    document.getElementById('outcomeNote').value = data.outcome.note ?? '';
    document.getElementById('outcomeSaveStatus').textContent = '';

    document.getElementById('benefitsMethodologyNote').textContent = data.benefitsCatalog.methodologyNote || '';
    currentBenefitRows = data.benefitRows;
    document.getElementById('benefitsTableBody').innerHTML = currentBenefitRows.map(benefitRowHtml).join('');
    document.getElementById('benefitsTotalValue').textContent = data.netSocialValueEUR !== null ? formatEUR(data.netSocialValueEUR) : 'N/D';

    document.querySelectorAll('#benefitsTableBody .benefit-qty-input').forEach(input => {
      input.addEventListener('input', () => {
        const row = input.closest('.benefit-ref-row');
        const idx = parseInt(row.dataset.benefitIndex, 10);
        const b = currentBenefitRows.find(r => r.benefitIndex === idx);
        b.quantity = parseFloat(input.value) || 0;
        const net = computeBenefitNetValueClient(b.quantity, b.proxyValueEUR, 1, b.deadweightPct, b.attributionPct, b.dropoffPct);
        row.querySelector('.benefit-net-cell').textContent = formatEUR(net);
        const total = computeBenefitRowsTotal(currentBenefitRows);
        document.getElementById('benefitsTotalValue').textContent = formatEUR(total);
      });
    });

    fillKpiTable('#kpiEconomicTable', data.kpiCatalog.economicKPIs, 'def');
    fillKpiTable('#kpiProcessTable', data.kpiCatalog.processQualityKPIs, 'target');
    fillKpiTable('#kpiVolumeTable', data.kpiCatalog.serviceVolumeKPIs, 'def');
    document.getElementById('kpiSourceNote').textContent = data.kpiCatalog.sourceNote || '';
  }

  async function saveOutcome() {
    const cluster = document.getElementById('clusterSelect').value;
    const statusEl = document.getElementById('outcomeSaveStatus');
    const benefitQuantities = {};
    currentBenefitRows.forEach(b => { if (b.quantity) benefitQuantities[String(b.benefitIndex)] = b.quantity; });

    const payload = {
      cluster,
      year: SROI_YEAR,
      usersServed: document.getElementById('outcomeUsers').value ? parseInt(document.getElementById('outcomeUsers').value, 10) : null,
      hoursDelivered: document.getElementById('outcomeHours').value ? parseFloat(document.getElementById('outcomeHours').value) : null,
      benefitQuantities,
      note: document.getElementById('outcomeNote').value || null,
    };

    statusEl.textContent = 'Salvataggio...';
    try {
      const res = await apiFetch(`${API_BASE}/sroi/outcome`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      renderSroi(data);
      statusEl.textContent = 'Salvato.';
    } catch (err) {
      console.error(err);
      statusEl.textContent = 'Errore nel salvataggio.';
    }
  }

  // ------------------------------------------------------------------
  // PAGE: Calcolo SROI (rigoroso, per progetto)
  // ------------------------------------------------------------------
  let sroiProjectsCache = [];
  let selectedProjectId = null;
  let benefitLibraryCache = {};

  const COST_CATEGORIES = ['Personale', 'Materiali', 'Spazi e sedi', 'Altro'];
  const BENEFIT_CATEGORIES = ['Salute', 'Inclusione sociale', 'Occupazione', 'Educazione', 'Caregiver', 'Custom'];

  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  async function loadSroiCalcPage() {
    await ensureServices();
    await refreshSroiProjectList();
    document.getElementById('sroiNewProjectBtn').onclick = createNewSroiProject;
  }

  async function refreshSroiProjectList() {
    const res = await apiFetch(`${API_BASE}/sroi/projects`);
    sroiProjectsCache = await res.json();
    renderSroiProjectList();
  }

  function renderSroiProjectList() {
    const box = document.getElementById('sroiProjectList');
    if (sroiProjectsCache.length === 0) {
      box.innerHTML = '<p style="font-size:12px; color: var(--text-muted);">Nessun progetto ancora creato.</p>';
      return;
    }
    box.innerHTML = sroiProjectsCache.map(p => `
      <div class="project-card ${p.id === selectedProjectId ? 'selected' : ''}" data-project-id="${p.id}">
        <div class="project-card-title-row">
          <span class="project-card-name">${escapeHtml(p.name)}</span>
          <span class="status-badge ${p.status === 'Completato' ? 'win' : 'prep'}">${p.status}</span>
        </div>
        <div class="project-card-meta">${escapeHtml(p.serviceCluster || '-')} · ${p.year || ''}</div>
        <div class="project-card-sroi">SROI: <span>${p.sroiRatio !== null ? p.sroiRatio.toFixed(2) : 'N/D'}</span></div>
      </div>
    `).join('');
    box.querySelectorAll('.project-card').forEach(card => {
      card.addEventListener('click', () => selectSroiProject(parseInt(card.dataset.projectId, 10)));
    });
  }

  async function createNewSroiProject() {
    const res = await apiFetch(`${API_BASE}/sroi/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: 'Nuovo progetto', status: 'In corso', year: new Date().getFullYear() }),
    });
    const data = await res.json();
    selectedProjectId = data.id;
    await refreshSroiProjectList();
    renderProjectDetail(data);
  }

  async function selectSroiProject(id) {
    selectedProjectId = id;
    renderSroiProjectList();
    const res = await apiFetch(`${API_BASE}/sroi/projects/${id}`);
    const data = await res.json();
    renderProjectDetail(data);
  }

  async function reloadSelectedProject() {
    const res = await apiFetch(`${API_BASE}/sroi/projects/${selectedProjectId}`);
    const data = await res.json();
    renderProjectDetail(data);
    await refreshSroiProjectList();
  }

  function clusterOptionsHtml(selected) {
    const clusters = allServices ? distinctClusters(allServices) : [];
    return '<option value="">-</option>' + clusters.map(c =>
      `<option value="${c}" ${c === selected ? 'selected' : ''}>${c}</option>`
    ).join('');
  }

  function costRowHtml(c) {
    return `
      <div class="cost-row" data-cost-id="${c.id}">
        <span></span>
        <select class="sroi-cost-category">
          ${COST_CATEGORIES.map(cat => `<option value="${cat}" ${cat === c.category ? 'selected' : ''}>${cat}</option>`).join('')}
        </select>
        <input type="number" class="sroi-cost-amount" value="${c.amountEUR}" step="1000">
        <button class="icon-btn sroi-delete-cost" title="Rimuovi">✕</button>
      </div>
    `;
  }

  function benefitCardHtml(b) {
    return `
      <div class="benefit-card" data-benefit-id="${b.id}">
        <div class="benefit-card-top">
          <div style="flex:1;">
            <select class="category-tag-select">
              ${BENEFIT_CATEGORIES.map(cat => `<option value="${cat}" ${cat === b.category ? 'selected' : ''}>${cat}</option>`).join('')}
            </select>
            <input type="text" class="benefit-title-input" value="${escapeHtml(b.title)}" placeholder="Titolo del beneficio">
            <div style="font-size:11px; color: var(--text-muted); margin-top:2px;">
              <input type="text" class="benefit-stakeholder-input" value="${escapeHtml(b.stakeholder || '')}" placeholder="Stakeholder (es. Utenti / Famiglie)" style="border:none; background:transparent; font-size:11px; color:var(--text-muted); width:100%;">
            </div>
          </div>
          <div class="benefit-net-value">
            <div class="label">Valore netto</div>
            <div class="value">${formatEUR(b.netValueEUR)}</div>
          </div>
          <button class="icon-btn sroi-delete-benefit" title="Rimuovi">✕</button>
        </div>
        <div class="benefit-fields">
          <div><label>Quantità</label><input type="number" class="bf" data-field="quantity" value="${b.quantity}"></div>
          <div><label>Proxy (€/unità)</label><input type="number" class="bf" data-field="proxyValueEUR" value="${b.proxyValueEUR}"></div>
          <div><label>Anni durata</label><input type="number" class="bf" data-field="durationYears" value="${b.durationYears}" min="1" step="1"></div>
          <div><label>Deadweight %</label><input type="number" class="bf" data-field="deadweightPct" value="${b.deadweightPct}" min="0" max="100"></div>
          <div><label>Attribution %</label><input type="number" class="bf" data-field="attributionPct" value="${b.attributionPct}" min="0" max="100"></div>
          <div><label>Drop-off % /anno</label><input type="number" class="bf" data-field="dropoffPct" value="${b.dropoffPct}" min="0" max="100"></div>
        </div>
      </div>
    `;
  }

  function renderProjectDetail(data) {
    const el = document.getElementById('sroiProjectDetail');
    const sroiDisplay = data.sroiRatio !== null && data.sroiRatio !== undefined ? data.sroiRatio.toFixed(2) + 'x' : 'N/D';

    el.innerHTML = `
      <div class="sroicalc-detail-header">
        <h2>${escapeHtml(data.name)}</h2>
        <div style="display:flex; align-items:center; gap:14px;">
          <span class="stat-label">SROI Ratio: <strong style="color:var(--green-d); font-size:15px;">${sroiDisplay}</strong></span>
          <button class="btn btn-secondary btn-sm" id="sroiDeleteProjectBtn">Elimina</button>
          <button class="btn btn-primary btn-sm" id="sroiSaveProjectBtn">Salva</button>
        </div>
      </div>

      <div class="card glass" style="margin-bottom:18px;">
        <div class="form-grid">
          <div class="filter-group" style="grid-column: span 2;">
            <label>Nome progetto *</label>
            <input type="text" id="sroiFieldName" value="${escapeHtml(data.name)}">
          </div>
          <div class="filter-group">
            <label>Area di servizio</label>
            <select id="sroiFieldCluster">${clusterOptionsHtml(data.serviceCluster)}</select>
          </div>
          <div class="filter-group">
            <label>Stato</label>
            <select id="sroiFieldStatus">
              <option value="In corso" ${data.status === 'In corso' ? 'selected' : ''}>In corso</option>
              <option value="Completato" ${data.status === 'Completato' ? 'selected' : ''}>Completato</option>
            </select>
          </div>
          <div class="filter-group">
            <label>Anno di riferimento</label>
            <input type="number" id="sroiFieldYear" value="${data.year || ''}">
          </div>
          <div class="filter-group">
            <label>Beneficiari diretti</label>
            <input type="number" id="sroiFieldBeneficiaries" value="${data.directBeneficiaries || ''}">
          </div>
          <div class="filter-group" style="grid-column: span 2;">
            <label>Descrizione</label>
            <textarea id="sroiFieldDescription" rows="2">${escapeHtml(data.description || '')}</textarea>
          </div>
        </div>
      </div>

      <div class="card glass" style="margin-bottom:18px;">
        <div class="card-header"><h3 class="card-title">Rendiconto Costi Diretti</h3></div>
        <div id="sroiCostRows">${data.costs.map(costRowHtml).join('')}</div>
        <button class="btn btn-secondary btn-sm" id="sroiAddCostBtn" style="margin-top:12px;">+ Voce di costo</button>
        <div class="total-row"><span>Totale Investimento</span><span>${formatEUR(data.totalInvestmentEUR)}</span></div>
      </div>

      <div class="card glass">
        <div class="card-header">
          <h3 class="card-title">Benefici (${data.benefits.length})</h3>
          <div style="display:flex; gap:8px;">
            <div class="library-dropdown">
              <button class="btn btn-secondary btn-sm" id="sroiLibraryBtn">📚 Libreria</button>
              <div class="library-menu" id="sroiLibraryMenu" style="display:none;"></div>
            </div>
            <button class="btn btn-secondary btn-sm" id="sroiAddBenefitBtn">+ Custom</button>
          </div>
        </div>
        <div id="sroiBenefitCards">${data.benefits.map(benefitCardHtml).join('') || '<p class="text-center">Nessun beneficio aggiunto. Usa "Libreria" o "+ Custom".</p>'}</div>
        <div class="total-row" style="margin-top:8px;"><span>Valore Sociale Netto Totale</span><span>${formatEUR(data.totalNetValueEUR)}</span></div>
      </div>
    `;

    attachProjectDetailHandlers(data.id);
  }

  function attachProjectDetailHandlers(projectId) {
    document.getElementById('sroiSaveProjectBtn').addEventListener('click', async () => {
      await apiFetch(`${API_BASE}/sroi/projects/${projectId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: document.getElementById('sroiFieldName').value,
          serviceCluster: document.getElementById('sroiFieldCluster').value || null,
          status: document.getElementById('sroiFieldStatus').value,
          year: parseInt(document.getElementById('sroiFieldYear').value, 10) || null,
          directBeneficiaries: parseInt(document.getElementById('sroiFieldBeneficiaries').value, 10) || null,
          description: document.getElementById('sroiFieldDescription').value,
        }),
      });
      await reloadSelectedProject();
    });

    document.getElementById('sroiDeleteProjectBtn').addEventListener('click', async () => {
      await apiFetch(`${API_BASE}/sroi/projects/${projectId}`, { method: 'DELETE' });
      selectedProjectId = null;
      document.getElementById('sroiProjectDetail').innerHTML =
        '<div class="sroicalc-empty">Seleziona un progetto dalla lista oppure crea un nuovo progetto SROI.</div>';
      await refreshSroiProjectList();
    });

    document.getElementById('sroiAddCostBtn').addEventListener('click', async () => {
      await apiFetch(`${API_BASE}/sroi/projects/${projectId}/costs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ category: 'Altro', amountEUR: 0 }),
      });
      await reloadSelectedProject();
    });

    document.querySelectorAll('#sroiCostRows .cost-row').forEach(row => {
      const costId = row.dataset.costId;
      const saveNow = () => {
        apiFetch(`${API_BASE}/sroi/projects/${projectId}/costs/${costId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            category: row.querySelector('.sroi-cost-category').value,
            amountEUR: parseFloat(row.querySelector('.sroi-cost-amount').value) || 0,
          }),
        });
      };
      const debouncedSave = debounce(saveNow, 500);
      row.querySelector('.sroi-cost-category').addEventListener('change', saveNow);
      row.querySelector('.sroi-cost-amount').addEventListener('input', () => { recomputeTotals(); debouncedSave(); });
      row.querySelector('.sroi-delete-cost').addEventListener('click', async () => {
        await apiFetch(`${API_BASE}/sroi/projects/${projectId}/costs/${costId}`, { method: 'DELETE' });
        await reloadSelectedProject();
      });
    });

    document.getElementById('sroiAddBenefitBtn').addEventListener('click', async () => {
      await apiFetch(`${API_BASE}/sroi/projects/${projectId}/benefits`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ category: 'Custom', title: 'Nuovo beneficio', quantity: 0, proxyValueEUR: 0, durationYears: 1, deadweightPct: 0, attributionPct: 100, dropoffPct: 0 }),
      });
      await reloadSelectedProject();
    });

    const libraryBtn = document.getElementById('sroiLibraryBtn');
    const libraryMenu = document.getElementById('sroiLibraryMenu');
    libraryBtn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const cluster = document.getElementById('sroiFieldCluster').value || null;
      const cacheKey = cluster || '__all__';
      if (!benefitLibraryCache[cacheKey]) {
        const url = cluster
          ? `${API_BASE}/sroi/benefits-catalog?cluster=${encodeURIComponent(cluster)}`
          : `${API_BASE}/sroi/benefits-catalog`;
        const res = await apiFetch(url);
        benefitLibraryCache[cacheKey] = await res.json();
      }
      const catalog = benefitLibraryCache[cacheKey];
      const items = cluster
        ? catalog.benefits
        : Object.values(catalog.byCluster).flatMap(c => c.benefits.map(b => ({ ...b, _cluster: c.cluster })));

      const noteHtml = `<div class="library-menu-note">${escapeHtml(cluster ? catalog.methodologyNote : catalog.methodologyNote)}</div>`;
      libraryMenu.innerHTML = noteHtml + items.map((item, i) => `
        <div class="library-menu-item" data-lib-index="${i}">
          <div class="cat">${escapeHtml(item.category)}${item._cluster ? ' · ' + escapeHtml(item._cluster) : ''}</div>
          <div>${escapeHtml(item.title)}</div>
          <div class="lib-proxy">${formatEUR(item.proxyValueEUR)} / ${escapeHtml(item.unit)} · confidenza ${escapeHtml(item.confidence)}</div>
        </div>
      `).join('');
      libraryMenu.querySelectorAll('.library-menu-item').forEach(el => {
        el.addEventListener('click', async () => {
          const item = items[parseInt(el.dataset.libIndex, 10)];
          await apiFetch(`${API_BASE}/sroi/projects/${projectId}/benefits`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              category: item.category, title: item.title, stakeholder: item.stakeholder,
              note: `${item.source} (confidenza: ${item.confidence})`, quantity: 0,
              proxyValueEUR: item.proxyValueEUR, durationYears: 1,
              deadweightPct: item.deadweightPct, attributionPct: item.attributionPct, dropoffPct: item.dropoffPct,
            }),
          });
          libraryMenu.style.display = 'none';
          await reloadSelectedProject();
        });
      });
      libraryMenu.style.display = libraryMenu.style.display === 'none' ? 'block' : 'none';
    });
    document.addEventListener('click', () => { if (libraryMenu) libraryMenu.style.display = 'none'; }, { once: true });

    document.querySelectorAll('.benefit-card').forEach(card => {
      const benefitId = card.dataset.benefitId;
      const buildPayload = () => {
        const payload = {
          category: card.querySelector('.category-tag-select').value,
          title: card.querySelector('.benefit-title-input').value,
          stakeholder: card.querySelector('.benefit-stakeholder-input').value,
        };
        card.querySelectorAll('.bf').forEach(input => {
          payload[input.dataset.field] = parseFloat(input.value) || 0;
        });
        return payload;
      };
      const saveNow = () => {
        apiFetch(`${API_BASE}/sroi/projects/${projectId}/benefits/${benefitId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(buildPayload()),
        });
      };
      const debouncedSave = debounce(saveNow, 500);

      card.querySelectorAll('.bf').forEach(input => {
        input.addEventListener('input', () => { recomputeBenefitCard(card); debouncedSave(); });
      });
      card.querySelector('.benefit-title-input').addEventListener('input', debouncedSave);
      card.querySelector('.benefit-stakeholder-input').addEventListener('input', debouncedSave);
      card.querySelector('.category-tag-select').addEventListener('change', saveNow);

      card.querySelector('.sroi-delete-benefit').addEventListener('click', async () => {
        await apiFetch(`${API_BASE}/sroi/projects/${projectId}/benefits/${benefitId}`, { method: 'DELETE' });
        await reloadSelectedProject();
      });
    });
  }

  function debounce(fn, delay) {
    let timer = null;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), delay);
    };
  }

  function computeBenefitNetValueClient(quantity, proxy, duration, deadweightPct, attributionPct, dropoffPct) {
    const deadweight = (deadweightPct || 0) / 100;
    const attribution = (attributionPct !== null && attributionPct !== undefined ? attributionPct : 100) / 100;
    const dropoff = (dropoffPct || 0) / 100;
    const years = Math.max(parseInt(duration, 10) || 1, 1);
    const base = (quantity || 0) * (proxy || 0) * (1 - deadweight) * attribution;
    let total = 0;
    for (let t = 0; t < years; t++) total += base * Math.pow(1 - dropoff, t);
    return total;
  }

  function recomputeBenefitCard(card) {
    const fields = {};
    card.querySelectorAll('.bf').forEach(input => { fields[input.dataset.field] = parseFloat(input.value) || 0; });
    const net = computeBenefitNetValueClient(
      fields.quantity, fields.proxyValueEUR, fields.durationYears,
      fields.deadweightPct, fields.attributionPct, fields.dropoffPct
    );
    card.querySelector('.benefit-net-value .value').textContent = formatEUR(net);
    recomputeTotals();
  }

  function recomputeTotals() {
    const detail = document.getElementById('sroiProjectDetail');
    let totalInvestment = 0;
    detail.querySelectorAll('.cost-row .sroi-cost-amount').forEach(input => {
      totalInvestment += parseFloat(input.value) || 0;
    });
    let totalNetValue = 0;
    detail.querySelectorAll('.benefit-card').forEach(card => {
      const fields = {};
      card.querySelectorAll('.bf').forEach(input => { fields[input.dataset.field] = parseFloat(input.value) || 0; });
      totalNetValue += computeBenefitNetValueClient(
        fields.quantity, fields.proxyValueEUR, fields.durationYears,
        fields.deadweightPct, fields.attributionPct, fields.dropoffPct
      );
    });

    const totalRows = detail.querySelectorAll('.total-row');
    if (totalRows[0]) totalRows[0].querySelector('span:last-child').textContent = formatEUR(totalInvestment);
    if (totalRows[1]) totalRows[1].querySelector('span:last-child').textContent = formatEUR(totalNetValue);

    const sroiRatio = totalInvestment ? totalNetValue / totalInvestment : null;
    const sroiHeader = detail.querySelector('.sroicalc-detail-header strong');
    if (sroiHeader) sroiHeader.textContent = sroiRatio !== null ? sroiRatio.toFixed(2) + 'x' : 'N/D';
  }

  // ------------------------------------------------------------------
  // PAGE: Territorio (mappa)
  // ------------------------------------------------------------------
  let territorioMapInstance = null;
  let territorioLoaded = false;

  async function loadTerritorioPage() {
    if (territorioLoaded) return;
    territorioLoaded = true;

    const res = await apiFetch(`${API_BASE}/territorio/mappa`);
    const data = await res.json();
    document.getElementById('territorioNote').textContent = data.sourceNote || '';

    territorioMapInstance = L.map('territorioMap').setView([41.5, 15.5], 6);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 18,
    }).addTo(territorioMapInstance);

    const maxValue = Math.max(...data.sites.map(s => s.valoreCommesseEUR));
    data.sites.forEach(s => {
      if (s.lat === null) return;
      const radius = 6 + Math.sqrt(s.valoreCommesseEUR / maxValue) * 24;
      L.circleMarker([s.lat, s.lon], {
        radius, color: COLOR_GREEN, fillColor: COLOR_GREEN, fillOpacity: 0.45, weight: 1.5,
      }).addTo(territorioMapInstance).bindPopup(`
        <strong>${escapeHtml(s.siteName)}</strong><br>
        ${escapeHtml(s.comune)} (${escapeHtml(s.regione || '')})<br>
        Valore commesse (${data.year}): ${formatEUR(s.valoreCommesseEUR)}
      `);
    });

    const top = data.sites.slice(0, 8);
    document.getElementById('territorioRankedList').innerHTML = top.map((s, i) => `
      <div class="stat-row ranked">
        <span class="stat-label"><span class="rank-badge">${i + 1}</span>${escapeHtml(s.siteName)}</span>
        <span class="stat-value accent">${formatEUR(s.valoreCommesseEUR)}</span>
      </div>
    `).join('');

    document.getElementById('territorioTableBody').innerHTML = data.sites.map(s => `
      <tr>
        <td style="font-weight:600">${escapeHtml(s.siteName)}</td>
        <td>${escapeHtml(s.comune || '')}</td>
        <td>${escapeHtml(s.regione || '')}</td>
        <td style="font-family: var(--font-mono)">${formatEUR(s.valoreCommesseEUR)}</td>
        <td>${s.numeroCluster}</td>
      </tr>
    `).join('');
  }

  // ------------------------------------------------------------------
  // PAGE: Anomalie
  // ------------------------------------------------------------------
  let anomalieLoaded = false;

  async function loadAnomaliePage() {
    if (anomalieLoaded) return;
    anomalieLoaded = true;

    const res = await apiFetch(`${API_BASE}/territorio/anomalie`);
    const data = await res.json();
    document.getElementById('anomalieNote').textContent = data.sourceNote || '';

    const bySite = {};
    data.anomalies.forEach(a => {
      bySite[a.siteName] = bySite[a.siteName] || [];
      bySite[a.siteName].push(a);
    });

    const container = document.getElementById('anomalieList');
    const siteNames = Object.keys(bySite);
    if (siteNames.length === 0) {
      container.innerHTML = '<p class="text-center">Nessuna anomalia rilevata rispetto alle soglie impostate.</p>';
      return;
    }

    container.innerHTML = siteNames.map(siteName => {
      const items = bySite[siteName];
      const worst = items.some(a => a.severity === 'CRITICO') ? 'CRITICO' : 'ATTENZIONE';
      return `
        <div class="anomaly-site-card">
          <div class="anomaly-site-header">
            <h4>${escapeHtml(siteName)} <span class="badge-sev ${worst.toLowerCase()}">${worst}</span></h4>
            <span class="meta">${items.length} anomalia${items.length > 1 ? 'e' : ''} rilevata${items.length > 1 ? 'e' : ''}</span>
          </div>
          ${items.map(a => `
            <div class="anomaly-item ${a.severity.toLowerCase()}">
              <div class="anomaly-item-top">
                <span><span class="badge-sev ${a.severity.toLowerCase()}">${a.severity}</span><strong>${escapeHtml(a.serviceName)}</strong></span>
                <span style="color:${a.deviationPct >= 0 ? 'var(--green-d)' : 'var(--red-d)'}; font-weight:700;">${a.deviationPct >= 0 ? '+' : ''}${(a.deviationPct * 100).toFixed(1)}%</span>
              </div>
              <div class="anomaly-item-detail">
                Anno ${a.year}: ${formatEUR(a.actualEUR)} — Media storica: ${formatEUR(a.historicalAverageEUR)} — Cluster: ${a.cluster} — Stato: ${a.status}
              </div>
              ${a.suggestedActions.length ? `<ul class="anomaly-actions">${a.suggestedActions.map(s => `<li>${escapeHtml(s)}</li>`).join('')}</ul>` : ''}
            </div>
          `).join('')}
        </div>
      `;
    }).join('');
  }

  // ------------------------------------------------------------------
  // PAGE: Genera Relazione (Fase 5)
  // ------------------------------------------------------------------
  async function loadRelazionePage() {
    const clusterSelect = document.getElementById('relCluster');
    const regioneSelect = document.getElementById('relRegione');

    if (!clusterSelect.dataset.loaded) {
      const services = await ensureServices();
      const clusters = distinctClusters(services);
      clusterSelect.innerHTML = clusters.map(c => `<option value="${c}">${c}</option>`).join('');
      clusterSelect.dataset.loaded = '1';

      const sites = await ensureSites();
      const regioni = [...new Set(sites.map(s => s.Regione).filter(Boolean))].sort();
      regioneSelect.innerHTML = '<option value="">Tutte le regioni</option>' +
        regioni.map(r => `<option value="${r}">${r}</option>`).join('');

      clusterSelect.addEventListener('change', refreshRelSroiProjectOptions);
      document.getElementById('relGeneraBtn').addEventListener('click', generateRelazione);
      document.getElementById('relPrintBtn').addEventListener('click', () => window.print());
      await refreshRelSroiProjectOptions();
    }
  }

  async function refreshRelSroiProjectOptions() {
    const cluster = document.getElementById('relCluster').value;
    const select = document.getElementById('relSroiProject');
    const res = await apiFetch(`${API_BASE}/sroi/projects`);
    const projects = await res.json();
    const matching = projects.filter(p => p.serviceCluster === cluster);
    select.innerHTML = '<option value="">Nessuno</option>' +
      matching.map(p => `<option value="${p.id}">${escapeHtml(p.name)} (SROI ${p.sroiRatio !== null ? p.sroiRatio.toFixed(2) + 'x' : 'N/D'})</option>`).join('');
  }

  async function generateRelazione() {
    const cluster = document.getElementById('relCluster').value;
    const regione = document.getElementById('relRegione').value;
    const budget = parseFloat(document.getElementById('relBudget').value) || 0;
    const durata = parseFloat(document.getElementById('relDurata').value) || 1;
    const sroiProjectId = document.getElementById('relSroiProject').value;

    const params = new URLSearchParams({ cluster, budget_eur: budget, durata_anni: durata });
    if (regione) params.set('regione', regione);
    if (sroiProjectId) params.set('sroi_project_id', sroiProjectId);

    const res = await apiFetch(`${API_BASE}/relazione/genera?${params.toString()}`);
    const data = await res.json();

    document.getElementById('relOutput').style.display = 'block';
    document.getElementById('relHeaderCluster').textContent = data.cluster;
    document.getElementById('relHeaderSub').textContent =
      `Budget: ${formatEUR(data.budgetEUR)} — Durata: ${data.durataAnni} anni — ` +
      `Territorio: ${data.regione || 'tutte le regioni'}`;

    // 1. Track record
    const tr = data.trackRecord;
    document.getElementById('relTrackStats').innerHTML = `
      <div class="stat-row"><span class="stat-label">Commesse comparabili nel cluster${tr.regioneFiltro ? ' (' + tr.regioneFiltro + ')' : ''}</span><span class="stat-value accent">${tr.numeroCommesseComparabili}</span></div>
      <div class="stat-row"><span class="stat-label">Anni di esperienza documentata</span><span class="stat-value">${tr.anniEsperienza}</span></div>
    `;
    document.getElementById('relTrackBody').innerHTML = tr.progetti.map(p => `
      <tr>
        <td style="font-family: var(--font-mono); color: var(--text-muted)">${p.sito}</td>
        <td style="font-weight:600">${p.servizio}<br><span style="color: var(--text-muted); font-size: 0.85em; font-weight:400;">${p.enteCommittente}</span></td>
        <td style="font-family: var(--font-mono)">${formatEUR(p.valoreEUR)}</td>
        <td>${p.regione || ''}</td>
        <td>${p.anno}</td>
        <td><span class="status-badge ${p.stato === 'In essere' ? 'win' : 'eval'}">${p.stato}</span></td>
      </tr>
    `).join('') || '<tr><td colspan="6" class="text-center">Nessuna commessa comparabile trovata</td></tr>';

    // 2. Stima impatto SAM
    const stima = data.stimaImpattoMacroeconomico;
    document.getElementById('relImpactHypothesis').textContent = stima ? stima.ipotesi : 'N/D';

    if (relSamChartInstance) { relSamChartInstance.destroy(); relSamChartInstance = null; }
    if (stima && stima.impact) {
      const ctx = document.getElementById('relSamChart').getContext('2d');
      relSamChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: ['Diretto (budget)', 'Totale Tipo I (+fornitori)', 'Totale Tipo II (+indotto famiglie)'],
          datasets: [
            { label: 'Output EUR', data: [stima.direct.outputEUR, stima.total.type1_leontief.outputEUR, stima.total.type2_sam.outputEUR], backgroundColor: COLOR_GREEN, borderRadius: 6 },
            { label: 'Valore Aggiunto EUR', data: [stima.direct.valueAddedEUR, stima.total.type1_leontief.valueAddedEUR, stima.total.type2_sam.valueAddedEUR], backgroundColor: COLOR_NAVY, borderRadius: 6 },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${formatEUR(c.parsed.y)}` } } },
          scales: {
            y: { beginAtZero: true, grid: { color: COLOR_GRID } },
            x: { grid: { display: false } },
          },
        },
      });

      document.getElementById('relSamSummary').innerHTML = `
        <div class="stat-row"><span class="stat-label">Occupazione diretta stimata</span><span class="stat-value accent">${formatNumber(stima.direct.jobsEstimate, 1)}</span></div>
        <div class="stat-row"><span class="stat-label">Posti equiv. indiretti (Tipo I)</span><span class="stat-value">${formatNumber(stima.impact.type1_leontief.deltaJobsEquivalent, 1)}</span></div>
        <div class="stat-row"><span class="stat-label">Posti equiv. indiretti+indotti (Tipo II)</span><span class="stat-value">${formatNumber(stima.impact.type2_sam.deltaJobsEquivalent, 1)}</span></div>
        <div class="stat-row"><span class="stat-label">Moltiplicatore Tipo I / Tipo II</span><span class="stat-value">${stima.impact.type1_leontief.outputMultiplier.toFixed(2)}x / ${stima.impact.type2_sam.outputMultiplier.toFixed(2)}x</span></div>
      `;
    } else {
      document.getElementById('relSamSummary').innerHTML = '<div class="stat-row"><span class="stat-label">Impatto non calcolabile per questo budget.</span></div>';
    }

    // 3. SROI progetto collegato + benefici del cluster + KPI catalog
    const relBanner = document.getElementById('relSroiBanner');
    const relCalculated = data.progettoSroiCollegato && data.progettoSroiCollegato.sroiRatio !== null && data.progettoSroiCollegato.sroiRatio !== undefined;
    relBanner.classList.toggle('calculated', relCalculated);
    relBanner.querySelector('.sroi-banner-value').textContent = relCalculated ? `${data.progettoSroiCollegato.sroiRatio.toFixed(2)}x` : 'N/D';
    document.getElementById('relSroiNote').textContent = data.sroiStatus;

    document.getElementById('relBenefitsMethodologyNote').textContent = data.benefitsCatalog.methodologyNote || '';
    document.getElementById('relBenefitsTableBody').innerHTML = data.benefitsCatalog.benefits.map(b => `
      <tr>
        <td>
          <div style="font-weight:600;">${escapeHtml(b.title)}</div>
          <div style="font-size:11px; color: var(--text-muted);">${escapeHtml(b.category)} · ${escapeHtml(b.unit)}</div>
        </td>
        <td style="color: var(--text-muted); font-size:0.9em;">${escapeHtml(b.stakeholder || '-')}</td>
        <td style="font-family: var(--font-mono);">${formatEUR(b.proxyValueEUR)}</td>
        <td>${confidenceBadge(b.confidence)}</td>
        <td style="font-size:11px; color: var(--text-muted);">${escapeHtml(b.source)}</td>
      </tr>
    `).join('');

    fillKpiTable('#relKpiEconomicTable', data.kpiMonitoraggioProposto.economicKPIs, 'def');
    fillKpiTable('#relKpiProcessTable', data.kpiMonitoraggioProposto.processQualityKPIs, 'target');
    fillKpiTable('#relKpiVolumeTable', data.kpiMonitoraggioProposto.serviceVolumeKPIs, 'def');

    // 4. Note metodologiche
    document.getElementById('relNoteMetodologiche').textContent = data.noteMetodologiche;
  }

  // ------------------------------------------------------------------
  // Export
  // ------------------------------------------------------------------
  document.getElementById('exportPdfBtn').addEventListener('click', () => window.print());

  document.getElementById('exportExcelBtn').addEventListener('click', () => {
    if (currentServiceRevenueData.length === 0) return alert('Nessun dato da esportare');
    const ws = XLSX.utils.json_to_sheet(currentServiceRevenueData);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Storico Servizi");
    XLSX.writeFile(wb, "Auxilium_Servizi.xlsx");
  });

  // ------------------------------------------------------------------
  // Init
  // ------------------------------------------------------------------
  let dashboardInitialized = false;
  function initDashboard() {
    if (dashboardInitialized) return;
    dashboardInitialized = true;
    fetchOverview();
    setInterval(fetchOverview, 30000);
  }

  if (getToken()) initDashboard();
});
