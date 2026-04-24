'use strict';

const API = '/api';
let token = localStorage.getItem('avd_token') || null;
let currentUser = null;
let faultState   = {};
let refreshTimer = null;

// ═══════════════════════════════════════════════════════════
//  API HELPER
// ═══════════════════════════════════════════════════════════
async function api(path, opts = {}) {
  const headers = { 'Authorization': `Bearer ${token}` };
  if (opts.json !== undefined) {
    headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(opts.json);
    delete opts.json;
  }
  const res = await fetch(`${API}${path}`, { ...opts, headers });
  if (res.status === 401) { doLogout(); throw new Error('Session expired'); }
  const txt = await res.text();
  if (!txt || txt.trim() === '') return null;
  try   { return JSON.parse(txt); }
  catch { throw new Error(`Non-JSON (HTTP ${res.status}) from ${path}: ${txt.slice(0,120)}`); }
}

// Wrapper that always returns an array (for list endpoints)
async function apiList(path) {
  const data = await api(path);
  if (Array.isArray(data)) return data;
  console.warn('Expected array from', path, 'got:', data);
  return [];
}

// ═══════════════════════════════════════════════════════════
//  LOGIN
// ═══════════════════════════════════════════════════════════
async function doLogin() {
  const username = document.getElementById('inp-user').value.trim();
  const password = document.getElementById('inp-pass').value;
  if (!username || !password) return;
  setLoginBusy(true);
  hideLoginError();
  try {
    const body = new URLSearchParams({ username, password });
    const res  = await fetch(`${API}/auth/token`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body:    body.toString(),
    });
    const txt = await res.text();
    let data;
    try { data = JSON.parse(txt); }
    catch { throw new Error(`Server error (HTTP ${res.status}). Run: docker compose logs app`); }
    if (!res.ok) throw new Error(data.detail || `Login failed (HTTP ${res.status})`);
    token = data.access_token;
    localStorage.setItem('avd_token', token);
    currentUser = { username: data.username, role: data.role };
    enterApp();
  } catch (e) {
    showLoginError(e.message);
  } finally {
    setLoginBusy(false);
  }
}

function setLoginBusy(busy) {
  document.getElementById('btn-login').disabled = busy;
  document.getElementById('btn-text').style.display = busy ? 'none'   : 'inline';
  document.getElementById('btn-spin').style.display = busy ? 'inline' : 'none';
}
function showLoginError(msg) {
  const el = document.getElementById('login-error');
  el.textContent = '✗ ' + msg;
  el.style.display = 'block';
}
function hideLoginError() {
  document.getElementById('login-error').style.display = 'none';
}
document.addEventListener('keydown', e => {
  if (e.key === 'Enter' && document.getElementById('login-page').classList.contains('active')) doLogin();
});

function doLogout() {
  token = null;
  localStorage.removeItem('avd_token');
  currentUser = null;
  clearInterval(refreshTimer);
  document.getElementById('app-page').classList.remove('active');
  document.getElementById('login-page').classList.add('active');
  initRadar();
}

// ═══════════════════════════════════════════════════════════
//  STARTUP
// ═══════════════════════════════════════════════════════════
window.addEventListener('load', async () => {
  initRadar();

  // Try auto-login from stored token
  if (token) {
    try {
      const me = await api('/auth/me');
      if (me && me.username) {
        currentUser = { username: me.username, role: me.role };
        enterApp();
        return;
      }
    } catch {
      token = null;
      localStorage.removeItem('avd_token');
    }
  }

  // Show login page stats (public-facing numbers, fetched without auth)
  loadLoginStats();
});

// Login page stats — fetched without auth by hitting summary with no token
async function loadLoginStats() {
  try {
    // Public endpoint — no auth required
    const res = await fetch(`${API}/dashboard/public-stats`);
    if (!res.ok) return;
    const d = await res.json();
    const set = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = (val != null) ? val : '—';
    };
    set('ls-flights',  d?.flights?.total   );
    set('ls-aircraft', d?.aircraft?.total  );
    set('ls-airports', d?.airports?.total  );
    set('ls-delayed',  d?.flights?.delayed );
  } catch(e) { console.warn('Login stats:', e); }
}

