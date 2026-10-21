/* MIGRIGA ANALYTICS - Project Guide (route #lab): how the parts fit together, viva walkthrough,
   the ten DWM concepts, a live Apriori walkthrough, KPI definitions and the concept-to-code map */
(() => {
  const { api, esc, fmt, renderTable, errorBox, $ } = MA;

  const CONCEPTS = [
    { n: '01', t: 'Data warehousing', go: 'etl',
      p: 'A warehouse is a separate, subject-oriented, integrated, time-variant and non-volatile store built for analysis. Migriga keeps it in its own SQLite file (data/warehouse/migriga_warehouse.db), apart from the operational store database (migriga.db), so analytical queries never touch live orders.',
      impl: ['etl/schema.sql', 'etl/config.py → warehouse_path()', 'analytics/warehouse.py → connect() (read-only)'] },
    { n: '02', t: 'ETL & data quality', go: 'etl',
      p: 'Extract reads the CSV as text and validates columns. Transform parses dates and numbers, rejects unusable rows with a reason, classifies cancellations and adjustments, flags duplicates and builds the dimensions. Load upserts the dimensions and refreshes the facts in one transaction, then verifies counts and keys.',
      impl: ['etl/extract.py → extract()', 'etl/transform.py → transform(), classify_lines()', 'etl/load.py → load(), verify()', 'POST /api/analytics/etl/run', 'tables etl_run_log, etl_rejected_rows, stg_raw_sales'] },
    { n: '03', t: 'Facts, dimensions & star schema', go: 'etl',
      p: 'fact_sales holds one row per accepted invoice line (the grain), with measures quantity, unit_price and line_amount, and foreign keys to dim_date, dim_product, dim_customer and dim_country. Surrogate keys stay stable across reloads; customer_key 0 is an explicit anonymous member.',
      impl: ['etl/schema.sql', 'etl/load.py (upsert on natural keys)', 'docs/data_dictionary.md'] },
    { n: '04', t: 'OLAP roll-up & drill-down', go: 'olap', preset: { rows: 'year' },
      p: 'Navigating the time hierarchy year › quarter › month › day changes the GROUP BY level. Roll-up aggregates to a coarser level. Drill-down fixes a member (e.g. 2010) and breaks it into finer members.',
      impl: ['analytics/olap.py → TIME_HIERARCHY, drill_down_level(), roll_up_level()', 'POST /api/analytics/olap', 'js/analytics/olap.js → rollUp(), drillDown()'] },
    { n: '05', t: 'Slice, dice & pivot', go: 'olap', preset: { rows: 'quarter', columns: 'country', measure: 'gross_sales', filters: { countries: ['France', 'Germany', 'EIRE', 'Netherlands'] } },
      p: 'Slice fixes one dimension to a single member (Year = 2010). Dice restricts several dimensions at once (date range AND countries AND products). Pivot cross-tabulates two dimensions for one measure and can swap rows and columns.',
      impl: ['analytics/olap.py → run_query(), _where()', 'analytics/warehouse.py → build_filters()', 'POST /api/analytics/olap/export'] },
    { n: '06', t: 'Association-rule mining (Apriori)', go: 'basket',
      p: 'Apriori finds frequent itemsets level by level. Candidates of size k are joined from frequent (k−1)-itemsets, and any candidate with an infrequent subset is pruned, because every subset of a frequent itemset must also be frequent. Rules A → C are then generated from each frequent itemset.',
      impl: ['analytics/market_basket.py → load_baskets(), apriori(), association_rules()', 'POST /api/analytics/basket/jobs', 'tests/test_market_basket.py'] },
    { n: '07', t: 'Support, confidence & lift', go: 'basket',
      p: 'support(X) = baskets containing X ÷ all baskets. confidence(A→C) = support(A∪C) ÷ support(A). lift(A→C) = confidence ÷ support(C): 1 means independence, above 1 means positive association. None of these measures show causation.',
      impl: ['analytics/market_basket.py → association_rules()', 'Apriori playground below runs the same function'] },
    { n: '08', t: 'RFM analysis', go: 'segments',
      p: 'Recency = days from last purchase to the reference date (day after the last purchase in the data, not today). Frequency = distinct purchase invoices. Monetary = gross purchases minus the customer’s own cancellations. Anonymous lines are never given a customer profile.',
      impl: ['analytics/customer_segmentation.py → compute_rfm(), eligibility()', 'tests/test_segmentation.py'] },
    { n: '09', t: 'K-Means clustering', go: 'segments',
      p: 'RFM values are log1p-transformed (they are heavily skewed) and standardised, then K-Means with a fixed seed and 10 initialisations groups customers. Each cluster is described only by its measured medians compared with the overall median.',
      impl: ['analytics/customer_segmentation.py → prepare_features(), fit_kmeans(), describe_clusters()', 'POST /api/analytics/segmentation/jobs', 'data/processed/segmentation_model.json'] },
    { n: '10', t: 'Evaluation & limitations', go: 'segments',
      p: 'Silhouette (−1…1) and inertia across k = 2…10 help choose k. Neither proves the clusters are “real”. The data is one UK retailer’s history, not Migriga’s, with no costs (so no profit), and cancellations cannot be reliably matched to their original invoices.',
      impl: ['analytics/customer_segmentation.py → silhouette()', 'docs/dwm_concepts.md → Limitations'] },
  ];

  const KPIS = [
    ['Gross sales', 'Σ quantity × unit_price on merchandise SALE lines (qty > 0, price > 0, not C/A invoice), duplicates excluded.'],
    ['Cancelled value', 'Σ −line_amount on merchandise lines of C-prefixed invoices. These are not linked to the original sale.'],
    ['Net sales', 'Gross sales − cancelled value (equivalently Σ line_amount over eligible SALE + CANCELLATION lines).'],
    ['Orders', 'COUNT(DISTINCT invoice_no) over SALE lines. Never invoice lines.'],
    ['Invoice lines', 'Count of SALE fact rows.'],
    ['Units sold', 'Σ quantity on SALE lines.'],
    ['Average order value', 'Gross sales ÷ orders.'],
    ['Identified customers', 'Distinct customer_key ≠ 0 with at least one SALE line in the period.'],
    ['Repeat-customer rate', 'Identified customers with ≥ 2 distinct SALE invoices ÷ identified customers in the period.'],
    ['Anonymous share', 'Gross sales on lines without a CustomerID ÷ gross sales. These lines count in sales but not in customer metrics.'],
    ['Excluded from sales', 'STOCK_ADJUSTMENT (negative qty on normal invoices), ZERO_PRICE, ADJUSTMENT (bad debt, A invoices), postage/fees/manual codes, flagged duplicates.'],
  ];

  const MAP = [
    ['Data warehouse', 'etl/schema.sql', '—', 'GET /api/analytics/overview', 'all dim_*, fact_sales', 'Data Warehouse & ETL'],
    ['Extract', 'etl/extract.py', 'extract(), file_sha256()', 'POST /api/analytics/etl/run', 'stg_raw_sales', 'Data Warehouse & ETL'],
    ['Transform / cleaning', 'etl/transform.py', 'transform(), classify_lines(), normalize_customer_id()', 'POST /api/analytics/etl/run', 'etl_rejected_rows', 'Data Warehouse & ETL'],
    ['Load / rerun safety', 'etl/load.py, etl/lock.py', 'load(), verify(), ETLLock', 'POST /api/analytics/etl/run', 'fact_sales (UNIQUE line_fingerprint)', 'Data Warehouse & ETL'],
    ['ETL monitoring', 'backend/analytics_api.py', 'etl_status()', 'GET /api/analytics/etl/status', 'etl_run_log', 'Data Warehouse & ETL'],
    ['Star schema', 'etl/schema.sql', '—', '—', 'fact_sales, dim_date, dim_product, dim_customer, dim_country', 'Data Warehouse & ETL'],
    ['Roll-up / drill-down', 'analytics/olap.py', 'roll_up_level(), drill_down_level(), run_query()', 'POST /api/analytics/olap', 'fact_sales ⋈ dim_date', 'OLAP Explorer'],
    ['Slice / dice', 'analytics/olap.py, analytics/warehouse.py', '_where(), build_filters()', 'POST /api/analytics/olap', 'fact_sales ⋈ all dims', 'OLAP Explorer'],
    ['Pivot', 'analytics/olap.py', 'run_query() (pivot mode)', 'POST /api/analytics/olap', 'fact_sales ⋈ all dims', 'OLAP Explorer'],
    ['OLAP export', 'analytics/olap.py', 'to_csv_rows()', 'POST /api/analytics/olap/export', '—', 'OLAP Explorer'],
    ['Basket construction', 'analytics/market_basket.py', 'load_baskets()', 'POST /api/analytics/basket/jobs', 'fact_sales ⋈ dim_product', 'Market Basket'],
    ['Apriori', 'analytics/market_basket.py', 'apriori()', 'POST /api/analytics/basket/jobs, /lab/apriori-demo', '—', 'Market Basket, Project Guide'],
    ['Support / confidence / lift', 'analytics/market_basket.py', 'association_rules()', 'GET /api/analytics/jobs/{id}', '—', 'Market Basket'],
    ['RFM features', 'analytics/customer_segmentation.py', 'compute_rfm(), eligibility()', 'POST /api/analytics/segmentation/jobs', 'fact_sales ⋈ dim_customer', 'Customer Segments'],
    ['K-Means', 'analytics/customer_segmentation.py', 'prepare_features(), fit_kmeans(), describe_clusters()', 'POST /api/analytics/segmentation/jobs', 'data/processed/segmentation_model.json', 'Customer Segments'],
    ['Cluster evaluation', 'analytics/customer_segmentation.py', 'silhouette(), elbow loop in segment()', 'GET /api/analytics/jobs/{id}', '—', 'Customer Segments'],
    ['Dashboard KPIs & insights', 'analytics/dashboard.py', 'get_dashboard(), build_insights()', 'GET /api/analytics/dashboard', 'fact_sales ⋈ all dims', 'Dashboard, Sales, Products & Countries'],
    ['Background jobs & caching', 'analytics/jobs.py, analytics/warehouse.py', 'JobManager.submit(), ResultCache', 'GET /api/analytics/jobs/{id}', 'warehouse_meta.data_version', 'Market Basket, Segmentation'],
  ];

  const SAMPLE = `bread, milk
bread, diapers, beer, eggs
milk, diapers, beer, cola
bread, milk, diapers, beer
bread, milk, diapers, cola`;

  const routeName = { etl: 'Data Warehouse & ETL', olap: 'OLAP Explorer', basket: 'Market Basket', segments: 'Customer Segments' };

  const FLOW = [
    ['etl', '01 · SOURCE', 'Raw CSV', '525k historical invoice lines (Online Retail II), kept unchanged.'],
    ['etl', '02 · ETL', 'Clean & load', 'Extract, validate, classify sales vs cancellations, flag duplicates, load in one transaction.'],
    ['etl', '03 · WAREHOUSE', 'Star schema', 'fact_sales + date, product, customer and country dimensions in a separate SQLite file.'],
    ['olap', '04 · ANALYSE', 'Dashboard & OLAP', 'KPIs and charts, plus roll-up, drill-down, slice, dice and pivot on the cube.'],
    ['basket', '05 · MINE', 'Apriori & K-Means', 'Products bought together, and customer segments from RFM features.'],
  ];

  const VIVA = [
    ['Start on the <a href="#dashboard">Dashboard</a>: explain that the data is a UK retailer’s history (not Migriga sales) and read the four KPIs.', 'dashboard'],
    ['Open <a href="#etl">Data Warehouse &amp; ETL</a>: show rows processed and rejected, then the cleaning rules (cancellations, duplicates, missing customer IDs).', 'etl'],
    ['Describe the star schema: one fact table (grain = one invoice line) and four dimensions. Open “Warehouse tables” for row counts.', 'etl'],
    ['In the <a href="#olap">OLAP Explorer</a>: group by Month, click <em>Summarise</em> twice to reach Year (roll-up), click 2010 (drill-down), add a country (dice) and a pivot.', 'olap'],
    ['In <a href="#basket">Market Basket</a>: run Apriori with the defaults, click the top rule and read its explanation (support, confidence, lift; association ≠ causation).', 'basket'],
    ['In <a href="#segments">Customer Segments</a>: explain R, F and M, show the segment cards and the silhouette score under “Model details”.', 'segments'],
    ['Finish with the concept-to-code map below to show where each concept is implemented.', 'lab'],
  ];

  function init() {
    const root = $('#lab-root');
    root.innerHTML = `
      ${MA.pageHead('Help', 'Project Guide', '')}
      ${MA.intro('Explains how the parts of Migriga Analytics fit together and links every Data Warehousing &amp; Data Mining concept to the page where it runs and the code that implements it.',
        'Everything here uses the same warehouse built from <code>data/raw/online_retail_09_10.csv</code> (Chen, D. 2012, <em>Online Retail II</em>, UCI Machine Learning Repository, <a href="https://doi.org/10.24432/C5CG6D" target="_blank" rel="noopener">doi:10.24432/C5CG6D</a>, CC BY 4.0).')}

      ${MA.card('How it fits together', `<div class="an-flow">${FLOW.map(([go, n, t, d]) => `<a href="#${go}"><span class="num">${n}</span><strong>${t}</strong><span>${d}</span></a>`).join('')}</div>`,
        { sub: 'Data flows left to right. Click a step to open the page that shows it.' })}

      <div class="an-grid cols-2">
        ${MA.card('Explaining the project in a viva', `<ol class="an-viva">${VIVA.map(([t]) => `<li><span>${t}</span></li>`).join('')}</ol>`, { sub: 'A seven-step walkthrough of about ten minutes.' })}
        ${MA.card('Key definitions', `<div id="lab-kpis"></div>`, { sub: 'The same rules are used on every page.' })}
      </div>

      <h2 class="an-card-title" style="margin: 6px 0 12px;">The ten DWM concepts</h2>
      <div class="an-concepts" style="margin-bottom: 18px;">${CONCEPTS.map((c, i) => `
        <article class="an-concept">
          <span class="num">CONCEPT ${c.n}</span>
          <h3>${esc(c.t)}</h3>
          <p>${esc(c.p)}</p>
          <div class="impl"><strong>Implemented in:</strong><br>${c.impl.map((x) => `<code>${esc(x)}</code>`).join('<br>')}</div>
          <button class="an-btn sm" type="button" data-concept="${i}">See it in ${esc(routeName[c.go])} →</button>
        </article>`).join('')}</div>

      ${MA.details('Try it: Apriori step by step', `
        <p class="an-hint" style="margin-bottom: 10px;">Runs the real <code>apriori()</code> and <code>association_rules()</code> functions on baskets you type.</p>
        <div class="an-grid cols-1-2" style="margin: 0;">
          <div>
            <div class="an-field"><label for="lab-baskets">Baskets: one per line, items separated by commas</label>
              <textarea class="an-input" id="lab-baskets" spellcheck="false">${SAMPLE}</textarea></div>
            <div class="an-controls" style="margin-top: 12px;">
              <div class="an-field"><label for="lab-sup">Min support</label><input class="an-input" type="number" id="lab-sup" value="0.6" min="0.05" max="1" step="0.05"></div>
              <div class="an-field"><label for="lab-conf">Min confidence</label><input class="an-input" type="number" id="lab-conf" value="0.7" min="0" max="1" step="0.05"></div>
              <button class="an-btn primary" type="button" id="lab-run">Run analysis</button>
            </div>
          </div>
          <div id="lab-out"><div class="an-state">Click “Run analysis” to see each Apriori level.</div></div>
        </div>`, { hint: 'interactive demo', open: true })}
      ${MA.details('Concept-to-code map', '<div id="lab-map"></div>', { hint: 'file, function, API endpoint, table and page for each concept' })}
      ${MA.details('Star schema diagram', `<pre class="an-code" style="max-height: none; white-space: pre; overflow-x: auto;">                    ┌──────────────┐
                    │   dim_date   │ date_key (yyyymmdd), full_date, day, month,
                    │              │ month_name, quarter, year, year_month, weekday…
                    └──────┬───────┘
┌──────────────┐    ┌──────┴────────────────────────┐    ┌────────────────┐
│ dim_product  │    │          fact_sales           │    │ dim_customer   │
│ product_key  ├────┤ sales_key (PK)                ├────┤ customer_key   │
│ stock_code   │    │ date_key, product_key,        │    │ customer_id    │
│ description  │    │ customer_key, country_key (FK)│    │ (0 = anonymous)│
│ item_class   │    │ invoice_no (degenerate dim)   │    └────────────────┘
└──────────────┘    │ source_row_number, fingerprint│
                    │ quantity, unit_price,         │    ┌───────────────┐
                    │ line_amount, line_type,       ├────┤  dim_country  │
                    │ is_product, is_duplicate …    │    │ country_key   │
                    └───────────────────────────────┘    │ country_name  │
                     grain: one accepted invoice line    └───────────────┘</pre>`, { hint: 'fact and dimension tables' })}`;

    root.querySelectorAll('[data-concept]').forEach((b) => b.addEventListener('click', () => {
      const c = CONCEPTS[Number(b.dataset.concept)];
      if (c.go === 'olap' && c.preset && MA.openOlap) MA.openOlap(c.preset); else MA.go(c.go);
    }));
    $('#lab-run').addEventListener('click', runDemo);
    renderTable($('#lab-kpis'), { caption: 'KPI definitions', columns: [{ key: 0, label: 'Metric' }, { key: 1, label: 'Definition', sortable: false }], rows: KPIS });
    renderTable($('#lab-map'), { caption: 'Concept to code map', columns: [
      { key: 0, label: 'Concept' }, { key: 1, label: 'Source file', render: (r) => `<code>${esc(r[1])}</code>` },
      { key: 2, label: 'Function', render: (r) => `<code>${esc(r[2])}</code>` }, { key: 3, label: 'API endpoint', render: (r) => `<code>${esc(r[3])}</code>` },
      { key: 4, label: 'Tables / artefacts' }, { key: 5, label: 'Page' }], rows: MAP });
  }

  async function runDemo() {
    const out = $('#lab-out');
    const baskets = $('#lab-baskets').value.split('\n').map((l) => l.split(',').map((s) => s.trim()).filter(Boolean)).filter((b) => b.length);
    out.classList.add('an-loading');
    try {
      const r = await api('/api/analytics/lab/apriori-demo', { method: 'POST', body: { baskets, min_support: Number($('#lab-sup').value), min_confidence: Number($('#lab-conf').value) } });
      const pill = (items, cls, count) => `<span class="an-pill ${cls}">{${esc(items.join(', '))}}${count !== undefined ? ' · ' + count : ''}</span>`;
      out.innerHTML = `<p class="an-hint" style="margin-bottom: 10px;">${r.n_baskets} baskets · an itemset is frequent if it appears in ≥ ${r.min_support_count} baskets.</p>
        <div class="an-trace">${r.trace.map((lv) => `
          <div class="an-trace-level"><h4>Level ${lv.k}: ${lv.k === 1 ? 'count single items' : `join L${lv.k - 1} → ${lv.candidates} candidate(s)`}</h4>
            <div class="an-pill-list">${lv.frequent.map(([items, c]) => pill(items, 'ok', c)).join('')}
              ${(lv.pruned_itemsets || []).map((items) => pill(items, 'pruned')).join('')}
              ${(lv.infrequent || []).map((items) => pill(Array.isArray(items) ? items : [items], 'no')).join('')}</div>
            <div class="an-hint" style="margin-top: 6px;">${lv.frequent.length} frequent${lv.pruned ? ` · ${lv.pruned} pruned (infrequent subset, never counted)` : ''}${lv.infrequent?.length ? ` · ${lv.infrequent.length} below min support` : ''}</div>
          </div>`).join('')}</div>
        <h4 class="an-label" style="margin: 16px 0 8px;">Rules (confidence ≥ ${esc($('#lab-conf').value)})</h4>
        ${r.rules.length ? `<table class="an-table"><thead><tr><th>Rule</th><th class="num">Support</th><th class="num">Confidence</th><th class="num">Lift</th></tr></thead><tbody>
          ${r.rules.map((x) => `<tr><td>{${esc(x.antecedent.join(', '))}} <span class="an-arrow">→</span> {${esc(x.consequent.join(', '))}}</td>
            <td class="num">${fmt.num(x.support, 2)}</td><td class="num">${fmt.num(x.confidence, 2)}</td><td class="num">${fmt.num(x.lift, 2)}</td></tr>`).join('')}</tbody></table>`
          : '<div class="an-state">No rule meets the confidence threshold.</div>'}
        <p class="an-hint" style="margin-top: 8px;">Legend: <span class="an-pill ok">frequent</span> <span class="an-pill pruned">pruned by Apriori property</span> <span class="an-pill no">counted, infrequent</span></p>`;
    } catch (e) { out.innerHTML = errorBox(e); }
    finally { out.classList.remove('an-loading'); }
  }

  MA.register('lab', { init });
})();
