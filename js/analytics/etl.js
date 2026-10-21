/* MIGRIGA ANALYTICS - Data Warehouse & ETL: status summary, real pipeline execution and data-quality details */
(() => {
  const { api, esc, fmt, chart, axis, renderTable, errorBox, BRAND, $ } = MA;
  let root, polling = false;

  function init() { root = $('#etl-root'); }
  function show() { load(); }

  const badge = (s) => {
    const cls = { SUCCESS: 'ok', SKIPPED_UNCHANGED: 'neutral', RUNNING: 'warn', FAILED: 'bad', INTERRUPTED: 'bad' }[s] || 'neutral';
    const label = { SUCCESS: 'Success', SKIPPED_UNCHANGED: 'Skipped (unchanged)', RUNNING: 'Running', FAILED: 'Failed', INTERRUPTED: 'Interrupted' }[s] || s;
    return `<span class="an-badge ${cls}">${esc(label)}</span>`;
  };

  async function load() {
    try {
      const s = await api('/api/analytics/etl/status');
      render(s);
      if (s.running_job && !polling) poll(s.running_job.id);
    } catch (e) { root.innerHTML = errorBox(e); }
  }

  function tile(label, value, sub) {
    return `<div class="an-stat"><div class="l">${label}</div><div class="v" style="font-size: 1.1rem;">${value}</div><div class="s">${sub}</div></div>`;
  }

  function render(s) {
    const last = s.last_success, q = last?.quality || {}, ex = q.extract || {}, ver = q.verification;
    const run = s.runs[0];
    const whOk = s.warehouse_exists && last && (s.table_counts.fact_sales || 0) > 0;
    root.innerHTML = `
      ${MA.pageHead('Data management', 'Data Warehouse &amp; ETL', '')}
      ${MA.intro('The <strong>ETL pipeline</strong> (Extract, Transform, Load) reads the raw CSV, cleans and checks every row, and loads it into a separate <strong>star-schema data warehouse</strong> that all analytics pages query.',
        `Source file <code>data/raw/${esc(s.dataset.source_file)}</code> (never modified). Warehouse: one fact table, <code>fact_sales</code>, with four dimension tables (date, product, customer, country), plus staging and audit tables.`)}
      <div class="an-card">
        <div class="an-card-header"><h2 class="an-card-title">Status</h2>
          ${whOk ? '<span class="an-badge ok">✓ Warehouse ready</span>' : '<span class="an-badge warn">Warehouse needs loading</span>'}</div>
        <div class="an-stats">
          ${tile('Source file', s.dataset.source_present ? '✓ Found' : '✕ Missing', s.dataset.source_present ? esc(s.dataset.source_file) : 'Place the CSV in data/raw/')}
          ${tile('Last ETL run', run ? `#${run.run_id} ${badge(run.status)}` : 'Never', run ? esc(run.started_at.replace('T', ' ')) : 'Click Run ETL below')}
          ${tile('Rows processed', last ? fmt.int(last.rows_read) : '—', last ? `${fmt.int(last.rows_loaded)} loaded into fact_sales` : '')}
          ${tile('Rows rejected', last ? fmt.int(last.rows_rejected) : '—', last ? (last.rows_rejected ? 'see Rejected rows below' : 'every row passed validation') : '')}
          ${tile('Warehouse status', ver ? (ver.passed ? '✓ Checks passed' : '✕ Checks failed') : '—', ver ? 'row counts, totals & keys verified' : '')}
        </div>
        <div style="margin-top: 16px;" class="an-controls">
          <button class="an-btn primary" id="etl-run" type="button" ${s.running_job ? 'disabled' : ''}>▶ Run ETL</button>
          <label class="an-check"><input type="checkbox" id="etl-force"> Rebuild even if the file has not changed</label>
        </div>
        <div style="margin-top: 12px;"><div class="an-progress" aria-hidden="true"><span id="etl-bar" style="width: ${s.running_job ? s.running_job.progress : 0}%"></span></div>
          <div class="an-status-line" id="etl-msg" aria-live="polite">${s.running_job ? 'Running: ' + esc(s.running_job.message) : 'Rerunning is safe: an unchanged file is skipped, and a changed file is reloaded in one all-or-nothing transaction.'}</div></div>
      </div>
      ${last ? `
      ${MA.card('What the cleaning found', `<div class="an-stats">
          ${tile('Date range', `${esc((q.date_min || '').slice(0, 10))} → ${esc((q.date_max || '').slice(0, 10))}`, '')}
          ${tile('Invoices', fmt.int(q.distinct_invoices), `${fmt.int(q.cancellation_invoices)} cancellations`)}
          ${tile('Customers', fmt.int(q.distinct_customers), `${fmt.int(q.missing_customer_lines)} lines without a customer ID`)}
          ${tile('Duplicate lines', fmt.int(q.duplicate_lines_flagged), 'kept but excluded from totals')}
          ${tile('Postage / fee lines', fmt.int(q.non_product_lines), 'excluded from product sales')}
        </div>`, { sub: 'Key data-quality numbers from the last successful load. Full details below.' })}
      ${MA.details('Data-quality profile', `<div class="an-stats" style="margin-bottom: 14px;">
            ${tile('Products (stock codes)', fmt.int(q.distinct_products), `${fmt.int(q.stock_codes_case_normalized)} lines case-normalised`)}
            ${tile('Countries', fmt.int(q.distinct_countries), '')}
            ${tile('Exact duplicate rows', fmt.int(q.exact_duplicate_rows_raw), 'identical on all 8 columns')}
            ${tile('Negative quantity', fmt.int(q.negative_quantity_lines), 'cancellations + stock adjustments')}
            ${tile('Zero / negative price', fmt.int(q.zero_price_lines), `${q.negative_price_lines} negative (bad-debt adjustments)`)}
            ${tile('Missing description', fmt.int(q.missing_description_lines), 'product’s usual description used')}</div>
          <h3 class="an-label" style="margin: 6px 0 8px;">Missing values by source column</h3><div id="etl-missing"></div>`, { hint: 'missing values, duplicates, invalid values' })}
      ${MA.details('How each line was classified', `<div class="an-chart"><canvas id="etl-types" role="img" aria-label="Fact lines by classification"></canvas></div>
          <ul class="an-hint" style="font-size: 0.82rem; line-height: 1.7; margin: 10px 0 0 18px; list-style: disc;">
            <li><strong>SALE</strong>: normal purchase (quantity &gt; 0, price &gt; 0) — counted in sales.</li>
            <li><strong>CANCELLATION</strong>: invoice starting with “C” — subtracted for net sales.</li>
            <li><strong>STOCK_ADJUSTMENT</strong>, <strong>ZERO_PRICE</strong>, <strong>ADJUSTMENT</strong>: kept for traceability but not counted as sales.</li></ul>`, { hint: 'SALE, CANCELLATION, adjustments', id: 'etl-types-panel' })}
      ${MA.details('Warehouse tables', '<div id="etl-tables"></div>', { hint: 'star schema row counts' })}
      ${MA.details('Load verification', ver ? `<ul class="an-hint" style="font-size: 0.84rem; line-height: 1.8; margin-left: 18px; list-style: disc;">
            <li>Fact rows ${fmt.int(ver.fact_rows)} = expected ${fmt.int(ver.expected_fact_rows)} ${ver.row_count_match ? '✓' : '✕'}</li>
            <li>Σ line amount £${fmt.num(ver.line_amount_total)} matches the transform ${ver.amount_match ? '✓' : '✕'}</li>
            <li>Foreign-key violations: ${ver.foreign_key_violations} · orphan keys: ${Object.values(ver.orphan_foreign_keys).reduce((a, b) => a + b, 0)} · duplicate fingerprints: ${ver.duplicate_fingerprints}</li>
            <li>Source SHA-256: <code>${esc(ex.source_sha256 || '')}</code></li></ul>` : 'No verification data.', { hint: 'counts, totals, referential integrity' })}` : ''}
      ${MA.details('Run history', '<div id="etl-runs"></div>', { hint: `${s.runs.length} recent runs (etl_run_log)` })}
      ${MA.details('Rejected rows', '<div id="etl-rejected"><div class="an-state">Loading…</div></div>', { hint: last ? `${fmt.int(last.rows_rejected)} in the last load` : '' })}`;

    $('#etl-run').addEventListener('click', start);
    if (last) {
      renderTable($('#etl-missing'), { caption: 'Missing values per column', columns: [
        { key: 'col', label: 'Column' }, { key: 'n', label: 'Blank values', num: true, format: fmt.int },
        { key: 'pct', label: '% of rows', num: true, format: (v) => fmt.pct(v, 2) },
        { key: 'policy', label: 'How it is handled', sortable: false }],
        rows: Object.entries(q.missing_values || {}).map(([col, n]) => ({ col, n, pct: n / q.rows_read, policy: POLICY[col] || '—' })) });
      renderTable($('#etl-tables'), { caption: 'Warehouse table row counts', columns: [
        { key: 't', label: 'Table', render: (r) => `<code>${esc(r.t)}</code>` }, { key: 'role', label: 'Role', sortable: false }, { key: 'n', label: 'Rows', num: true, format: fmt.int }],
        rows: Object.entries(s.table_counts).map(([t, n]) => ({ t, n, role: ROLES[t] || '' })) });
      const panel = $('#etl-types-panel');
      panel.addEventListener('toggle', () => {
        if (!panel.open) return;
        const types = Object.entries(s.line_type_counts || {});
        chart($('#etl-types'), {
          type: 'bar',
          data: { labels: types.map(([t]) => t), datasets: [{ data: types.map(([, n]) => n), backgroundColor: BRAND, maxBarThickness: 24 }] },
          options: { indexAxis: 'y', interaction: { mode: 'nearest', intersect: false, axis: 'y' },
            plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => `${fmt.int(c.raw)} lines (${fmt.pct(c.raw / last.rows_loaded, 2)})` } } },
            scales: { x: { type: 'logarithmic', grid: { color: MA.INK.grid }, border: { display: false }, ticks: { callback: (v) => [1, 10, 100, 1000, 10000, 100000, 1000000].includes(v) ? fmt.compact(v) : '' }, title: { display: true, text: 'Lines (log scale)' } },
                      y: axis.cat({ ticks: { color: MA.INK.text } }) } },
        });
      });
    }
    renderTable($('#etl-runs'), { caption: 'ETL run history', sort: { key: 'run_id', dir: 'desc' }, columns: [
      { key: 'run_id', label: '#', num: true }, { key: 'status', label: 'Status', render: (r) => badge(r.status) },
      { key: 'started_at', label: 'Started', cls: 'nowrap', format: (v) => esc((v || '').replace('T', ' ')) }, { key: 'triggered_by', label: 'Started by' },
      { key: 'rows_read', label: 'Read', num: true, format: fmt.int }, { key: 'rows_rejected', label: 'Rejected', num: true, format: fmt.int },
      { key: 'rows_loaded', label: 'Loaded', num: true, format: fmt.int }, { key: 'elapsed_seconds', label: 'Seconds', num: true, format: (v) => fmt.num(v, 1) },
      { key: 'notes', label: 'Notes', sortable: false, render: (r) => esc(r.error_message || (r.warnings || []).join(' ')) }], rows: s.runs });
    loadRejected();
  }

  const POLICY = {
    InvoiceNo: 'Row rejected (missing invoice number)', StockCode: 'Row rejected (missing stock code)',
    Description: 'Kept; the product’s usual description is used', Quantity: 'Row rejected (invalid quantity)',
    InvoiceDate: 'Row rejected (invalid date)', UnitPrice: 'Row rejected (invalid price)',
    CustomerID: 'Kept as an anonymous purchase; never given a made-up ID', Country: "Recorded as 'Unknown'",
  };
  const ROLES = { dim_date: 'Dimension', dim_product: 'Dimension', dim_customer: 'Dimension (key 0 = anonymous)', dim_country: 'Dimension',
    fact_sales: 'Fact table (one row per invoice line)', stg_raw_sales: 'Staging (raw text copy)', etl_rejected_rows: 'Audit', etl_run_log: 'Audit' };

  async function loadRejected() {
    const el = $('#etl-rejected');
    try {
      const { rejected } = await api('/api/analytics/etl/rejected?limit=100');
      if (!rejected.length) { el.innerHTML = '<div class="an-state">No rows were rejected — every source record passed validation.</div>'; return; }
      renderTable(el, { caption: 'Rejected rows', pageSize: 20, columns: [
        { key: 'source_row_number', label: 'Source row', num: true }, { key: 'reason', label: 'Reason' },
        { key: 'raw', label: 'Raw record', sortable: false, render: (r) => `<code>${esc(JSON.stringify(r.raw_record))}</code>` }], rows: rejected });
    } catch (e) { el.innerHTML = e.code === 'warehouse_unavailable' ? '<div class="an-state">Warehouse not loaded yet.</div>' : errorBox(e); }
  }

  async function start() {
    const btn = $('#etl-run');
    btn.disabled = true;
    try {
      const { job } = await api('/api/analytics/etl/run', { method: 'POST', body: { force: $('#etl-force').checked } });
      poll(job.id);
    } catch (e) { $('#etl-msg').textContent = e.message; btn.disabled = false; }
  }

  async function poll(id) {
    polling = true;
    let final = null;
    try {
      for (;;) {
        const { job } = await api(`/api/analytics/jobs/${id}`);
        const bar = $('#etl-bar'), msg = $('#etl-msg');
        if (bar) bar.style.width = job.progress + '%';
        if (msg) msg.textContent = `Running: ${job.message}`;
        if (job.status === 'done' || job.status === 'failed') { final = job; break; }
        await new Promise((r) => setTimeout(r, 1000));
      }
    } catch (e) { /* surfaced by the next status load */ }
    polling = false;
    await MA.loadOverview();
    await load();
    const msg = $('#etl-msg');
    if (msg && final) {
      msg.innerHTML = final.status === 'failed'
        ? `<span style="color: var(--an-bad)">ETL failed: ${esc(final.error)}</span>`
        : `<span style="color: var(--an-good)">✓ ETL finished: ${esc(final.result.status.replace('_', ' ').toLowerCase())}, ${fmt.int(final.result.rows_loaded)} rows loaded.</span>`;
    }
  }

  MA.register('etl', { init, show });
})();