// ═══════════════════════════════════════════════════════════
//  APP SHELL
// ═══════════════════════════════════════════════════════════
function enterApp() {
  document.getElementById('login-page').classList.remove('active');
  document.getElementById('app-page').classList.add('active');
  document.getElementById('sb-user').textContent = currentUser.username;
  document.getElementById('sb-role').textContent = currentUser.role.toUpperCase();
  showView('dashboard');
  startClock();
  refreshTimer = setInterval(refreshView, 30000);
}

function startClock() {
  const el = document.getElementById('clock');
  function tick() { el.textContent = new Date().toUTCString().replace(' GMT', ' UTC'); }
  tick();
  setInterval(tick, 1000);
}

// ═══════════════════════════════════════════════════════════
//  VIEW ROUTING
// ═══════════════════════════════════════════════════════════
const TITLES = {
  dashboard: 'Dashboard', flights: 'Flights', aircraft: 'Fleet',
  airports:  'Airports',  chaos:   'Chaos Control',
};

function showView(name) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById(`view-${name}`)?.classList.add('active');
  document.querySelector(`[data-view="${name}"]`)?.classList.add('active');
  document.getElementById('view-title').textContent = TITLES[name] || name;
  ({ dashboard: loadDashboard, flights: loadFlights, aircraft: loadAircraft,
     airports: loadAirports, chaos: loadChaos })[name]?.();
}

function refreshView() {
  const active = document.querySelector('.view.active');
  if (!active) return;
  const name = active.id.replace('view-', '');
  if (name !== 'chaos') showView(name);
  updateFaultInd();
}

// ═══════════════════════════════════════════════════════════
//  DASHBOARD
// ═══════════════════════════════════════════════════════════
async function loadDashboard() {
  try {
    const d = await api('/dashboard/summary');
    if (!d) return;
    setText('k-total',  d.flights?.total);
    setText('k-active', d.flights?.active);
    setText('k-delayed',d.flights?.delayed);
    setText('k-canc',   d.flights?.cancelled);
    setText('k-fleet',  d.aircraft?.total);
    setText('k-ontime', d.flights?.on_time_pct != null ? d.flights.on_time_pct + '%' : '—');
    setText('h-api',    d.system_health?.api_latency_ms    != null ? d.system_health.api_latency_ms    + ' ms' : '—');
    setText('h-db',     d.system_health?.db_query_time_ms  != null ? d.system_health.db_query_time_ms  + ' ms' : '—');
    setText('h-cache',  d.system_health?.cache_hit_pct     != null ? d.system_health.cache_hit_pct     + '%'   : '—');
    renderBusiest(d.busiest_origins || []);
  } catch(e) { console.error('dashboard error:', e); }

  renderMap();
}

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = (val != null) ? val : '—';
}

function renderBusiest(data) {
  const el = document.getElementById('busiest-panel');
  if (!el || !data.length) return;
  const max = Math.max(...data.map(r => r.departures), 1);
  el.innerHTML = data.map(r => `
    <div class="b-row">
      <span class="b-iata">${r.iata}</span>
      <div class="b-track"><div class="b-fill" style="width:${Math.round(r.departures/max*100)}%"></div></div>
      <span class="b-cnt">${r.departures}</span>
    </div>`).join('');
}

// ═══════════════════════════════════════════════════════════
//  FLIGHT MAP
// ═══════════════════════════════════════════════════════════
async function renderMap() {
  const svg = document.getElementById('flight-map');
  if (!svg) return;

  const W = 900, H = 440;

  // Equirectangular projection — matches world.svg viewBox exactly
  function proj(lat, lon) {
    return [
      ((lon + 180) / 360) * W,
      ((90  - lat) / 180) * H,
    ];
  }

  // Start with world map background + ocean fill
  let content = `
    <rect width="${W}" height="${H}" fill="#061525"/>
    <image href="/static/img/world.svg" x="0" y="0"
           width="${W}" height="${H}"
           preserveAspectRatio="none"
           style="pointer-events:none"/>
  `;

  // Airport dots
  try {
    const airports = await apiList('/airports/');
    content += airports.map(a => {
      const [x, y] = proj(a.lat, a.lon);
      return `
        <circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3"
          fill="rgba(0,198,255,0.18)" stroke="rgba(0,198,255,0.8)" stroke-width="1">
          <title>${a.iata_code} – ${a.name}</title>
        </circle>
        <circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="1.2"
          fill="rgba(0,198,255,1)"/>`;
    }).join('');
  } catch(e) { console.warn('Map airports error:', e); }

  // Flight position markers
  try {
    const flights = await apiList('/flights/?limit=200');
    const enRoute = flights.filter(f =>
      f.status === 'en_route' && f.lat != null && f.lon != null
    );
    content += enRoute.map(f => {
      const [x, y] = proj(Number(f.lat), Number(f.lon));
      return `
        <g transform="translate(${x.toFixed(1)},${y.toFixed(1)})">
          <circle r="8" fill="rgba(0,230,118,0.1)" stroke="rgba(0,230,118,0.5)" stroke-width="1"/>
          <text x="0" y="1" text-anchor="middle" dominant-baseline="central"
                font-size="9" fill="rgba(0,230,118,0.95)">✈</text>
          <text x="10" y="-7" font-size="7" font-family="monospace"
                fill="rgba(0,230,118,0.75)">${f.flight_number}</text>
          <title>${f.flight_number} ${f.origin_iata}→${f.destination_iata}</title>
        </g>`;
    }).join('');
  } catch(e) { console.warn('Map flights error:', e); }

  svg.innerHTML = content;
}

