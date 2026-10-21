/* ==========================================================================
   MIGRIGA ANALYTICS - core: auth gate, API client, sidebar router, formatting,
   light chart theme, page-structure helpers, sortable tables, filter bar and
   background-job polling.
   ========================================================================== */
const MA = (() => {
  const TOKEN_KEY = 'migriga_admin_token';
  let token = localStorage.getItem(TOKEN_KEY);
  const modules = {};
  const initialized = new Set();
  const state = { overview: null };

  // Brand rose gold for single-series charts; validated categorical palette (white surface,
  // CVD-safe adjacent pairs) for multi-series charts - assigned in fixed order, never cycled.
  const BRAND = '#B07D62';
  const PALETTE = ['#A8742A', '#2F6FB0', '#B25A3E', '#7E57B5', '#258C5A', '#D0609A',
                   '#C49A55', '#6E9BD0', '#CF8A73', '#A58BCF'];
  const INK = { text: '#2E2A28', muted: '#6B6460', faint: '#857D78', grid: 'rgba(46, 42, 40, 0.08)', axis: '#E2D8D0', surface: '#FFFFFF' };

  // ------------------------------------------------------------- utilities
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const $ = (sel, root = document) => root.querySelector(sel);
  const fmt = {
    money: (v, d = 0) => (v === null || v === undefined || isNaN(v)) ? '—' : '£' + Number(v).toLocaleString('en-GB', { minimumFractionDigits: d, maximumFractionDigits: d }),
    money2: (v) => fmt.money(v, 2),
    int: (v) => (v === null || v === undefined || isNaN(v)) ? '—' : Math.round(Number(v)).toLocaleString('en-GB'),
    num: (v, d = 2) => (v === null || v === undefined || isNaN(v)) ? '—' : Number(v).toLocaleString('en-GB', { minimumFractionDigits: d, maximumFractionDigits: d }),
    pct: (v, d = 1) => (v === null || v === undefined || isNaN(v)) ? '—' : (Number(v) * 100).toFixed(d) + '%',
    compact: (v) => (v === null || v === undefined || isNaN(v)) ? '—' : Intl.NumberFormat('en-GB', { notation: 'compact', maximumFractionDigits: 1 }).format(v),
    byKind: (kind, v) => kind === 'money' ? fmt.money2(v) : kind === 'int' ? fmt.int(v) : fmt.num(v),
    month: (ym) => { const [y, m] = String(ym).split('-'); return new Date(Number(y), Number(m) - 1, 1).toLocaleString('en-GB', { month: 'short', year: 'numeric' }); },
  };

  function debounce(fn, ms = 350) {
    let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
  }

  // ------------------------------------------------------------- API
  class ApiError extends Error {
    constructor(message, status, code) { super(message); this.status = status; this.code = code; }
  }

  async function api(path, { method = 'GET', body, raw = false } = {}) {
    const headers = { 'Authorization': `Bearer ${token || ''}` };
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    let res;
    try {
      res = await fetch(path, { method, headers, body: body !== undefined ? JSON.stringify(body) : undefined });
    } catch (e) {
      throw new ApiError('Cannot reach the Migriga server. Is it running?', 0, 'network');
    }
    if (res.status === 401 || res.status === 403) {
      showLogin('Your session has expired or lacks admin rights. Please sign in again.');
      throw new ApiError('Admin sign-in required.', res.status, 'auth');
    }
    if (!res.ok) {
      let detail = `Request failed (${res.status}).`, code;
      try { const j = await res.json(); detail = typeof j.detail === 'string' ? j.detail : (j.detail?.[0]?.msg || detail); code = j.code; } catch (_) {}
      if (code === 'warehouse_unavailable') showWarehouseMissing(detail);
      throw new ApiError(detail, res.status, code);
    }
    return raw ? res : res.json();
  }

  async function download(path, { method = 'GET', body, filename = 'export.csv' } = {}) {
    const res = await api(path, { method, body, raw: true });
    const blob = await res.blob();
    const cd = res.headers.get('Content-Disposition') || '';
    const m = cd.match(/filename="([^"]+)"/);
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = m ? m[1] : filename;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }

  /** Submits a background job and polls until it finishes. onProgress(job, cached) gets every update. */
  async function runJob(path, body, onProgress = () => {}) {
    const start = await api(path, { method: 'POST', body });
    let job = start.job;
    onProgress(job, start.cached);
    while (job.status === 'queued' || job.status === 'running') {
      await new Promise((r) => setTimeout(r, 600));
      job = (await api(`/api/analytics/jobs/${job.id}`)).job;
      onProgress(job, start.cached);
    }
    if (job.status === 'failed') throw new ApiError(job.error || 'The analysis failed.', 500, 'job_failed');
    return job;
  }

  function showWarehouseMissing(msg) {
    const el = $('#an-warehouse-missing');
    el.innerHTML = `<strong>The data warehouse is not ready.</strong> ${esc(msg)} Open <a href="#etl">Data Warehouse &amp; ETL</a> and click <em>Run ETL</em>, or run <code>python3 -m etl.run_etl</code>.`;
    el.hidden = false;
  }

  // ------------------------------------------------------------- auth
  function showLogin(message) {
    $('#an-shell').hidden = true;
    $('#an-login').style.display = 'flex';
    $('#an-login-error').textContent = message || '';
  }

  async function checkAuth() {
    if (!token) return showLogin('');
    try {
      const res = await fetch('/api/auth/me', { headers: { 'Authorization': `Bearer ${token}` } });
      if (!res.ok) throw new Error();
      const { user } = await res.json();
      if (user.role !== 'admin') return showLogin('This account is not an administrator.');
      $('#an-user-name').textContent = user.full_name;
      $('#an-login').style.display = 'none';
      $('#an-shell').hidden = false;
      await loadOverview();
      route();
    } catch (_) {
      localStorage.removeItem(TOKEN_KEY); token = null; showLogin('');
    }
  }

  function setupAuthUI() {
    $('#an-login-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      $('#an-login-error').textContent = '';
      try {
        const res = await fetch('/api/auth/login', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: $('#an-login-email').value, password: $('#an-login-pass').value }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Sign-in failed.');
        if (data.user.role !== 'admin') throw new Error('This account does not have admin privileges.');
        token = data.token;
        localStorage.setItem(TOKEN_KEY, token);
        localStorage.setItem('migriga_user', JSON.stringify(data.user));
        checkAuth();
      } catch (err) { $('#an-login-error').textContent = err.message; }
    });
    $('#an-logout').addEventListener('click', async () => {
      try { await fetch('/api/auth/logout', { method: 'POST', headers: { 'Authorization': `Bearer ${token}` } }); } catch (_) {}
      localStorage.removeItem(TOKEN_KEY); token = null; showLogin('Signed out.');
    });
  }

  async function loadOverview() {
    try {
      state.overview = await api('/api/analytics/overview');
      if (!state.overview.initialized) showWarehouseMissing(state.overview.message || '');
      else $('#an-warehouse-missing').hidden = true;
    } catch (e) { /* surfaced by api() */ }
    return state.overview;
  }

  // ------------------------------------------------------------- router + mobile menu
  function register(name, mod) { modules[name] = mod; }

  function setMenu(open) {
    $('#an-shell').classList.toggle('menu-open', open);
    $('#an-scrim').hidden = !open;
    $('#an-menu-btn').setAttribute('aria-expanded', open ? 'true' : 'false');
  }

  function route() {
    if ($('#an-shell').hidden) return;
    const name = (location.hash.replace('#', '').split('?')[0]) || 'dashboard';
    const target = modules[name] ? name : 'dashboard';
    document.querySelectorAll('.an-section').forEach((s) => { s.hidden = s.dataset.section !== target; });
    document.querySelectorAll('.an-nav a[data-route]').forEach((a) => {
      const on = a.dataset.route === target;
      a.classList.toggle('active', on);
      if (on) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
    });
    setMenu(false);
    const mod = modules[target];
    if (!initialized.has(target)) { initialized.add(target); mod.init?.(); }
    mod.show?.();
    resizeCharts(document.querySelector(`.an-section[data-section="${target}"]`));
  }

  /** Charts drawn while hidden (other page, closed panel, different viewport) keep a stale size; refit them. */
  function resizeCharts(scope) {
    if (typeof Chart === 'undefined' || !scope) return;
    requestAnimationFrame(() => scope.querySelectorAll('canvas').forEach((c) => Chart.getChart(c)?.resize()));
  }

  function go(name) {
    if (location.hash === '#' + name) route(); else location.hash = name;
    window.scrollTo({ top: 0 });
  }

  // ------------------------------------------------------------- charts (light theme)
  const charts = new WeakMap();
  function chart(canvas, config) {
    if (!canvas) return null;
    if (typeof Chart === 'undefined') {
      canvas.parentElement.innerHTML = '<div class="an-state">Chart library unavailable; see the table view.</div>';
      return null;
    }
    const old = charts.get(canvas);
    if (old) old.destroy();
    const c = new Chart(canvas, config);
    charts.set(canvas, c);
    return c;
  }

  function applyChartTheme() {
    if (typeof Chart === 'undefined') return;
    const d = Chart.defaults;
    d.color = INK.muted;
    d.font.family = "'Plus Jakarta Sans', -apple-system, sans-serif";
    d.font.size = 11.5;
    d.borderColor = INK.grid;
    d.maintainAspectRatio = false;
    d.animation.duration = 250;
    d.layout.padding = { left: 4, right: 8, top: 6 };
    Object.assign(d.plugins.legend.labels, { boxWidth: 10, boxHeight: 10, useBorderRadius: true, borderRadius: 3, color: INK.text });
    Object.assign(d.plugins.tooltip, { backgroundColor: '#FFFFFF', borderColor: '#E2D8D0', borderWidth: 1, titleColor: '#1A1817',
      bodyColor: INK.text, padding: 10, cornerRadius: 8, boxPadding: 4 });
    d.elements.bar.borderRadius = 4;
    d.elements.bar.borderSkipped = 'start';
    d.elements.line.borderWidth = 2;
    d.elements.point.radius = 0;
    d.elements.point.hoverRadius = 5;
    d.interaction = { mode: 'nearest', intersect: false, axis: 'x' };
  }

  const axis = {
    money: (extra = {}) => ({ grid: { color: INK.grid }, border: { display: false }, ticks: { callback: (v) => '£' + fmt.compact(v) }, ...extra }),
    count: (extra = {}) => ({ grid: { color: INK.grid }, border: { display: false }, ticks: { callback: (v) => fmt.compact(v) }, ...extra }),
    cat: (extra = {}) => ({ grid: { display: false }, border: { color: INK.axis }, ...extra }),
  };

  // ------------------------------------------------------------- page-structure helpers
  /** Page header: eyebrow, title, one-line lede. */
  function pageHead(eyebrow, title, lede, right = '') {
    return `<div class="an-page-head an-head-row"><div><div class="an-eyebrow">${eyebrow}</div><h1 class="an-title">${title}</h1>
      ${lede ? `<p class="an-lede">${lede}</p>` : ''}</div>${right}</div>`;
  }
  /** "What does this do?" + "What data is used?" */
  function intro(what, data) {
    return `<div class="an-intro"><div><h3>What does this do?</h3><p>${what}</p></div><div><h3>What data is used?</h3><p>${data}</p></div></div>`;
  }
  /** Collapsible section for advanced settings / technical details. */
  function details(summary, body, { open = false, hint = '', id = '' } = {}) {
    return `<details class="an-details" ${open ? 'open' : ''} ${id ? `id="${id}"` : ''}><summary>${summary}${hint ? ` <small>${hint}</small>` : ''}</summary><div class="body">${body}</div></details>`;
  }
  function kpi(label, value, caption = '') {
    return `<div class="an-kpi"><span class="an-kpi-label">${label}</span><span class="an-kpi-value">${value}</span>${caption ? `<span class="an-kpi-sub">${caption}</span>` : ''}</div>`;
  }
  function card(title, body, { sub = '', right = '', cls = '', id = '' } = {}) {
    return `<div class="an-card ${cls}" ${id ? `id="${id}"` : ''}><div class="an-card-header"><h2 class="an-card-title">${title}</h2>${right}</div>${sub ? `<p class="an-card-sub">${sub}</p>` : ''}${body}</div>`;
  }
  function canvasCard(title, sub, { cls = '', id, height = '', right = '' } = {}) {
    return card(esc(title), `<div class="an-chart ${height}"><canvas id="${id}" role="img" aria-label="${esc(title)}"></canvas></div>`, { sub, cls, right });
  }
  function errorBox(err) { return `<div class="an-banner error" role="alert">${esc(err.message || err)}</div>`; }

  // ------------------------------------------------------------- tables
  /**
   * renderTable(container, { columns: [{key,label,num,format,render,sortable,cls,sortValue}], rows,
   *   sort: {key, dir}, pageSize, caption, onRowClick, footer, note })
   */
  function renderTable(container, opts) {
    const st = { sort: opts.sort || null, page: 0 };
    const pageSize = opts.pageSize || 0;
    function sorted() {
      const rows = [...opts.rows];
      if (!st.sort) return rows;
      const { key, dir } = st.sort;
      const col = opts.columns.find((c) => c.key === key);
      const val = col?.sortValue || ((r) => r[key]);
      return rows.sort((a, b) => {
        const x = val(a), y = val(b);
        if (x === y) return 0;
        if (x === null || x === undefined) return 1;
        if (y === null || y === undefined) return -1;
        return (x > y ? 1 : -1) * (dir === 'asc' ? 1 : -1);
      });
    }
    function draw() {
      const all = sorted();
      const pages = pageSize ? Math.max(1, Math.ceil(all.length / pageSize)) : 1;
      st.page = Math.min(st.page, pages - 1);
      const rows = pageSize ? all.slice(st.page * pageSize, (st.page + 1) * pageSize) : all;
      const head = opts.columns.map((c) => {
        const sortable = c.sortable !== false;
        const aria = st.sort?.key === c.key ? (st.sort.dir === 'asc' ? 'ascending' : 'descending') : 'none';
        return `<th scope="col" class="${c.num ? 'num' : ''} ${sortable ? 'sortable' : ''}" ${sortable ? `data-key="${esc(c.key)}" tabindex="0" aria-sort="${aria}"` : ''}>${esc(c.label)}</th>`;
      }).join('');
      const body = rows.length ? rows.map((r, i) => `<tr data-i="${i}">${opts.columns.map((c) => {
        const v = c.render ? c.render(r) : (c.format ? c.format(r[c.key]) : esc(r[c.key]));
        return `<td class="${c.num ? 'num' : ''} ${c.cls ? (typeof c.cls === 'function' ? c.cls(r) : c.cls) : ''}">${v}</td>`;
      }).join('')}</tr>`).join('') : `<tr><td colspan="${opts.columns.length}" class="an-state">No rows match.</td></tr>`;
      const foot = opts.footer ? `<tfoot><tr>${opts.footer.map((f, i) => `<td class="${opts.columns[i]?.num ? 'num' : ''}">${f}</td>`).join('')}</tr></tfoot>` : '';
      container.innerHTML = `<div class="an-table-wrap"><table class="an-table ${opts.onRowClick ? 'an-clickable' : ''}">${opts.caption ? `<caption class="an-sr-only">${esc(opts.caption)}</caption>` : ''}<thead><tr>${head}</tr></thead><tbody>${body}</tbody>${foot}</table></div>
        <div class="an-table-meta"><span>${fmt.int(all.length)} row${all.length === 1 ? '' : 's'}${opts.note ? ' · ' + opts.note : ''}</span>
        ${pageSize && pages > 1 ? `<span class="an-btn-row"><button class="an-btn sm" data-pg="-1" ${st.page === 0 ? 'disabled' : ''}>← Previous</button>
          <span>Page ${st.page + 1} of ${pages}</span><button class="an-btn sm" data-pg="1" ${st.page >= pages - 1 ? 'disabled' : ''}>Next →</button></span>` : ''}</div>`;
      container.querySelectorAll('th.sortable').forEach((th) => {
        const act = () => {
          const key = th.dataset.key;
          const dir = st.sort?.key === key && st.sort.dir === 'desc' ? 'asc' : 'desc';
          st.sort = { key, dir }; st.page = 0; draw();
        };
        th.addEventListener('click', act);
        th.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); act(); } });
      });
      container.querySelectorAll('[data-pg]').forEach((b) => b.addEventListener('click', () => { st.page += Number(b.dataset.pg); draw(); }));
      if (opts.onRowClick) {
        container.querySelectorAll('tbody tr[data-i]').forEach((tr) => tr.addEventListener('click', (e) => {
          container.querySelectorAll('tbody tr.selected').forEach((x) => x.classList.remove('selected'));
          tr.classList.add('selected');
          opts.onRowClick(rows[Number(tr.dataset.i)], e);
        }));
      }
    }
    draw();
    return { update(rows) { opts.rows = rows; st.page = 0; draw(); } };
  }

  // ------------------------------------------------------------- shared filter bar (dice filters)
  /**
   * new FilterBar(container, { onChange, fields: ['date','countries','products','customers'], chipsEl, inline })
   * Edits are staged; "Apply filters" (or removing a chip / "Clear") sends them to onChange.
   */
  class FilterBar {
    constructor(el, { onChange, fields = ['date', 'countries', 'products'], chipsEl, inline = false, compact = false } = {}) {
      this.el = el; this.onChange = onChange || (() => {}); this.chipsEl = chipsEl;
      this.values = { date_from: '', date_to: '', countries: [], products: [], customers: [] };
      this.productNames = {};
      const opts = state.overview?.filter_options || { countries: [], date_min: '', date_max: '' };
      const uid = Math.random().toString(36).slice(2, 7);
      const has = (f) => fields.includes(f);
      el.classList.add('an-filterbar');
      if (inline) el.classList.add('inline');
      if (compact) el.classList.add('compact');
      el.innerHTML = `
        ${has('date') ? `<div class="an-field"><label for="fd-${uid}">From</label><input class="an-input" type="date" id="fd-${uid}" min="${opts.date_min || ''}" max="${opts.date_max || ''}"></div>
        <div class="an-field"><label for="td-${uid}">To</label><input class="an-input" type="date" id="td-${uid}" min="${opts.date_min || ''}" max="${opts.date_max || ''}"></div>` : ''}
        ${has('countries') ? `<div class="an-field grow"><label for="co-${uid}">Country</label>
          <select class="an-select" id="co-${uid}"><option value="">Add a country…</option>${opts.countries.map((c) => `<option>${esc(c)}</option>`).join('')}</select></div>` : ''}
        ${has('products') ? `<div class="an-field grow an-picker"><label for="pr-${uid}">Product</label>
          <input class="an-input" id="pr-${uid}" placeholder="Search code or name…" autocomplete="off" role="combobox" aria-expanded="false">
          <div class="an-suggest" hidden></div></div>` : ''}
        ${has('customers') ? `<div class="an-field"><label for="cu-${uid}">Customer ID</label><input class="an-input" id="cu-${uid}" placeholder="e.g. 13085, then Enter" inputmode="numeric"></div>` : ''}
        <div class="an-btn-row"><button class="an-btn primary" type="button" data-apply>Apply filters</button>
          <button class="an-btn ghost" type="button" data-reset>Clear</button></div>`;
      this.from = el.querySelector(`#fd-${uid}`); this.to = el.querySelector(`#td-${uid}`);
      this.country = el.querySelector(`#co-${uid}`); this.product = el.querySelector(`#pr-${uid}`);
      this.suggest = el.querySelector('.an-suggest'); this.customer = el.querySelector(`#cu-${uid}`);
      this.from?.addEventListener('change', () => { this.values.date_from = this.from.value; this.renderChips(true); });
      this.to?.addEventListener('change', () => { this.values.date_to = this.to.value; this.renderChips(true); });
      this.country?.addEventListener('change', () => {
        const v = this.country.value;
        if (v && !this.values.countries.includes(v)) { this.values.countries.push(v); this.renderChips(true); }
        this.country.value = '';
      });
      this.customer?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          const v = this.customer.value.trim();
          if (/^\d+$/.test(v) && !this.values.customers.includes(v)) { this.values.customers.push(v); this.renderChips(true); }
          this.customer.value = '';
        }
      });
      if (this.product) {
        const search = debounce(async () => {
          const q = this.product.value.trim();
          if (q.length < 2) { this.suggest.hidden = true; return; }
          try {
            const { products } = await api(`/api/analytics/products/search?q=${encodeURIComponent(q)}&limit=15`);
            this.suggest.innerHTML = products.length ? products.map((p) => `<button type="button" data-code="${esc(p.stock_code)}" data-desc="${esc(p.description)}"><code>${esc(p.stock_code)}</code>${esc(p.description)}</button>`).join('') : '<div class="an-state" style="padding: 10px;">No products found</div>';
            this.suggest.hidden = false; this.product.setAttribute('aria-expanded', 'true');
          } catch (_) { this.suggest.hidden = true; }
        }, 250);
        this.product.addEventListener('input', search);
        this.suggest.addEventListener('click', (e) => {
          const b = e.target.closest('button[data-code]'); if (!b) return;
          const code = b.dataset.code;
          this.productNames[code] = b.dataset.desc;
          if (!this.values.products.includes(code)) { this.values.products.push(code); this.renderChips(true); }
          this.product.value = ''; this.suggest.hidden = true; this.product.setAttribute('aria-expanded', 'false');
        });
        document.addEventListener('click', (e) => { if (!el.contains(e.target)) this.suggest.hidden = true; });
      }
      el.querySelector('[data-apply]').addEventListener('click', () => this.apply());
      el.querySelector('[data-reset]').addEventListener('click', () => this.reset());
      this.applied = JSON.stringify(this.get());
    }
    get() {
      const v = this.values;
      return { date_from: v.date_from || null, date_to: v.date_to || null, countries: [...v.countries], products: [...v.products], customers: [...v.customers] };
    }
    set(values) {
      this.values = { date_from: '', date_to: '', countries: [], products: [], customers: [], ...values };
      if (this.from) this.from.value = this.values.date_from || '';
      if (this.to) this.to.value = this.values.date_to || '';
      this.applied = JSON.stringify(this.get());
      this.renderChips(false);
    }
    apply() { this.applied = JSON.stringify(this.get()); this.renderChips(false); this.onChange(this.get()); }
    reset() { this.set({}); this.onChange(this.get()); }
    count() { const v = this.values; return (v.date_from || v.date_to ? 1 : 0) + v.countries.length + v.products.length + v.customers.length; }
    renderChips(pending) {
      const btn = this.el.querySelector('[data-apply]');
      const dirty = JSON.stringify(this.get()) !== this.applied;
      btn.textContent = dirty ? 'Apply filters •' : 'Apply filters';
      if (!this.chipsEl) return;
      const v = this.values, chips = [];
      if (v.date_from || v.date_to) chips.push(['date', `${v.date_from || 'start'} → ${v.date_to || 'end'}`]);
      v.countries.forEach((c) => chips.push(['country', c]));
      v.products.forEach((p) => chips.push(['product', `${p}${this.productNames[p] ? ' · ' + this.productNames[p] : ''}`, p]));
      v.customers.forEach((c) => chips.push(['customer', c]));
      this.chipsEl.innerHTML = chips.length
        ? `<span class="an-chip-label">${dirty ? 'Filters (not applied yet)' : 'Active filters'}</span>` + chips.map(([k, label, raw]) => `<span class="an-chip"><span>${esc(k)}: ${esc(label)}</span><button type="button" aria-label="Remove ${esc(k)} filter ${esc(label)}" data-k="${k}" data-v="${esc(raw ?? label)}">×</button></span>`).join('')
        : '<span class="an-chip-label">No filters — showing all eligible data</span>';
      this.chipsEl.querySelectorAll('button[data-k]').forEach((b) => b.addEventListener('click', () => {
        const k = b.dataset.k, val = b.dataset.v;
        if (k === 'date') { v.date_from = ''; v.date_to = ''; if (this.from) this.from.value = ''; if (this.to) this.to.value = ''; }
        if (k === 'country') v.countries = v.countries.filter((x) => x !== val);
        if (k === 'product') v.products = v.products.filter((x) => x !== val);
        if (k === 'customer') v.customers = v.customers.filter((x) => x !== val);
        this.apply();
      }));
    }
  }

  function qs(filters) {
    const p = new URLSearchParams();
    if (filters.date_from) p.set('date_from', filters.date_from);
    if (filters.date_to) p.set('date_to', filters.date_to);
    if (filters.countries?.length) p.set('countries', filters.countries.join(','));
    if (filters.products?.length) p.set('products', filters.products.join(','));
    return p.toString();
  }

  /** Shared loader for pages built on GET /api/analytics/dashboard (served from cache when unchanged). */
  async function loadDashboardData(filters) { return api('/api/analytics/dashboard?' + qs(filters || {})); }

  // ------------------------------------------------------------- boot
  document.addEventListener('DOMContentLoaded', () => {
    applyChartTheme();
    setupAuthUI();
    $('#an-menu-btn').addEventListener('click', () => setMenu(!$('#an-shell').classList.contains('menu-open')));
    $('#an-scrim').addEventListener('click', () => setMenu(false));
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') setMenu(false); });
    window.addEventListener('hashchange', route);
    document.addEventListener('toggle', (e) => { if (e.target.open) resizeCharts(e.target); }, true);
    window.addEventListener('resize', debounce(() => resizeCharts(document.querySelector('.an-section:not([hidden])')), 200));
    checkAuth();
  });

  return { api, download, runJob, register, go, route, state, esc, $, fmt, debounce, chart, axis,
           pageHead, intro, details, kpi, card, canvasCard, renderTable, FilterBar, qs, errorBox,
           loadDashboardData, BRAND, PALETTE, INK, loadOverview };
})();
