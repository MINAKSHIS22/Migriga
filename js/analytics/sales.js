/* MIGRIGA ANALYTICS - Sales Analysis: trends over time, weekday / hour patterns, cancellations
   and customer purchase frequency (GET /api/analytics/dashboard with the chosen filters). */
(() => {
  const { esc, fmt, chart, axis, renderTable, FilterBar, errorBox, BRAND, PALETTE, $ } = MA;
  let body, bar, reqSeq = 0;

  function init() {
    const root = $('#sales-root');
    root.innerHTML = `
      ${MA.pageHead('Explore data', 'Sales Analysis', '')}
      ${MA.intro('Shows <strong>when</strong> sales happen: the monthly trend, busy weekdays and hours, how much was cancelled, and how often customers come back.',
        'Merchandise sale and cancellation lines from <code>fact_sales</code>, grouped through <code>dim_date</code>. Postage/fees and flagged duplicate lines are excluded.')}
      <div id="sales-filters"></div>
      <div class="an-chips" id="sales-active" style="margin-bottom: 14px;"></div>
      <div id="sales-body"></div>`;
    body = $('#sales-body');
    bar = new FilterBar($('#sales-filters'), { onChange: load, fields: ['date', 'countries', 'products'], chipsEl: $('#sales-active') });
    bar.renderChips(false);
    load();
  }

  async function load() {
    const seq = ++reqSeq;
    body.classList.add('an-loading');
    if (!body.innerHTML) body.innerHTML = '<div class="an-state">Loading…</div>';
    try {
      const d = await MA.loadDashboardData(bar.get());
      if (seq === reqSeq) render(d);
    } catch (e) { if (seq === reqSeq) body.innerHTML = errorBox(e); }
    finally { if (seq === reqSeq) body.classList.remove('an-loading'); }
  }

  function render(d) {
    const k = d.kpis;
    if (!k.orders) { body.innerHTML = '<div class="an-card"><div class="an-state">No eligible sales match these filters.</div></div>'; return; }
    const m = d.monthly;
    const best = m.reduce((a, b) => ((b.net || 0) > (a.net || 0) ? b : a));
    const busiestDay = d.weekday.reduce((a, b) => (b.orders > a.orders ? b : a));
    const busiestHour = d.hourly.reduce((a, b) => (b.orders > a.orders ? b : a));
    const partial = d.insights.find((i) => i.id === 'partial_months');
    body.innerHTML = `
      <div class="an-stats" style="margin-bottom: 18px;">
        <div class="an-stat"><div class="l">Net sales</div><div class="v">${fmt.money(k.net_sales)}</div><div class="s">${fmt.money(k.gross_sales)} gross</div></div>
        <div class="an-stat"><div class="l">Cancelled value</div><div class="v">${fmt.money(k.cancelled_value)}</div><div class="s">${fmt.pct(k.gross_sales ? k.cancelled_value / k.gross_sales : null)} of gross · ${fmt.int(k.cancellation_invoices)} invoices</div></div>
        <div class="an-stat"><div class="l">Average order value</div><div class="v">${fmt.money2(k.avg_order_value)}</div><div class="s">Gross sales ÷ invoices</div></div>
        <div class="an-stat"><div class="l">Repeat customers</div><div class="v">${fmt.pct(k.repeat_customer_rate)}</div><div class="s">Identified customers with 2+ invoices</div></div>
      </div>
      <div class="an-interpret"><strong>Reading the trend:</strong> the best month was ${esc(fmt.month(best.month))} (${fmt.money(best.net)} net).
        Most invoices were placed on ${esc(busiestDay.weekday)}s and around ${String(busiestHour.hour).padStart(2, '0')}:00.
        ${partial ? esc(partial.text) : ''}</div>
      ${MA.canvasCard('Monthly sales', 'Net sales per month (£) = gross sales − cancellations. Hover a bar for the breakdown.', { id: 'sales-monthly', height: 'tall' })}
      <div class="an-grid cols-2">
        ${MA.canvasCard('Invoices by weekday', 'Distinct purchase invoices by day of the week.', { id: 'sales-weekday' })}
        ${MA.canvasCard('Invoices by hour of day', 'Hour of the invoice timestamp.', { id: 'sales-hour' })}
      </div>
      <div class="an-grid cols-2">
        ${MA.canvasCard('Cancelled value by month', 'Lines on cancellation (C-prefixed) invoices, £.', { id: 'sales-cancel' })}
        ${MA.canvasCard('Customers by number of invoices', 'How many times identified customers purchased.', { id: 'sales-dist' })}
      </div>
      ${MA.details('Monthly figures table', '<div id="sales-table"></div>', { hint: 'gross, cancelled, net, invoices, units' })}
      ${MA.details('How these numbers are calculated', `<ul class="an-hint" style="font-size: 0.82rem; line-height: 1.7; margin-left: 18px; list-style: disc;">
        <li><strong>Gross sales</strong> = Σ quantity × unit price on merchandise SALE lines (quantity &gt; 0, price &gt; 0).</li>
        <li><strong>Cancelled value</strong> = value of lines on invoices starting with “C”. Cancellations are counted in the month they happen because the source does not link them to the original sale.</li>
        <li><strong>Invoices</strong> = distinct invoice numbers with a SALE line, never invoice lines.</li>
        <li>Postage, fees, manual adjustments, zero-price lines and flagged duplicate lines are excluded.</li></ul>`)}`;

    chart($('#sales-monthly'), {
      type: 'bar',
      data: { labels: m.map((r) => fmt.month(r.month)), datasets: [{ label: 'Net sales', data: m.map((r) => r.net), backgroundColor: BRAND, maxBarThickness: 34 }] },
      options: { plugins: { legend: { display: false }, tooltip: { callbacks: {
        label: (c) => `Net sales ${fmt.money(c.raw)}`,
        afterLabel: (c) => { const r = m[c.dataIndex]; return [`Gross ${fmt.money(r.gross)}`, `Cancelled ${fmt.money(r.cancelled)}`, `${fmt.int(r.orders)} invoices`]; } } } },
        scales: { x: axis.cat({ ticks: { maxRotation: 0, autoSkipPadding: 10 } }), y: axis.money() } },
    });
    simple('#sales-weekday', d.weekday.map((r) => r.weekday.slice(0, 3)), d.weekday.map((r) => r.orders), 'Invoices', fmt.int);
    simple('#sales-hour', d.hourly.map((r) => String(r.hour).padStart(2, '0') + ':00'), d.hourly.map((r) => r.orders), 'Invoices', fmt.int);
    simple('#sales-cancel', m.map((r) => fmt.month(r.month)), m.map((r) => r.cancelled), 'Cancelled', fmt.money, PALETTE[2], true);
    simple('#sales-dist', d.customer_order_distribution.map((r) => r.bucket), d.customer_order_distribution.map((r) => r.customers), 'Customers', fmt.int);

    renderTable($('#sales-table'), { caption: 'Monthly sales figures', columns: [
      { key: 'month', label: 'Month', cls: 'nowrap', format: (v) => esc(fmt.month(v)), sortValue: (r) => r.month },
      { key: 'gross', label: 'Gross £', num: true, format: (v) => fmt.money(v) },
      { key: 'cancelled', label: 'Cancelled £', num: true, format: (v) => fmt.money(v) },
      { key: 'net', label: 'Net £', num: true, format: (v) => fmt.money(v) },
      { key: 'orders', label: 'Invoices', num: true, format: fmt.int },
      { key: 'units', label: 'Units', num: true, format: fmt.int }], rows: m });
  }

  function simple(sel, labels, values, label, f, color = BRAND, money = false) {
    chart($(sel), {
      type: 'bar',
      data: { labels, datasets: [{ label, data: values, backgroundColor: color, maxBarThickness: 28 }] },
      options: { plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => `${label}: ${f(c.raw)}` } } },
        scales: { x: axis.cat({ ticks: { maxRotation: 0, autoSkipPadding: 8 } }), y: money ? axis.money() : axis.count() } },
    });
  }

  MA.register('sales', { init });
})();