// ═══════════════════════════════════════════════════════════
//  FLIGHTS TABLE
// ═══════════════════════════════════════════════════════════
async function loadFlights() {
  const statusFilter = document.getElementById('filter-status')?.value || '';
  const qs = statusFilter ? `status=${statusFilter}&limit=100` : 'limit=100';
  const tbody = document.getElementById('flights-body');
  if (tbody) tbody.innerHTML = '<tr><td colspan="8" class="loading">Loading…</td></tr>';

  try {
    const flights = await apiList(`/flights/?${qs}`);
    if (!flights.length) {
      if (tbody) tbody.innerHTML = '<tr><td colspan="8" class="loading">No flights found.</td></tr>';
      return;
    }
    if (tbody) tbody.innerHTML = flights.map(f => `
      <tr>
        <td style="color:var(--accent);font-weight:600">${f.flight_number}</td>
        <td>${f.origin_iata}</td>
        <td>${f.destination_iata}</td>
        <td><span class="sb s-${f.status}">${f.status.replace(/_/g,' ').toUpperCase()}</span></td>
        <td>${f.departure_time ? f.departure_time.slice(0,16).replace('T',' ') : '—'}</td>
        <td>${f.gate || '—'}</td>
        <td>${f.altitude_ft ? Number(f.altitude_ft).toLocaleString() + ' ft' : '—'}</td>
        <td style="color:${f.delay_minutes > 0 ? 'var(--orange)' : 'var(--text-d)'}">
          ${f.delay_minutes > 0 ? '+' + f.delay_minutes + 'm' : '—'}
        </td>
      </tr>`).join('');
  } catch(e) {
    console.error('loadFlights error:', e);
    if (tbody) tbody.innerHTML = `<tr><td colspan="8" class="loading" style="color:var(--red)">Error: ${e.message}</td></tr>`;
  }
}

// ═══════════════════════════════════════════════════════════
//  AIRCRAFT TABLE
// ═══════════════════════════════════════════════════════════
async function loadAircraft() {
  const statusFilter = document.getElementById('filter-ac')?.value || '';
  const qs = statusFilter ? `?status=${statusFilter}` : '';
  const tbody = document.getElementById('aircraft-body');
  if (tbody) tbody.innerHTML = '<tr><td colspan="9" class="loading">Loading…</td></tr>';

  try {
    const aircraft = await apiList(`/aircraft/${qs}`);
    if (!aircraft.length) {
      if (tbody) tbody.innerHTML = '<tr><td colspan="9" class="loading">No aircraft found.</td></tr>';
      return;
    }
    if (tbody) tbody.innerHTML = aircraft.map(a => `
      <tr>
        <td style="color:var(--accent);font-weight:600">${a.tail_number}</td>
        <td>${a.model}</td>
        <td>${a.manufacturer}</td>
        <td>${a.capacity}</td>
        <td>${Number(a.range_nm).toLocaleString()}</td>
        <td>${a.engine_type || '—'}</td>
        <td>${a.year_manufactured || '—'}</td>
        <td><span class="sb s-${a.status}">${a.status.toUpperCase()}</span></td>
        <td>${Number(a.flight_hours).toLocaleString()}</td>
      </tr>`).join('');
  } catch(e) {
    console.error('loadAircraft error:', e);
    if (tbody) tbody.innerHTML = `<tr><td colspan="9" class="loading" style="color:var(--red)">Error: ${e.message}</td></tr>`;
  }
}

