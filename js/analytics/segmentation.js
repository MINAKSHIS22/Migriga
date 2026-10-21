/* MIGRIGA ANALYTICS - Customer Segmentation (RFM + K-Means) via background job */
(() => {
  const { runJob, download, esc, fmt, chart, axis, renderTable, errorBox, PALETTE, $ } = MA;
  let root, current, running = false;

  function init() {
    root = $('#seg-root');
    root.innerHTML = `
      ${MA.pageHead('Data mining', 'Customer Segmentation', '')}
      <div class="an-intro">
        <div><h3>What does this do?</h3><p>Groups customers with similar buying behaviour using three <strong>RFM</strong> measures and the <strong>K-Means</strong> clustering algorithm:</p>
          <ul><li><strong>Recency</strong>: how many days since the customer last purchased.</li>
            <li><strong>Frequency</strong>: on how many different invoices they purchased.</li>
            <li><strong>Monetary</strong>: how much eligible purchase value they generated (£, after their own cancellations).</li></ul></div>
        <div><h3>What data is used?</h3><p>Identified customers in <code>dim_customer</code> and their merchandise lines in <code>fact_sales</code>.
          Purchases without a customer ID are never given a profile. Recency is measured from the day after the last purchase in the data
          (10 Dec 2010), not from today. No names or demographics exist in the source.</p></div>
      </div>
      <div class="an-card">
        <div class="an-step">Controls</div>
        <div class="an-controls">
          <div class="an-field"><label for="seg-k">Number of segments</label>
            <select class="an-select" id="seg-k">${[2, 3, 4, 5, 6, 7, 8, 9, 10].map((k) => `<option ${k === 4 ? 'selected' : ''}>${k}</option>`).join('')}</select></div>
          <button class="an-btn primary" id="seg-run" type="button">Run analysis</button>
          <div class="an-field grow"><div class="an-progress" aria-hidden="true"><span id="seg-bar"></span></div>
            <div class="an-status-line" id="seg-status" aria-live="polite"></div></div>
        </div>
        ${MA.details('More settings', `<div class="an-controls"><div class="an-field"><label for="seg-seed">Random seed</label>
          <input class="an-input" type="number" id="seg-seed" value="42" min="0" step="1"></div>
          <p class="an-hint" style="max-width: 420px;">The same seed always gives the same segments (reproducible results).</p></div>`, { hint: 'random seed' })}
      </div>
      <div id="seg-results"></div>`;
    root.querySelector('.an-card .an-details').style.margin = '12px 0 0';
    $('#seg-run').addEventListener('click', run);
    $('#seg-k').addEventListener('change', run);
    run();
  }

  async function run() {
    if (running) return;
    running = true;
    const k = Number($('#seg-k').value), seed = Number($('#seg-seed').value);
    $('#seg-run').disabled = true;
    $('#seg-results').classList.add('an-loading');
    try {
      const job = await runJob('/api/analytics/segmentation/jobs', { k, seed }, (j, cached) => {
        $('#seg-bar').style.width = j.progress + '%';
        $('#seg-status').textContent = cached && j.status === 'done' ? 'Showing the saved result for these settings.' : `Working: ${j.message}`;
      });
      current = job;
      $('#seg-status').textContent = `Done — ${fmt.int(job.result.customers_included)} customers grouped into ${k} segments.`;
      render(job.result);
    } catch (e) {
      $('#seg-status').textContent = 'The analysis could not run.'; $('#seg-bar').style.width = '0';
      $('#seg-results').innerHTML = errorBox(e);
    } finally {
      running = false; $('#seg-run').disabled = false; $('#seg-results').classList.remove('an-loading');
    }
  }

  const color = (c) => PALETTE[(c - 1) % PALETTE.length];

  function render(r) {
    const ex = r.customers_excluded;
    const exTotal = Object.values(ex).reduce((a, b) => a + b, 0);
    const cl = [...r.clusters].sort((a, b) => a.cluster - b.cluster);
    const largest = cl.reduce((a, b) => (b.size > a.size ? b : a));
    const richest = r.clusters[0];   // clusters arrive ordered by median spend
    const out = $('#seg-results');
    out.innerHTML = `
      <div class="an-card">
        <div class="an-card-header"><h2 class="an-card-title">Segments found</h2>
          <span class="an-hint">${fmt.int(r.customers_included)} customers · ordered by median spend</span></div>
        <div class="an-seg-cards">${r.clusters.map((c) => `
          <div class="an-seg-card" style="--seg-color: ${color(c.cluster)}">
            <h4><span><span class="an-swatch" style="background: ${color(c.cluster)}"></span>Segment ${c.cluster}</span><span class="an-hint">${fmt.pct(c.share)}</span></h4>
            <div class="profile">${esc(c.profile)}</div>
            <dl><dt>Customers</dt><dd>${fmt.int(c.size)}</dd>
              <dt>Last purchase (median)</dt><dd>${fmt.int(c.median.recency_days)} days ago</dd>
              <dt>Invoices (median)</dt><dd>${fmt.num(c.median.frequency, 1)}</dd>
              <dt>Spend (median)</dt><dd>${fmt.money(c.median.monetary)}</dd></dl>
          </div>`).join('')}</div>
      </div>
      <div class="an-grid cols-2-1">
        ${MA.canvasCard('Customers per segment', 'Number of customers in each segment.', { id: 'seg-size' })}
        ${MA.card('What this means', `<div class="an-interpret" style="margin: 0;">
            The largest group is <strong>segment ${largest.cluster}</strong> (${fmt.int(largest.size)} customers, ${fmt.pct(largest.share)}): ${esc(largest.profile.toLowerCase())}.
            <br><br>Segment ${richest.cluster} has the highest median spend (${fmt.money(richest.median.monetary)}), last purchased a median of
            ${fmt.int(richest.median.recency_days)} days before the reference date, and bought on ${fmt.num(richest.median.frequency, 1)} invoices.
            <br><br>Descriptions compare each segment's median with the median of all customers (within ±15% = “typical”). They describe behaviour; they are not marketing labels.</div>`)}
      </div>
      ${MA.details('RFM comparison charts', `<div class="an-grid cols-3" style="margin: 0;">
          ${MA.canvasCard('Recency (median days)', 'Lower = bought more recently.', { id: 'seg-r', height: 'short' })}
          ${MA.canvasCard('Frequency (median invoices)', 'Distinct purchase invoices.', { id: 'seg-f', height: 'short' })}
          ${MA.canvasCard('Monetary (median £)', 'Purchases minus own cancellations.', { id: 'seg-m', height: 'short' })}</div>
          <div style="margin-top: 18px;">${MA.canvasCard('Each customer: recency vs spend', 'Log-scaled spend axis; colour = segment. Up to 2,500 customers shown.', { id: 'seg-scatter', height: 'tall' })}</div>`,
        { hint: 'medians per segment and customer scatter', id: 'seg-charts' })}
      ${MA.details('Customer-level RFM table', `<div class="an-btn-row" style="margin-bottom: 10px;">
            <select class="an-select" id="seg-filter" style="width: 170px;" aria-label="Filter by segment"><option value="">All segments</option>
              ${cl.map((c) => `<option value="${c.cluster}">Segment ${c.cluster}</option>`).join('')}</select>
            <input class="an-input" id="seg-search" placeholder="Customer ID or country…" style="width: 210px;" aria-label="Search customers">
            <button class="an-btn sm" id="seg-export" type="button">⤓ Export CSV</button></div>
          <p class="an-hint" style="margin-bottom: 10px;">Only the dataset's anonymised numeric customer ID and main country are shown.</p>
          <div id="seg-table"></div>`, { hint: `${fmt.int(r.customers.length)} customers` })}
      ${MA.details('Model details and evaluation', `
          <div class="an-stats" style="margin-bottom: 16px;">
            <div class="an-stat"><div class="l">Silhouette score</div><div class="v">${r.silhouette === null ? 'n/a' : fmt.num(r.silhouette, 3)}</div><div class="s">${esc(r.silhouette_note || '−1 to 1; higher = better separated')}</div></div>
            <div class="an-stat"><div class="l">Inertia (WCSS)</div><div class="v">${fmt.num(r.inertia, 0)}</div><div class="s">within-cluster sum of squares</div></div>
            <div class="an-stat"><div class="l">Customers excluded</div><div class="v">${fmt.int(exTotal)}</div><div class="s">${ex.no_eligible_purchase} with only cancellations · ${ex.non_positive_net_value} with net spend ≤ £0</div></div>
            <div class="an-stat"><div class="l">Reference date</div><div class="v">${esc(r.reference_date)}</div><div class="s">day after the last purchase</div></div>
            <div class="an-stat"><div class="l">Features</div><div class="v" style="font-size: 0.95rem;">${esc(r.features)}</div><div class="s">K-Means, 10 starts, seed ${r.params.seed}</div></div>
          </div>
          <div class="an-grid cols-2" style="margin: 0;">
            ${MA.canvasCard('Choosing the number of segments', 'Silhouette score for k = 2…10 (selected k highlighted).', { id: 'seg-elbow' })}
            ${MA.card('Elbow table', '<div id="seg-elbow-table"></div>')}
          </div>
          <div class="an-grid cols-3" style="margin: 18px 0 0;">
            ${MA.canvasCard('Recency distribution', `Clipped at ${fmt.int(r.distributions.recency_days.clipped_at_p99)} days (99th percentile).`, { id: 'seg-hr', height: 'short' })}
            ${MA.canvasCard('Frequency distribution', `Clipped at ${fmt.int(r.distributions.frequency.clipped_at_p99)} invoices.`, { id: 'seg-hf', height: 'short' })}
            ${MA.canvasCard('Monetary distribution', `Clipped at ${fmt.money(r.distributions.monetary.clipped_at_p99)}.`, { id: 'seg-hm', height: 'short' })}
          </div>`, { hint: 'silhouette, inertia, elbow, distributions', id: 'seg-model' })}`;

    chart($('#seg-size'), {
      type: 'bar',
      data: { labels: cl.map((c) => `Segment ${c.cluster}`), datasets: [{ data: cl.map((c) => c.size), backgroundColor: cl.map((c) => color(c.cluster)), maxBarThickness: 56 }] },
      options: { plugins: { legend: { display: false }, tooltip: { callbacks: { title: (c) => `Segment ${cl[c[0].dataIndex].cluster}: ${cl[c[0].dataIndex].profile}`,
        label: (c) => `${fmt.int(c.raw)} customers (${fmt.pct(cl[c.dataIndex].share)})` } } }, scales: { x: axis.cat(), y: axis.count() } },
    });

    const table = renderTable($('#seg-table'), {
      caption: 'Customer segment assignments', pageSize: 20, sort: { key: 'monetary', dir: 'desc' },
      columns: [
        { key: 'customer_id', label: 'Customer ID' }, { key: 'country', label: 'Country' },
        { key: 'recency_days', label: 'Recency (days)', num: true, format: fmt.int },
        { key: 'frequency', label: 'Invoices', num: true, format: fmt.int },
        { key: 'monetary', label: 'Spend £', num: true, format: (v) => fmt.money2(v) },
        { key: 'cluster', label: 'Segment', num: true, render: (x) => `<span class="an-swatch" style="background: ${color(x.cluster)}"></span>${x.cluster}` },
      ],
      rows: r.customers,
    });
    const refilter = () => {
      const c = $('#seg-filter').value, q = $('#seg-search').value.trim().toLowerCase();
      table.update(r.customers.filter((x) => (!c || String(x.cluster) === c) && (!q || x.customer_id.includes(q) || (x.country || '').toLowerCase().includes(q))));
    };
    $('#seg-filter').addEventListener('change', refilter);
    $('#seg-search').addEventListener('input', MA.debounce(refilter, 200));
    $('#seg-export').addEventListener('click', () => {
      const c = $('#seg-filter').value;
      download(`/api/analytics/segmentation/${current.id}/export${c ? '?cluster=' + c : ''}`).catch((e) => alert(e.message));
    });
    renderTable($('#seg-elbow-table'), { caption: 'Elbow and silhouette by k', columns: [
      { key: 'k', label: 'k', num: true }, { key: 'inertia', label: 'Inertia', num: true, format: (v) => fmt.num(v, 0) },
      { key: 'silhouette', label: 'Silhouette', num: true, format: (v) => fmt.num(v, 3) }], rows: r.elbow, note: `selected k = ${r.params.k}` });

    // Charts inside collapsed panels are drawn when the panel is opened
    const drawRfm = () => {
      const bars = (id, key, f) => chart($(id), {
        type: 'bar',
        data: { labels: cl.map((c) => `S${c.cluster}`), datasets: [{ data: cl.map((c) => c.median[key]), backgroundColor: cl.map((c) => color(c.cluster)), maxBarThickness: 40 }] },
        options: { plugins: { legend: { display: false }, tooltip: { callbacks: { title: (c) => `Segment ${cl[c[0].dataIndex].cluster}`, label: (c) => f(c.raw) } } },
          scales: { x: axis.cat(), y: key === 'monetary' ? axis.money() : axis.count() } },
      });
      bars('#seg-r', 'recency_days', (v) => `${fmt.int(v)} days`);
      bars('#seg-f', 'frequency', (v) => `${fmt.num(v, 1)} invoices`);
      bars('#seg-m', 'monetary', (v) => fmt.money(v));
      const step = Math.max(1, Math.ceil(r.customers.length / 2500));
      const sample = r.customers.filter((_, i) => i % step === 0);
      chart($('#seg-scatter'), {
        type: 'scatter',
        data: { datasets: cl.map((c) => ({ label: `Segment ${c.cluster}`, backgroundColor: color(c.cluster), borderColor: '#FFFFFF', borderWidth: 1, pointRadius: 3.5, pointHoverRadius: 6,
          data: sample.filter((x) => x.cluster === c.cluster).map((x) => ({ x: x.recency_days, y: Math.max(x.monetary, 1), id: x.customer_id, f: x.frequency })) })) },
        options: { interaction: { mode: 'nearest', intersect: true },
          plugins: { legend: { position: 'top', align: 'start' }, tooltip: { callbacks: { label: (c) => `Customer ${c.raw.id}: ${c.raw.x} days, ${c.raw.f} invoices, ${fmt.money(c.raw.y)}` } } },
          scales: { x: { ...axis.count(), title: { display: true, text: 'Recency (days)' } },
                    y: { type: 'logarithmic', grid: { color: MA.INK.grid }, border: { display: false }, title: { display: true, text: 'Spend (£, log scale)' }, ticks: { callback: (v) => [1, 10, 100, 1000, 10000, 100000].includes(v) ? '£' + fmt.compact(v) : '' } } } },
      });
    };
    const drawModel = () => {
      const el = r.elbow;
      chart($('#seg-elbow'), {
        type: 'line',
        data: { labels: el.map((e) => 'k=' + e.k), datasets: [{ label: 'Silhouette', data: el.map((e) => e.silhouette), borderColor: MA.BRAND, backgroundColor: MA.BRAND,
          pointRadius: el.map((e) => e.k === r.params.k ? 7 : 4), pointBackgroundColor: el.map((e) => e.k === r.params.k ? '#FFFFFF' : MA.BRAND), pointBorderWidth: 2 }] },
        options: { plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => `silhouette ${fmt.num(c.raw, 3)} · inertia ${fmt.num(el[c.dataIndex].inertia, 0)}` } } },
          scales: { x: axis.cat(), y: { ...axis.count(), ticks: { callback: (v) => fmt.num(v, 2) } } } },
      });
      const hist = (id, h, f) => chart($(id), {
        type: 'bar',
        data: { labels: h.edges.slice(0, -1).map((e, i) => `${f(e)}–${f(h.edges[i + 1])}`), datasets: [{ data: h.counts, backgroundColor: PALETTE[1], barPercentage: 1, categoryPercentage: 0.94 }] },
        options: { plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => `${fmt.int(c.raw)} customers` } } },
          scales: { x: axis.cat({ ticks: { maxTicksLimit: 5, maxRotation: 0 } }), y: axis.count() } },
      });
      hist('#seg-hr', r.distributions.recency_days, (v) => fmt.int(v));
      hist('#seg-hf', r.distributions.frequency, (v) => fmt.num(v, 0));
      hist('#seg-hm', r.distributions.monetary, (v) => '£' + fmt.compact(v));
    };
    const p1 = $('#seg-charts'), p2 = $('#seg-model');
    p1.addEventListener('toggle', () => { if (p1.open) drawRfm(); });
    p2.addEventListener('toggle', () => { if (p2.open) drawModel(); });
  }

  MA.register('segments', { init });
})();
