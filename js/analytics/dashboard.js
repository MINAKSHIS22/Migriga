/* MIGRIGA ANALYTICS - Overview dashboard (GET /api/analytics/dashboard)
   Four KPIs, two charts, a country ranking, three insights and links to the detailed pages. */
(() => {
  const { esc, fmt, chart, axis, card, kpi, FilterBar, errorBox, BRAND, $ } = MA;
  let root, bar, body, reqSeq = 0;

  function init() {
    root = $('#dash-root');
    root.innerHTML = `
      ${MA.pageHead('Overview', 'Migriga Analytics', '')}
      <p class="an-subtitle" style="margin-top: -12px;">Retail Data Insights | Data Warehousing &amp; Data Mining</p>
      <div class="an-notice" role="note"><span aria-hidden="true">ℹ️</span><span>All figures come from the historical
        <em>Online Retail II</em> dataset (a UK gift retailer, Dec 2009 – Dec 2010, values in GBP £), loaded into the Migriga
        data warehouse. They are not verified Migriga sales.</span></div>
      <div id="dash-filters" style="margin-top: 16px;"></div>
      <div class="an-chips" id="dash-active" aria-live="polite" style="margin-bottom: 14px;"></div>
      <div id="dash-body"></div>`;
    body = $('#dash-body');
    bar = new FilterBar($('#dash-filters'), { onChange: load, fields: ['date'], chipsEl: $('#dash-active'), compact: true });
    bar.renderChips(false);
    load();
  }

  async function load() {
    const seq = ++reqSeq;
    body.classList.add('an-loading');
    if (!body.innerHTML) body.innerHTML = '<div class="an-state">Loading figures from the warehouse…</div>';
    try {
      const d = await MA.loadDashboardData(bar.get());
      if (seq === reqSeq) render(d);
    } catch (e) {
      if (seq === reqSeq) body.innerHTML = errorBox(e);
    } finally {
      if (seq === reqSeq) body.classList.remove('an-loading');
    }
  }

  function render(d) {
    const k = d.kpis;
    if (!k.orders) {
      body.innerHTML = `<div class="an-card"><div class="an-state">No eligible sales in this date range. Choose a range between
        ${esc(MA.state.overview?.filter_options?.date_min || '')} and ${esc(MA.state.overview?.filter_options?.date_max || '')}, or click Clear.</div></div>`;
      return;
    }
    const pick = (id) => d.insights.find((i) => i.id === id);
    const insights = ['best_month', 'top_product', 'top_country'].map(pick).filter(Boolean);
    const countries = d.countries.slice(0, 6);
    const maxC = Math.max(...countries.map((c) => c.net || 0), 1);
    const totalNet = d.countries.reduce((s, c) => s + (c.net || 0), 0);

    body.innerHTML = `
      <div class="an-kpis">
        ${kpi('Eligible sales value', fmt.money(k.net_sales), `Gross ${fmt.money(k.gross_sales)} minus cancellations ${fmt.money(k.cancelled_value)}`)}
        ${kpi('Number of invoices', fmt.int(k.orders), 'Distinct purchase invoices (orders)')}
        ${kpi('Units sold', fmt.int(k.units_sold), 'Total quantity on sale lines')}
        ${kpi('Identified customers', fmt.int(k.identified_customers), `${fmt.pct(k.anonymous_gross_share)} of sales had no customer ID`)}
      </div>

      <div class="an-grid cols-2">
        ${MA.canvasCard('Sales over time', 'Eligible (net) sales value per month, £.', { id: 'dash-trend' })}
        ${MA.canvasCard('Top products by sales value', 'Gross sales value of the 8 best-selling products, £.', { id: 'dash-top' })}
      </div>

      <div class="an-grid cols-2">
        ${card('Key insights', `<ol class="an-insights">${insights.map((i, n) => `<li><span class="n">${n + 1}</span><span>${esc(i.text)}</span></li>`).join('')}</ol>`,
          { sub: 'Calculated from the data for the selected period.' })}
        ${card('Top countries', `<ol class="an-rank">${countries.map((c, i) => `<li><span class="pos">${i + 1}</span><span>${esc(c.country)}</span>
            <span class="bar" aria-hidden="true"><span style="width: ${Math.max(1, (c.net / maxC) * 100)}%"></span></span>
            <span class="val">${fmt.money(c.net)}<small>${fmt.pct(totalNet ? c.net / totalNet : null)}</small></span></li>`).join('')}</ol>`,
          { sub: `Eligible sales by country (${fmt.int(d.countries.length)} countries in total).`, right: '<a class="an-btn sm ghost" href="#products">All countries →</a>' })}
      </div>

      ${card('Explore more', `<div class="an-explore">
          <a href="#sales"><strong>📈 Sales in more detail</strong><span>Monthly trend, weekdays, hours and cancellations.</span><span class="go">Sales Analysis →</span></a>
          <a href="#basket"><strong>🛍️ Products bought together</strong><span>Apriori finds items that often share an invoice.</span><span class="go">Market Basket →</span></a>
          <a href="#segments"><strong>👥 Customer segments</strong><span>Group customers by recency, frequency and spend.</span><span class="go">Customer Segments →</span></a>
          <a href="#etl"><strong>🗄️ The data warehouse</strong><span>How the CSV was cleaned and loaded into a star schema.</span><span class="go">Warehouse &amp; ETL →</span></a>
        </div>`)}`;

    const m = d.monthly;
    chart($('#dash-trend'), {
      type: 'line',
      data: { labels: m.map((r) => fmt.month(r.month)), datasets: [{ label: 'Net sales', data: m.map((r) => r.net), borderColor: BRAND,
        backgroundColor: 'rgba(176, 125, 98, 0.10)', fill: true, tension: 0.25, pointRadius: 3, pointBackgroundColor: BRAND }] },
      options: { plugins: { legend: { display: false }, tooltip: { callbacks: {
        label: (c) => `Net sales ${fmt.money(c.raw)}`, afterLabel: (c) => `${fmt.int(m[c.dataIndex].orders)} invoices` } } },
        scales: { x: axis.cat({ ticks: { maxRotation: 0, autoSkipPadding: 12 } }), y: axis.money({ beginAtZero: true }) } },
    });
    const top = d.top_products_value.slice(0, 8);
    chart($('#dash-top'), {
      type: 'bar',
      data: { labels: top.map((p) => short(p.description)), datasets: [{ label: 'Gross sales', data: top.map((p) => p.gross), backgroundColor: BRAND, maxBarThickness: 20 }] },
      options: { indexAxis: 'y', interaction: { mode: 'nearest', intersect: false, axis: 'y' },
        plugins: { legend: { display: false }, tooltip: { callbacks: { title: (c) => `${top[c[0].dataIndex].stock_code} · ${top[c[0].dataIndex].description}`,
          label: (c) => `${fmt.money(c.raw)} · ${fmt.int(top[c.dataIndex].units)} units` } } },
        scales: { x: axis.money(), y: axis.cat({ ticks: { color: MA.INK.text, font: { size: 11 } } }) } },
    });
  }

  function short(s, n = 30) { return s.length > n ? s.slice(0, n - 1) + '…' : s; }

  MA.register('dashboard', { init });
})();