// ═══════════════════════════════════════════════════════════
//  AIRPORTS TABLE
// ═══════════════════════════════════════════════════════════
async function loadAirports() {
  const tbody = document.getElementById('airports-body');
  if (tbody) tbody.innerHTML = '<tr><td colspan="9" class="loading">Loading…</td></tr>';

  try {
    const airports = await apiList('/airports/');
    if (!airports.length) {
      if (tbody) tbody.innerHTML = '<tr><td colspan="9" class="loading">No airports found.</td></tr>';
      return;
    }
    if (tbody) tbody.innerHTML = airports.map(a => `
      <tr>
        <td style="color:var(--accent);font-weight:600">${a.iata_code}</td>
        <td style="color:var(--text-s)">${a.icao_code || '—'}</td>
        <td>${a.name}</td>
        <td>${a.city}</td>
        <td>${a.country}</td>
        <td style="color:var(--text-s)">${Number(a.lat).toFixed(3)}</td>
        <td style="color:var(--text-s)">${Number(a.lon).toFixed(3)}</td>
        <td>${a.elevation_ft != null ? Number(a.elevation_ft).toLocaleString() + ' ft' : '—'}</td>
        <td>${a.runways}</td>
      </tr>`).join('');
  } catch(e) {
    console.error('loadAirports error:', e);
    if (tbody) tbody.innerHTML = `<tr><td colspan="9" class="loading" style="color:var(--red)">Error: ${e.message}</td></tr>`;
  }
}

// ═══════════════════════════════════════════════════════════
//  CHAOS CONTROL
// ═══════════════════════════════════════════════════════════
async function loadChaos() {
  try {
    const [st, cat] = await Promise.all([api('/chaos/status'), api('/chaos/catalog')]);
    faultState = st?.faults || {};
    buildChaosCards(cat?.faults || {});
    updateFaultInd();
  } catch(e) { console.error('loadChaos error:', e); }
}

function buildChaosCards(catalog) {
  const buckets = { application: [], container: [] };
  for (const [key, info] of Object.entries(catalog)) {
    const on   = !!faultState[key];
    const crit = info.severity === 'critical';
    buckets[info.tier]?.push(`
      <div class="fault-card ${on ? (crit ? 'f-critical' : 'f-active') : ''}" id="card-${key}">
        <div class="f-top">
          <div>
            <div class="f-name">${info.label}</div>
            <span class="sev sev-${info.severity}">${info.severity.toUpperCase()}</span>
          </div>
          <label class="toggle">
            <input type="checkbox" ${on ? 'checked' : ''}
                   onchange="toggleFault('${key}', this.checked)"/>
            <span class="tslider"></span>
          </label>
        </div>
        <div class="f-desc">${info.description}</div>
        <div class="f-signal">📡 ${info.datadog_signal}</div>
        <div class="f-status ${on ? 'on' : ''}" id="flbl-${key}">${on ? '⚡ ACTIVE' : 'INACTIVE'}</div>
      </div>`);
  }
  document.getElementById('faults-application').innerHTML = buckets.application.join('');
  document.getElementById('faults-container').innerHTML   = buckets.container.join('');
}

async function toggleFault(name, enabled) {
  if (currentUser?.role !== 'admin') {
    chaosAlert('Admin role required to inject faults', 'error');
    // Revert the checkbox
    const cb = document.querySelector(`#card-${name} input[type=checkbox]`);
    if (cb) cb.checked = !enabled;
    return;
  }
  try {
    await api(`/chaos/${name}/toggle`, { method: 'POST', json: { enabled } });
    faultState[name] = enabled;
    const card = document.getElementById(`card-${name}`);
    if (card) {
      const crit = !!card.querySelector('.sev-critical');
      card.classList.toggle('f-active',   enabled && !crit);
      card.classList.toggle('f-critical', enabled &&  crit);
    }
    const lbl = document.getElementById(`flbl-${name}`);
    if (lbl) { lbl.textContent = enabled ? '⚡ ACTIVE' : 'INACTIVE'; lbl.classList.toggle('on', enabled); }
    updateFaultInd();
    chaosAlert(`${enabled ? '⚡ ACTIVATED' : '✓ DEACTIVATED'}: ${name.replace(/_/g,' ').toUpperCase()}`, enabled ? 'warn' : 'ok');
  } catch(e) {
    chaosAlert('Error: ' + e.message, 'error');
    const cb = document.querySelector(`#card-${name} input[type=checkbox]`);
    if (cb) cb.checked = !enabled;
  }
}

