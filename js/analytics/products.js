/* MIGRIGA ANALYTICS - Product and Country Analysis (GET /api/analytics/dashboard) */
(() => {
  const { esc, fmt, chart, axis, renderTable, FilterBar, errorBox, BRAND, PALETTE, $ } = MA;
  let body, bar, data, excludeUK = false, reqSeq = 0;

  function init() {
    const root = $('#products-root');
    root.innerHTML = `
      ${MA.pageHead('Explore data', 'Products &amp; Countries', '')}
      ${MA.intro('Shows <strong>what</strong> sells and <strong>where</strong>: the best-selling products by value and by quantity, and sales in every country.',
        '<code>fact_sales</code> joined to <code>dim_product</code> and <code>dim_country</code>. Merchandise lines only; postage and fees are excluded.')}
      <div id="pc-filters"></div>
      <div class="an-chips" id="pc-active" style="margin-bottom: 14px;"></div>
      <div id="pc-body"></div>`;
    body = $('#pc-body');
    bar = new FilterBar($('#pc-filters'), { onChange: load, fields: ['date', 'countries', 'products'], chipsEl: $('#pc-active') });
    bar.renderChips(false);
    load();
  }

  async function load() {
    const seq = ++reqSeq;
    body.classList.add('an-loading');
    if (!body.innerHTML) body.innerHTML = '<div class="an-state">Loading…</div>';
    try {
      const d = await MA.loadDashboardData(bar.get());
      if (seq === reqSeq) { data = d; render(); }
    } catch (e) { if (seq === reqSeq) body.innerHTML = errorBox(e); }
    finally { if (seq === reqSeq) body.classList.remove('an-loading'); }
  }

  function render() {
    const d = data, k = d.kpis;
    if (!k.orders) { body.innerHTML = '<div class="an-card"><div class="an-state">No eligible sales match these filters.</div></div>'; return; }
    const tp = d.top_products_value[0], tc = d.countries[0];
    const netTotal = d.countries.reduce((s, c) => s + (c.net || 0), 0);
    body.innerHTML = `
      <div class="an-interpret"><strong>In short:</strong> the top product is ${esc(tp.description)} (${fmt.money(tp.gross)}).
        The 10 best sellers make up ${fmt.pct(d.top10_product_share)} of gross sales across ${fmt.int(k.products_sold)} products, so sales are spread over a long tail of items.
        ${esc(tc.country)} accounts for ${fmt.pct(netTotal ? tc.net / netTotal : null)} of net sales.</div>
      <div class="an-grid cols-2">
        ${MA.canvasCard('Top 10 products by sales value', 'Gross sales value, £.', { id: 'pc-value', height: 'tall' })}
        ${MA.canvasCard('Top 10 products by quantity', 'Units sold.', { id: 'pc-qty', height: 'tall' })}
      </div>
      ${MA.card('Sales by country', `<div class="an-chart tall"><canvas id="pc-country" role="img" aria-label="Net sales by country"></canvas></div>`, {
        sub: 'Top 12 countries by net sales, £.',
        right: `<label class="an-check"><input type="checkbox" id="pc-ex-uk" ${excludeUK ? 'checked' : ''}> Hide United Kingdom to compare the others</label>` })}
      ${MA.details('Country table', '<div id="pc-country-table"></div>', { hint: `${d.countries.length} countries`, open: false })}
      ${MA.details('Product tables', '<div id="pc-prod-table"></div>', { hint: 'top 10 by value and quantity' })}
      <p class="an-hint">Need every product or a custom breakdown? Use the <a href="#olap">OLAP Explorer</a> with “Product” as the row dimension.</p>`;

    hbar('#pc-value', d.top_products_value, 'gross', BRAND, fmt.money, axis.money);
    hbar('#pc-qty', d.top_products_quantity, 'units', PALETTE[1], fmt.int, axis.count);
    drawCountries();
    $('#pc-ex-uk').addEventListener('change', (e) => { excludeUK = e.target.checked; drawCountries(); });
    renderTable($('#pc-country-table'), { caption: 'Sales by country', sort: { key: 'net', dir: 'desc' }, columns: [
      { key: 'country', label: 'Country' },
      { key: 'net', label: 'Net £', num: true, format: (v) => fmt.money(v) },
      { key: 'share', label: 'Share', num: true, sortValue: (r) => r.net, render: (r) => fmt.pct(netTotal ? r.net / netTotal : null) },
      { key: 'gross', label: 'Gross £', num: true, format: (v) => fmt.money(v) },
      { key: 'orders', label: 'Invoices', num: true, format: fmt.int }], rows: d.countries });
    const merged = d.top_products_value.map((p) => ({ ...p, list: 'By value' })).concat(d.top_products_quantity.map((p) => ({ ...p, list: 'By quantity' })));
    renderTable($('#pc-prod-table'), { caption: 'Top products', columns: [
      { key: 'list', label: 'List' }, { key: 'stock_code', label: 'Code' }, { key: 'description', label: 'Product' },
      { key: 'gross', label: 'Gross £', num: true, format: (v) => fmt.money(v) },
      { key: 'units', label: 'Units', num: true, format: fmt.int }], rows: merged });
  }

  function short(s, n = 30) { return s.length > n ? s.slice(0, n - 1) + '…' : s; }

  function hbar(sel, rows, key, color, f, ax) {
    chart($(sel), {
      type: 'bar',
      data: { labels: rows.map((r) => short(r.description)), datasets: [{ label: key, data: rows.map((r) => r[key]), backgroundColor: color, maxBarThickness: 20 }] },
      options: { indexAxis: 'y', interaction: { mode: 'nearest', intersect: false, axis: 'y' },
        plugins: { legend: { display: false }, tooltip: { callbacks: { title: (c) => `${rows[c[0].dataIndex].stock_code} · ${rows[c[0].dataIndex].description}`, label: (c) => f(c.raw) } } },
        scales: { x: ax(), y: axis.cat({ ticks: { color: MA.INK.text, font: { size: 11 } } }) } },
    });
  }

  function drawCountries() {
    const rows = data.countries.filter((c) => !excludeUK || c.country !== 'United Kingdom').slice(0, 12);
    const total = data.countries.reduce((s, c) => s + (c.net || 0), 0);
    chart($('#pc-country'), {
      type: 'bar',
      data: { labels: rows.map((r) => r.country), datasets: [{ label: 'Net sales', data: rows.map((r) => r.net), backgroundColor: BRAND, maxBarThickness: 20 }] },
      options: { indexAxis: 'y', interaction: { mode: 'nearest', intersect: false, axis: 'y' },
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => `${fmt.money(c.raw)} · ${fmt.pct(c.raw / total)} of all net · ${fmt.int(rows[c.dataIndex].orders)} invoices` } } },
        scales: { x: axis.money(), y: axis.cat({ ticks: { color: MA.INK.text } }) } },
    });
  }

  MA.register('products', { init });
})();
