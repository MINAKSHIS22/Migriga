/* MIGRIGA ANALYTICS - OLAP Explorer (POST /api/analytics/olap)
   Roll-up / drill-down along year > quarter > month > day, slice, dice and pivot.
   Every control change runs a real parameterised query against the warehouse. */
(() => {
  const { api, download, esc, fmt, chart, axis, renderTable, FilterBar, errorBox, BRAND, PALETTE, $ } = MA;
  const TIME = ['year', 'quarter', 'month', 'day'];
  const DEFAULT = { rows: 'month', columns: null, measure: 'net_sales', sort: 'natural', limit: 500, slices: {} };
  let st = structuredClone(DEFAULT), bar, root, last, reqSeq = 0, pendingPreset = null, openPanel = null;

  const dims = () => MA.state.overview?.olap?.dimensions || [];
  const measures = () => MA.state.overview?.olap?.measures || [];
  const dimLabel = (id) => dims().find((d) => d.id === id)?.label || id;

  function init() {
    root = $('#olap-root');
    const opt = (list, sel, none) => (none ? `<option value="">${none}</option>` : '') + list.map((d) => `<option value="${d.id}" ${d.id === sel ? 'selected' : ''}>${esc(d.label)}</option>`).join('');
    root.innerHTML = `
      ${MA.pageHead('Explore data', 'OLAP Explorer', '')}
      ${MA.intro('Summarises and explores sales across <strong>time, products, countries and customers</strong>. Pick a measure and a dimension, then use the five OLAP operations to zoom out, zoom in, filter or compare.',
        'The sales cube: <code>fact_sales</code> joined to <code>dim_date</code>, <code>dim_product</code>, <code>dim_country</code> and <code>dim_customer</code>. Eligible merchandise sale and cancellation lines only.')}
      <div class="an-card">
        <div class="an-step">Controls</div>
        <div class="an-controls" style="margin-bottom: 14px;">
          <div class="an-field"><label for="olap-measure">Show</label><select class="an-select" id="olap-measure">${opt(measures(), st.measure)}</select></div>
          <div class="an-field"><label for="olap-rows">Grouped by</label><select class="an-select" id="olap-rows">${opt(dims(), st.rows)}</select></div>
        </div>
        <div class="an-label" style="margin-bottom: 6px;">OLAP operations</div>
        <div class="an-btn-row an-op">
          <button class="an-btn" id="olap-rollup" type="button">↑ Summarise <small>(Roll-up)</small></button>
          <button class="an-btn" id="olap-drill" type="button">↓ More detail <small>(Drill-down)</small></button>
          <button class="an-btn" data-panel="slice" type="button">◎ One value only <small>(Slice)</small></button>
          <button class="an-btn" data-panel="dice" type="button">⧉ Several filters <small>(Dice)</small></button>
          <button class="an-btn" data-panel="pivot" type="button">⇄ Compare side by side <small>(Pivot)</small></button>
          <button class="an-btn ghost" id="olap-reset" type="button">Reset</button>
        </div>
        <p class="an-hint" id="olap-op-hint" style="margin-top: 8px;">Roll-up and drill-down move along Year › Quarter › Month › Day. Tip: click a row in the results to drill into it.</p>

        <div data-pane="slice" hidden style="margin-top: 14px;">
          <div class="an-controls">
            <div class="an-field"><label for="olap-slice-dim">Keep only rows where</label><select class="an-select" id="olap-slice-dim">
              ${['year', 'quarter', 'month', 'weekday', 'country', 'line_type'].map((d) => `<option value="${d}">${esc(dimLabel(d))}</option>`).join('')}</select></div>
            <div class="an-field grow"><label for="olap-slice-val">equals</label><input class="an-input" id="olap-slice-val" placeholder="e.g. 2010, 2010-Q4, 2010-11, Friday, France"></div>
            <button class="an-btn primary" id="olap-slice-add" type="button">Apply slice</button>
          </div>
        </div>
        <div data-pane="dice" hidden style="margin-top: 14px;"><div id="olap-dice"></div></div>
        <div data-pane="pivot" hidden style="margin-top: 14px;">
          <div class="an-controls">
            <div class="an-field"><label for="olap-cols">Put this dimension in columns</label><select class="an-select" id="olap-cols">${opt(dims(), st.columns, 'None (no pivot)')}</select></div>
            <button class="an-btn" id="olap-swap" type="button">⇄ Swap rows and columns</button>
          </div>
        </div>

        <div class="an-chips" id="olap-chips" aria-live="polite" style="margin-top: 14px;"></div>
        <div class="an-chips" id="olap-dice-chips"></div>
      </div>
      <div id="olap-result"></div>
      ${MA.details('Advanced options', `<div class="an-controls">
          <div class="an-field"><label for="olap-sort">Sort rows</label><select class="an-select" id="olap-sort">
            <option value="natural">Natural / time order</option><option value="measure_desc">Largest first</option><option value="measure_asc">Smallest first</option></select></div>
          <div class="an-field"><label for="olap-limit">Maximum rows</label><select class="an-select" id="olap-limit">
            ${[25, 50, 100, 500, 1000, 5000].map((n) => `<option ${n === st.limit ? 'selected' : ''}>${n}</option>`).join('')}</select></div></div>`, { hint: 'sorting and row limit' })}
      ${MA.details('Technical details', '<div id="olap-tech" class="an-explain">Run a query to see its SQL.</div>', { hint: 'operation summary and generated SQL' })}`;

    bar = new FilterBar($('#olap-dice'), { onChange: run, fields: ['date', 'countries', 'products', 'customers'], chipsEl: $('#olap-dice-chips'), inline: true });
    bar.renderChips(false);
    $('#olap-measure').addEventListener('change', (e) => { st.measure = e.target.value; run(); });
    $('#olap-rows').addEventListener('change', (e) => { st.rows = e.target.value; if (st.columns === st.rows) st.columns = null; sync(); run(); });
    $('#olap-cols').addEventListener('change', (e) => { st.columns = e.target.value || null; if (st.columns === st.rows) st.columns = null; sync(); run(); });
    $('#olap-sort').addEventListener('change', (e) => { st.sort = e.target.value; run(); });
    $('#olap-limit').addEventListener('change', (e) => { st.limit = Number(e.target.value); run(); });
    $('#olap-rollup').addEventListener('click', rollUp);
    $('#olap-drill').addEventListener('click', () => drillDown(null));
    $('#olap-swap').addEventListener('click', pivot);
    $('#olap-reset').addEventListener('click', () => { st = structuredClone(DEFAULT); bar.set({}); togglePanel(null); sync(); run(); });
    root.querySelectorAll('[data-panel]').forEach((b) => b.addEventListener('click', () => togglePanel(openPanel === b.dataset.panel ? null : b.dataset.panel)));
    $('#olap-slice-add').addEventListener('click', () => {
      const d = $('#olap-slice-dim').value, v = $('#olap-slice-val').value.trim();
      if (!v) return;
      addSlice(d, v); $('#olap-slice-val').value = '';
    });
    $('#olap-slice-val').addEventListener('keydown', (e) => { if (e.key === 'Enter') $('#olap-slice-add').click(); });
    if (pendingPreset) { applyState(pendingPreset); pendingPreset = null; } else { sync(); run(); }
  }

  function togglePanel(name) {
    openPanel = name;
    root.querySelectorAll('[data-pane]').forEach((p) => { p.hidden = p.dataset.pane !== name; });
    root.querySelectorAll('[data-panel]').forEach((b) => b.classList.toggle('active', b.dataset.panel === name));
  }

  function payload() {
    return { rows: st.rows, columns: st.columns, measure: st.measure, sort: st.sort, limit: st.limit, slices: st.slices, filters: bar.get() };
  }

  function sync() {
    $('#olap-rows').value = st.rows;
    $('#olap-cols').value = st.columns || '';
    $('#olap-measure').value = st.measure;
    $('#olap-sort').value = st.sort;
    $('#olap-limit').value = String(st.limit);
    const ti = TIME.indexOf(st.rows);
    $('#olap-rollup').disabled = ti <= 0;
    $('#olap-drill').disabled = ti < 0 || ti >= TIME.length - 1;
    $('#olap-swap').disabled = !st.columns;
    root.querySelector('[data-panel="pivot"]').classList.toggle('active', openPanel === 'pivot' || !!st.columns);
    $('#olap-op-hint').textContent = ti < 0
      ? 'Roll-up and drill-down work on the time hierarchy: choose Year, Quarter, Month or Day under “Grouped by”. Click a row to slice on it.'
      : 'Roll-up and drill-down move along Year › Quarter › Month › Day. Tip: click a row in the results to drill into it.';
    renderSliceChips();
  }

  function renderSliceChips() {
    const el = $('#olap-chips');
    const entries = Object.entries(st.slices);
    const crumbs = ['All time'].concat(TIME.filter((t) => st.slices[t]).map((t) => st.slices[t]));
    el.innerHTML = `<div class="an-breadcrumb" style="margin-right: 14px;"><span class="an-chip-label">Drill path</span>${crumbs.map((c, i) =>
      i < crumbs.length - 1 ? `<button type="button" data-crumb="${i}">${esc(c)}</button><span class="sep">›</span>` : `<strong>${esc(c)}</strong> <span class="an-hint">(by ${esc(dimLabel(st.rows).toLowerCase())})</span>`).join('')}</div>`
      + (entries.length ? `<span class="an-chip-label">Slices</span>` + entries.map(([d, v]) =>
        `<span class="an-chip"><span>${esc(dimLabel(d))} = ${esc(v)}</span><button type="button" aria-label="Remove slice ${esc(dimLabel(d))}" data-slice="${d}">×</button></span>`).join('') : '');
    el.querySelectorAll('[data-slice]').forEach((b) => b.addEventListener('click', () => { delete st.slices[b.dataset.slice]; sync(); run(); }));
    el.querySelectorAll('[data-crumb]').forEach((b) => b.addEventListener('click', () => {
      const keep = TIME.filter((t) => st.slices[t]).slice(0, Number(b.dataset.crumb));
      TIME.forEach((t) => { if (!keep.includes(t)) delete st.slices[t]; });
      st.rows = TIME[keep.length]; st.columns = st.columns === st.rows ? null : st.columns; sync(); run();
    }));
  }

  function addSlice(dim, value) {
    st.slices[dim] = String(value);
    if (st.rows === dim) {
      const ti = TIME.indexOf(dim);
      st.rows = ti >= 0 && ti < TIME.length - 1 ? TIME[ti + 1] : (dim === 'country' ? 'month' : 'country');
    }
    if (st.columns === dim) st.columns = null;
    sync(); run();
  }

  function rollUp() {
    const ti = TIME.indexOf(st.rows);
    if (ti <= 0) return;
    const up = TIME[ti - 1];
    TIME.slice(ti - 1).forEach((t) => delete st.slices[t]);   // a roll-up removes the slice at the target level and below
    st.rows = up; if (st.columns === up) st.columns = null;
    sync(); run();
  }

  function drillDown(member) {
    const ti = TIME.indexOf(st.rows);
    if (ti < 0 || ti >= TIME.length - 1) return;
    if (member !== null && member !== undefined) st.slices[st.rows] = String(member);
    st.rows = TIME[ti + 1]; if (st.columns === st.rows) st.columns = null;
    sync(); run();
  }

  function pivot() {
    if (!st.columns) return;
    [st.rows, st.columns] = [st.columns, st.rows];
    sync(); run();
  }

  async function run() {
    const seq = ++reqSeq;
    const out = $('#olap-result');
    out.classList.add('an-loading');
    if (!last) out.innerHTML = '<div class="an-card"><div class="an-state">Running the OLAP query…</div></div>';
    try {
      const r = await api('/api/analytics/olap', { method: 'POST', body: payload() });
      if (seq !== reqSeq) return;
      last = r; render(r);
    } catch (e) {
      if (seq === reqSeq) out.innerHTML = errorBox(e);
    } finally {
      if (seq === reqSeq) out.classList.remove('an-loading');
    }
  }

  function interpretation(r, f) {
    if (!r.rows.length) return '';
    const additive = !['avg_order_value', 'customers', 'orders'].includes(r.measure) || r.mode === 'aggregate';
    const byValue = [...r.rows].sort((a, b) => (b.value || 0) - (a.value || 0));
    const top = byValue[0];
    let s = `<strong>${esc(r.measure_label)}</strong> by ${esc(r.rows_label.toLowerCase())}: the largest is <strong>${esc(top.member)}</strong> with ${f(top.value)}`;
    if (additive && r.grand_total && r.measure !== 'avg_order_value') s += ` (${fmt.pct(top.value / r.grand_total)} of the total ${f(r.grand_total)})`;
    s += '.';
    if (byValue.length > 1) s += ` The smallest shown is ${esc(byValue[byValue.length - 1].member)} (${f(byValue[byValue.length - 1].value)}).`;
    if (r.mode === 'pivot') s += ` Columns compare ${esc(r.columns_label.toLowerCase())} values side by side.`;
    if (Object.keys(r.slices).length) s += ` Only rows where ${Object.entries(r.slices).map(([d, v]) => `${esc(dimLabel(d))} = ${esc(v)}`).join(' and ')} are included.`;
    return s;
  }

  function render(r) {
    const out = $('#olap-result');
    const f = (v) => fmt.byKind(r.measure_format, v);
    out.innerHTML = `
      <div class="an-card">
        <div class="an-card-header"><h2 class="an-card-title">Results</h2>
          <button class="an-btn sm" id="olap-export" type="button">⤓ Export CSV</button></div>
        <div class="an-stats" style="margin-bottom: 14px;">
          <div class="an-stat"><div class="l">Total · ${esc(r.measure_label)}</div><div class="v">${f(r.grand_total)}</div></div>
          <div class="an-stat"><div class="l">Groups shown</div><div class="v">${fmt.int(r.returned_groups)} <span class="an-hint">of ${fmt.int(r.total_groups)}</span></div>${r.truncated ? '<div class="s">Raise “Maximum rows” in Advanced options to see all</div>' : ''}</div>
          <div class="an-stat"><div class="l">Fact rows summarised</div><div class="v">${fmt.int(r.fact_rows_scanned)}</div></div>
        </div>
        ${r.rows.length ? `<div class="an-interpret">${interpretation(r, f)}</div>
          <div class="an-chart tall"><canvas id="olap-chart" role="img" aria-label="OLAP result chart"></canvas></div>
          <p class="an-hint" id="olap-chart-note" style="margin: 6px 0 14px;"></p>` : ''}
        <div id="olap-table"></div>
      </div>`;
    $('#olap-export').addEventListener('click', async () => {
      try { await download('/api/analytics/olap/export', { method: 'POST', body: payload() }); } catch (e) { alert(e.message); }
    });
    $('#olap-tech').innerHTML = `<p><strong>Operation:</strong> ${esc(r.explanation)}</p>
      <div class="an-code">${esc(r.sql)}</div><div class="an-code">-- bound parameters (in order)\n${esc(JSON.stringify(r.sql_params))}</div>`;
    if (!r.rows.length) {
      $('#olap-table').innerHTML = '<div class="an-state">No sales match this combination. Remove a slice or filter, or click Reset.</div>';
      return;
    }
    const memberCol = { key: 'member', label: r.rows_label, cls: 'member-link', sortValue: (x) => x.member };
    const clickMember = (row) => { if (r.drill_down_to) drillDown(row.member); else addSlice(r.rows_dimension, row.member); };
    if (r.mode === 'aggregate') {
      const total = r.grand_total || 0;
      renderTable($('#olap-table'), {
        caption: 'OLAP aggregate result',
        columns: [memberCol,
          { key: 'value', label: r.measure_label, num: true, format: f },
          { key: 'share', label: '% of total', num: true, sortValue: (x) => x.value, render: (x) => (total && r.measure !== 'avg_order_value') ? fmt.pct(x.value / total) : '—' },
          { key: 'fact_rows', label: 'Fact rows', num: true, format: fmt.int }],
        rows: r.rows, onRowClick: clickMember,
        note: r.drill_down_to ? `click a ${r.rows_label.toLowerCase()} to drill down to ${r.drill_down_to}` : 'click a row to slice on it',
      });
      const shown = r.rows.slice(0, 80);
      chart($('#olap-chart'), {
        type: 'bar',
        data: { labels: shown.map((x) => short(String(x.member))), datasets: [{ label: r.measure_label, data: shown.map((x) => x.value), backgroundColor: BRAND, maxBarThickness: 36 }] },
        options: { onClick: (e, els) => { if (els[0]) clickMember(shown[els[0].index]); },
          plugins: { legend: { display: false }, tooltip: { callbacks: { title: (c) => String(shown[c[0].dataIndex].member), label: (c) => `${r.measure_label}: ${f(c.raw)}` } } },
          scales: { x: axis.cat(), y: r.measure_format === 'money' ? axis.money() : axis.count() } },
      });
      $('#olap-chart-note').textContent = r.rows.length > 80 ? `Chart shows the first 80 of ${r.rows.length} rows; the table lists all.` : 'Click a bar to drill down or slice.';
    } else {
      const cols = r.columns.map((c) => String(c.member));
      const columns = [memberCol].concat(cols.map((c, i) => ({ key: 'c' + i, label: c, num: true, sortValue: (x) => x.cells[i], render: (x) => f(x.cells[i]) })),
        [{ key: 'value', label: 'Row total', num: true, format: f }]);
      const additive = !['avg_order_value', 'customers', 'orders'].includes(r.measure);
      const footer = additive ? ['Total (shown rows)'].concat(cols.map((_, i) => f(r.rows.reduce((s, x) => s + (x.cells[i] || 0), 0))), [f(r.rows.reduce((s, x) => s + (x.value || 0), 0))]) : null;
      renderTable($('#olap-table'), { caption: 'OLAP pivot result', columns, rows: r.rows, onRowClick: clickMember, footer,
        note: r.columns_truncated ? `columns limited to the first ${cols.length}` : (additive ? '' : 'distinct counts and averages are not additive, so no column totals') });
      const series = cols.slice(0, 6);
      const shown = r.rows.slice(0, 40);
      chart($('#olap-chart'), {
        type: 'bar',
        data: { labels: shown.map((x) => short(String(x.member))),
          datasets: series.map((c, i) => ({ label: short(c, 28), data: shown.map((x) => x.cells[i]), backgroundColor: PALETTE[i], maxBarThickness: 26 })) },
        options: { plugins: { legend: { position: 'top', align: 'start' }, tooltip: { mode: 'index', callbacks: { label: (c) => `${c.dataset.label}: ${f(c.raw)}` } } },
          scales: { x: axis.cat(), y: r.measure_format === 'money' ? axis.money() : axis.count() } },
      });
      $('#olap-chart-note').textContent = `Grouped bars: ${r.rows_label.toLowerCase()} × ${r.columns_label.toLowerCase()}`
        + (cols.length > 6 ? ` (chart shows the first 6 of ${cols.length} columns; the table shows all).` : '.') + (r.rows.length > 40 ? ` First 40 of ${r.rows.length} rows charted.` : '');
    }
  }

  function short(s, n = 26) { return s.length > n ? s.slice(0, n - 1) + '…' : s; }

  function applyState(preset) {
    st = { ...structuredClone(DEFAULT), ...structuredClone(preset) };
    if (preset.filters) { bar.set(preset.filters); togglePanel('dice'); } else bar.set({});
    if (preset.columns) togglePanel('pivot');
    sync(); run();
  }

  /** Used by the Project Guide to open the explorer in a given state. */
  MA.openOlap = (preset) => {
    if (root) applyState(preset); else pendingPreset = preset;
    MA.go('olap');
  };

  MA.register('olap', { init });
})();