async function resetAllFaults() {
  if (!confirm('Reset ALL active faults?')) return;
  try {
    await api('/chaos/reset-all', { method: 'POST' });
    chaosAlert('✓ All faults cleared', 'ok');
    await loadChaos();
  } catch(e) { chaosAlert('Error: ' + e.message, 'error'); }
}

function chaosAlert(msg, type) {
  const el = document.getElementById('chaos-alert');
  const styles = {
    error: { color:'var(--red)',    border:'rgba(255,61,90,.3)',   bg:'rgba(255,61,90,.08)'   },
    ok:    { color:'var(--green)',  border:'rgba(0,230,118,.3)',   bg:'rgba(0,230,118,.08)'   },
    warn:  { color:'var(--orange)', border:'rgba(255,112,67,.3)',  bg:'rgba(255,112,67,.08)'  },
  };
  const s = styles[type] || styles.warn;
  Object.assign(el.style, { display:'block', color:s.color, borderColor:s.border, background:s.bg, border:'1px solid' });
  el.textContent = msg;
  setTimeout(() => el.style.display = 'none', 4000);
}

function updateFaultInd() {
  const el = document.getElementById('fault-ind');
  if (!el) return;
  const n = Object.values(faultState).filter(Boolean).length;
  if (n > 0) {
    el.textContent = `⚡ ${n} FAULT${n > 1 ? 'S' : ''} ACTIVE`;
    el.className = 'fault-ind fault-on';
  } else {
    el.textContent = 'ALL SYSTEMS NOMINAL';
    el.className = 'fault-ind fault-off';
  }
}

// ═══════════════════════════════════════════════════════════
//  RADAR ANIMATION (login page background)
// ═══════════════════════════════════════════════════════════
function initRadar() {
  const canvas = document.getElementById('radar-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let angle = 0;
  const blips = Array.from({ length: 8 }, () => ({
    r:  Math.random() * 0.38 + 0.08,
    a:  Math.random() * Math.PI * 2,
    sz: Math.random() * 2   + 1,
  }));

  function draw() {
    canvas.width  = canvas.offsetWidth;
    canvas.height = canvas.offsetHeight;
    const cx = canvas.width  / 2;
    const cy = canvas.height / 2;
    const R  = Math.min(cx, cy) * 0.82;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Rings
    ctx.strokeStyle = 'rgba(0,198,255,0.15)';
    ctx.lineWidth   = 1;
    [0.25, 0.5, 0.75, 1].forEach(f => {
      ctx.beginPath(); ctx.arc(cx, cy, R * f, 0, Math.PI * 2); ctx.stroke();
    });
    ctx.beginPath(); ctx.moveTo(cx - R, cy); ctx.lineTo(cx + R, cy); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(cx, cy - R); ctx.lineTo(cx, cy + R); ctx.stroke();

    // Sweep
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(angle);
    const g = ctx.createLinearGradient(0, 0, R, 0);
    g.addColorStop(0, 'rgba(0,198,255,0.45)');
    g.addColorStop(1, 'rgba(0,198,255,0)');
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.arc(0, 0, R, -0.28, 0.28);
    ctx.closePath();
    ctx.fill();
    ctx.restore();

    // Blips
    blips.forEach(b => {
      const bx   = cx + Math.cos(b.a) * R * b.r * 2.5;
      const by   = cy + Math.sin(b.a) * R * b.r * 2.5;
      const diff = ((angle - b.a) % (Math.PI * 2) + Math.PI * 2) % (Math.PI * 2);
      if (diff < 0.45) {
        ctx.beginPath();
        ctx.arc(bx, by, b.sz, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(0,230,118,${(1 - diff / 0.45).toFixed(2)})`;
        ctx.fill();
      }
    });

    angle = (angle + 0.012) % (Math.PI * 2);
    requestAnimationFrame(draw);
  }
  draw();
}
