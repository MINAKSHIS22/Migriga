/* MIGRIGA ANALYTICS - Market Basket Analysis (Apriori) via background job */
(() => {
  const { runJob, download, esc, fmt, chart, axis, renderTable, errorBox, BRAND, PALETTE, $ } = MA;
  let root, current, running = false;

  function init() {
    root = $('#basket-root');
    const countries = MA.state.overview?.filter_options?.countries || [];
    root.innerHTML = `
      ${MA.pageHead('Data mining', 'Market Basket Analysis', '')}
      ${MA.intro('The <strong>Apriori</strong> algorithm finds products that frequently appear together on the same purchase invoice, and turns them into rules such as “customers who buy A also tend to buy B”.',
        'Each eligible purchase invoice is one basket and each product (stock code) is one item, built from merchandise SALE lines in <code>fact_sales</code>. Cancellations, returns, zero-price lines, postage/fees and duplicate lines are excluded, and a product counts once per basket.')}
      <div class="an-card">
        <div class="an-step">Controls</div>
        <form id="mb-form" class="an-controls">
          ${param('min_support', 'Minimum support', 0.003, 0.1, 0.001, 0.01, 'Share of baskets that must contain the products (0.01 = 1%).')}
          ${param('min_confidence', 'Minimum confidence', 0.05, 1, 0.05, 0.3, 'How often B is bought when A is bought.')}
          ${param('min_lift', 'Minimum lift', 0, 20, 0.5, 1, 'Above 1 = bought together more than by chance.')}
          <div class="an-btn-row" style="padding-bottom: 20px;"><button class="an-btn primary" type="submit" id="mb-run">Run analysis</button></div>
        </form>
        ${MA.details('More settings', `<div class="an-controls">
            <div class="an-field"><label for="mb-max_len">Largest product group</label>
              <select class="an-select" id="mb-max_len"><option value="2">2 products</option><option value="3" selected>3 products</option><option value="4">4 products</option></select></div>
            <div class="an-field grow"><label for="mb-country">Only baskets from</label>
              <select class="an-select" id="mb-country"><option value="">All countries</option>${countries.map((c) => `<option>${esc(c)}</option>`).join('')}</select></div></div>
            <p class="an-hint" style="margin-top: 8px;">Every pattern must appear in at least 5 baskets; very low support on a small country is rejected with an explanation.</p>`, { hint: 'itemset size, country' })}
        <div class="an-progress" aria-hidden="true"><span id="mb-bar"></span></div>
        <div class="an-status-line" id="mb-status" aria-live="polite">Using the default settings…</div>
      </div>
      <div id="mb-results"></div>`;
    root.querySelector('.an-card .an-details').style.margin = '6px 0 12px';
    $('#mb-form').addEventListener('submit', (e) => { e.preventDefault(); run(); });
    root.querySelectorAll('input[type="range"]').forEach((r) => {
      const n = $(`#mb-${r.dataset.p}`);
      r.addEventListener('input', () => { n.value = r.value; });
      n.addEventListener('input', () => { r.value = n.value; });
    });
    run();
  }

  function param(id, label, min, max, step, val, hint) {
    return `<div class="an-field grow"><label for="mb-${id}">${label}</label>
      <div style="display: flex; gap: 10px; align-items: center;">
        <input class="an-input" type="range" data-p="${id}" min="${min}" max="${max}" step="${step}" value="${val}" aria-label="${label} slider" style="flex: 1;">
        <input class="an-input" type="number" id="mb-${id}" min="${min}" max="${id === 'min_support' ? 1 : id === 'min_lift' ? 1000 : max}" step="${step}" value="${val}" style="width: 90px;" required></div>
      <span class="an-hint">${hint}</span></div>`;
  }

  async function run() {
    if (running) return;
    running = true;
    const body = {
      min_support: Number($('#mb-min_support').value), min_confidence: Number($('#mb-min_confidence').value),
      min_lift: Number($('#mb-min_lift').value), max_len: Number($('#mb-max_len').value),
      country: $('#mb-country').value || null,
    };
    const status = $('#mb-status'), barEl = $('#mb-bar');
    $('#mb-run').disabled = true;
    $('#mb-results').classList.add('an-loading');
    try {
      const job = await runJob('/api/analytics/basket/jobs', body, (j, cached) => {
        barEl.style.width = j.progress + '%';
        status.textContent = cached && j.status === 'done' ? 'Showing the saved result for these settings.' : `Working: ${j.message}`;
      });
      current = job;
      const secs = job.finished_at && job.started_at ? (job.finished_at - job.started_at).toFixed(1) : null;
      status.textContent = `Done — ${fmt.int(job.result.n_rules)} rules from ${fmt.int(job.result.n_baskets)} baskets` + (secs ? ` (${secs}s).` : '.');
      render(job.result);
    } catch (e) {
      status.textContent = 'The analysis could not run with these settings.'; barEl.style.width = '0';
      $('#mb-results').innerHTML = errorBox(e);
    } finally {
      running = false; $('#mb-run').disabled = false; $('#mb-results').classList.remove('an-loading');
    }
  }

  const names = (codes, d) => codes.map((c) => d[c] || c).join(' + ');
  function item(code, desc) { return `<span class="an-item"><code>${esc(code)}</code>${esc(desc[code] || '')}</span>`; }

  function explain(r, n, d) {
    const anteBaskets = Math.round(r.antecedent_support * n);
    return `<strong>How to read this rule:</strong> ${fmt.int(anteBaskets)} baskets contain <strong>${esc(names(r.antecedent, d))}</strong>.
      In ${fmt.pct(r.confidence)} of them (confidence) the basket also contains <strong>${esc(names(r.consequent, d))}</strong>.
      Both appear together in ${fmt.int(r.support_count)} baskets, ${fmt.pct(r.support, 2)} of all baskets (support).
      A lift of ${fmt.num(r.lift, 1)} means this pair occurs ${fmt.num(r.lift, 1)}× more often than if the products were bought independently.
      This shows the products are bought together; it does not prove that one purchase causes the other.`;
  }

  function render(r) {
    const out = $('#mb-results');
    if (!r.n_baskets) { out.innerHTML = `<div class="an-card"><div class="an-state">${esc(r.message)}</div></div>`; return; }
    const d = r.descriptions;
    const sizes = Object.entries(r.itemsets_by_size).map(([k, v]) => `${fmt.int(v)} of size ${k}`).join(', ');
    out.innerHTML = `
      <div class="an-stats" style="margin-bottom: 18px;">
        <div class="an-stat"><div class="l">Baskets analysed</div><div class="v">${fmt.int(r.n_baskets)}</div><div class="s">eligible purchase invoices</div></div>
        <div class="an-stat"><div class="l">Different products</div><div class="v">${fmt.int(r.n_items)}</div><div class="s">median ${r.median_basket_size} per basket</div></div>
        <div class="an-stat"><div class="l">Frequent product groups</div><div class="v">${fmt.int(r.n_frequent_itemsets)}</div><div class="s">in ≥ ${fmt.int(r.min_support_count)} baskets</div></div>
        <div class="an-stat"><div class="l">Association rules</div><div class="v">${fmt.int(r.n_rules)}</div><div class="s">meeting your thresholds</div></div>
      </div>
      <div class="an-card">
        <div class="an-card-header"><h2 class="an-card-title">Top association rules</h2>
          <div class="an-btn-row"><input class="an-input" id="mb-filter" placeholder="Search a product…" style="width: 220px;" aria-label="Filter rules by product">
          <button class="an-btn sm" id="mb-exp-rules" type="button">⤓ Export CSV</button></div></div>
        ${r.rules.length ? `<div class="an-interpret" id="mb-explain">${explain(r.rules[0], r.n_baskets, d)}</div>
        <p class="an-hint" style="margin: -6px 0 10px;">Click any rule to explain it. Sorted by lift; click a column heading to re-sort.</p>` : '<div class="an-banner info">No rules meet these thresholds. Try a lower minimum confidence or lift.</div>'}
        <div id="mb-rules"></div>
      </div>
      ${MA.details('Charts', `<div class="an-grid cols-2" style="margin: 0;">
          ${MA.canvasCard('Rules: support vs confidence', 'Each dot is a rule (top 400 by lift); bigger = higher lift.', { id: 'mb-scatter', height: 'tall' })}
          ${MA.canvasCard('Most frequent product pairs and triples', 'Share of baskets containing the whole group.', { id: 'mb-top', height: 'tall' })}</div>`,
        { hint: 'support vs confidence, most frequent groups', id: 'mb-charts' })}
      ${MA.details('Frequent product groups (itemsets)', `<div class="an-btn-row" style="margin-bottom: 10px;"><select class="an-select" id="mb-size" style="width: 160px;" aria-label="Filter by group size"><option value="">All sizes</option>
          ${Object.keys(r.itemsets_by_size).map((k) => `<option value="${k}">Size ${k}</option>`).join('')}</select>
          <button class="an-btn sm" id="mb-exp-items" type="button">⤓ Export CSV</button></div><div id="mb-itemsets"></div>`, { hint: sizes })}
      ${MA.details('Technical details', `<ul class="an-hint" style="font-size: 0.82rem; line-height: 1.7; margin-left: 18px; list-style: disc;">
          <li><strong>Support(X)</strong> = baskets containing every item of X ÷ all baskets (${fmt.int(r.n_baskets)}).</li>
          <li><strong>Confidence(A → B)</strong> = support(A ∪ B) ÷ support(A).</li>
          <li><strong>Lift(A → B)</strong> = confidence ÷ support(B). 1 means independent.</li>
          <li><strong>Apriori</strong>: count single items, keep the frequent ones, join frequent groups of size k−1 into candidates of size k, discard any candidate with an infrequent subset (the Apriori property), count the rest, and repeat up to size ${r.params.max_len}.</li>
          <li>Settings used: support ≥ ${r.params.min_support} (${fmt.int(r.min_support_count)} baskets), confidence ≥ ${r.params.min_confidence}, lift ≥ ${r.params.min_lift}, max size ${r.params.max_len}, country: ${esc(r.params.country || 'all')}.</li>
          <li>${fmt.int(r.n_basket_lines)} distinct invoice–product pairs; average ${r.avg_basket_size} products per basket.${r.results_truncated ? ' Tables show the top 2,000 rules and itemsets.' : ''}</li>
          <li>Code: <code>analytics/market_basket.py</code> → <code>load_baskets()</code>, <code>apriori()</code>, <code>association_rules()</code>.</li></ul>`)}`;

    if (r.rules.length) {
      const ruleTable = renderTable($('#mb-rules'), {
        caption: 'Association rules', pageSize: 10, sort: { key: 'lift', dir: 'desc' },
        columns: [
          { key: 'antecedent', label: 'If the basket contains', sortValue: (x) => x.antecedent.join(), render: (x) => x.antecedent.map((c) => item(c, d)).join('') },
          { key: 'consequent', label: '…it often also contains', sortValue: (x) => x.consequent.join(), render: (x) => x.consequent.map((c) => item(c, d)).join('') },
          { key: 'support', label: 'Support', num: true, format: (v) => fmt.pct(v, 2) },
          { key: 'confidence', label: 'Confidence', num: true, format: (v) => fmt.pct(v, 1) },
          { key: 'lift', label: 'Lift', num: true, format: (v) => fmt.num(v, 2) },
          { key: 'support_count', label: 'Baskets', num: true, format: fmt.int },
        ],
        rows: r.rules,
        onRowClick: (rule) => { $('#mb-explain').innerHTML = explain(rule, r.n_baskets, d); },
      });
      const match = (codes, q) => codes.some((c) => c.toUpperCase().includes(q) || (d[c] || '').toUpperCase().includes(q));
      $('#mb-filter').addEventListener('input', MA.debounce((e) => {
        const q = e.target.value.trim().toUpperCase();
        ruleTable.update(q ? r.rules.filter((x) => match(x.antecedent, q) || match(x.consequent, q)) : r.rules);
      }, 200));
    }
    const itemTable = renderTable($('#mb-itemsets'), {
      caption: 'Frequent itemsets', pageSize: 20, sort: { key: 'support', dir: 'desc' },
      columns: [
        { key: 'items', label: 'Products', sortValue: (x) => x.items.join(), render: (x) => x.items.map((c) => item(c, d)).join('') },
        { key: 'size', label: 'Size', num: true },
        { key: 'support', label: 'Support', num: true, format: (v) => fmt.pct(v, 2) },
        { key: 'support_count', label: 'Baskets', num: true, format: fmt.int },
      ],
      rows: r.itemsets,
    });
    $('#mb-size').addEventListener('change', (e) => itemTable.update(e.target.value ? r.itemsets.filter((x) => String(x.size) === e.target.value) : r.itemsets));
    $('#mb-exp-rules').addEventListener('click', () => download(`/api/analytics/basket/${current.id}/export?kind=rules`).catch((e) => alert(e.message)));
    $('#mb-exp-items').addEventListener('click', () => download(`/api/analytics/basket/${current.id}/export?kind=itemsets`).catch((e) => alert(e.message)));

    // Charts render when their panel is first opened (canvases need a visible size)
    const drawCharts = () => {
      const pts = r.rules.slice(0, 400);
      const maxLift = Math.max(...pts.map((p) => p.lift), 1);
      chart($('#mb-scatter'), {
        type: 'scatter',
        data: { datasets: [{ label: 'Rules', data: pts.map((p) => ({ x: p.support, y: p.confidence, r: 3 + 9 * Math.sqrt(p.lift / maxLift) })),
          backgroundColor: 'rgba(176, 125, 98, 0.55)', borderColor: '#FFFFFF', borderWidth: 1, pointRadius: (c) => c.raw?.r || 4, pointHoverRadius: (c) => (c.raw?.r || 4) + 2 }] },
        options: { interaction: { mode: 'nearest', intersect: true },
          plugins: { legend: { display: false }, tooltip: { callbacks: {
            title: (c) => `${names(pts[c[0].dataIndex].antecedent, d)} → ${names(pts[c[0].dataIndex].consequent, d)}`,
            label: (c) => { const p = pts[c.dataIndex]; return `support ${fmt.pct(p.support, 2)} · confidence ${fmt.pct(p.confidence)} · lift ${fmt.num(p.lift)}`; } } } },
          scales: { x: { ...axis.count(), title: { display: true, text: 'Support' }, ticks: { callback: (v) => fmt.pct(v, 1) } },
                    y: { ...axis.count(), title: { display: true, text: 'Confidence' }, ticks: { callback: (v) => fmt.pct(v, 0) } } } },
      });
      const top = r.itemsets.filter((x) => x.size >= 2).slice(0, 12);
      chart($('#mb-top'), {
        type: 'bar',
        data: { labels: top.map((x) => x.items.join(' + ')), datasets: [{ label: 'Support', data: top.map((x) => x.support), backgroundColor: PALETTE[1], maxBarThickness: 18 }] },
        options: { indexAxis: 'y', interaction: { mode: 'nearest', intersect: false, axis: 'y' },
          plugins: { legend: { display: false }, tooltip: { callbacks: { title: (c) => names(top[c[0].dataIndex].items, d), label: (c) => `support ${fmt.pct(c.raw, 2)} · ${fmt.int(top[c.dataIndex].support_count)} baskets` } } },
          scales: { x: { ...axis.count(), ticks: { callback: (v) => fmt.pct(v, 1) } }, y: axis.cat({ ticks: { color: MA.INK.text, font: { size: 10.5 } } }) } },
      });
    };
    const panel = $('#mb-charts');
    panel.addEventListener('toggle', () => { if (panel.open) drawCharts(); });
  }

  MA.register('basket', { init });
})();
