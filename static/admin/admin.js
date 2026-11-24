const API = location.origin;
const TITLES = {
  dash: ['Dashboard', 'Live ops snapshot'],
  analytics: ['Analytics / Funnel', 'KPIs a CEO watches daily'],
  users: ['Users CRM', '360° customer view'],
  orders: ['Orders', 'Payment ledger'],
  support: ['Support inbox', 'Banned + notes + free churn risks'],
  promos: ['Promo codes', 'Growth offers'],
  pushes: ['Push campaigns', 'Re-engagement'],
  announce: ['Announcements', 'In-app banners'],
  pixel: ['Pixel / CAPI', 'Meta ads measurement'],
  plans: ['Plans', 'Monetization catalog'],
  pandits: ['Pandits', 'Expert inventory'],
  content: ['CMS', 'Suggested questions & copy'],
  flags: ['Feature flags', 'Kill switches'],
  events: ['Event log', 'Pixel + CAPI stream'],
  audit: ['Audit trail', 'Who changed what'],
  app: ['App settings', 'Limits & maintenance'],
};

let token = localStorage.getItem('astro99_admin') || '';
let usersCache = [];
let dashCache = null;
let settingsCache = null;
let flagsCache = {};

async function api(path, opts = {}) {
  const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  if (token) headers['X-Admin-Key'] = token;
  const res = await fetch(API + path, { ...opts, headers });
  const ct = res.headers.get('content-type') || '';
  if (ct.includes('text/csv')) return res.text();
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : data.detail?.message || res.statusText);
  return data;
}

async function doLogin() {
  document.getElementById('loginErr').textContent = '';
  try {
    const password = document.getElementById('password').value;
    const res = await api('/admin/login', { method: 'POST', body: JSON.stringify({ password }) });
    token = res.token;
    localStorage.setItem('astro99_admin', token);
    boot();
  } catch (e) {
    document.getElementById('loginErr').textContent = e.message || 'Login failed';
  }
}

async function logout() {
  try {
    if (token) await api('/admin/logout', { method: 'POST', body: '{}' });
  } catch (_) {}
  token = '';
  localStorage.removeItem('astro99_admin');
  location.reload();
}

function showTab(id) {
  document.querySelectorAll('[id^=tab-]').forEach((el) => el.classList.add('hidden'));
  document.getElementById('tab-' + id).classList.remove('hidden');
  document.querySelectorAll('.side button[data-tab]').forEach((b) => b.classList.toggle('active', b.dataset.tab === id));
  const t = TITLES[id] || [id, ''];
  document.getElementById('pageTitle').textContent = t[0];
  document.getElementById('pageSub').textContent = t[1];
  const loaders = {
    dash: loadDash,
    analytics: loadAnalytics,
    users: loadUsers,
    orders: loadOrders,
    support: loadSupport,
    promos: loadPromos,
    pushes: loadPushes,
    announce: loadAnn,
    pixel: loadSettings,
    plans: loadPlans,
    pandits: loadPandits,
    content: loadSuggested,
    flags: loadFlags,
    events: loadEvents,
    audit: loadAudit,
    app: loadSettings,
  };
  (loaders[id] || (() => {}))();
}

async function boot() {
  document.getElementById('loginView').classList.add('hidden');
  document.getElementById('appView').classList.remove('hidden');
  await refreshAll();
}

async function refreshAll() {
  try {
    await loadDash();
  } catch (e) {
    if (/invalid|401|wrong/i.test(String(e.message))) logout();
  }
}

function money(n) {
  return '₹' + Number(n || 0).toLocaleString('en-IN');
}

async function loadDash() {
  const d = await api('/admin/dashboard');
  dashCache = d;
  const s = d.stats;
  document.getElementById('bUsers').textContent = s.users;
  document.getElementById('statCards').innerHTML = [
    ['Users', s.users, 'total accounts'],
    ['Revenue', money(s.revenue), 'paid volume'],
    ['Paid orders', s.paidOrders, s.conversionPct + '% conv'],
    ['ARPU', money(s.arpu), 'per paid order'],
    ['Active members', s.activeMembers, s.freeUsers + ' free'],
    ['Msgs used', s.messagesUsed, d.kpis.msgPerUser + '/user'],
    ['Autopay rate', (d.kpis.autopayRate || 0) + '%', 'of paid'],
    ['Banned', s.banned, 'risk'],
  ]
    .map(
      ([l, v, dlt]) =>
        `<div class="card"><div class="label">${l}</div><div class="value">${v}</div><div class="delta">${dlt}</div></div>`,
    )
    .join('');

  const maxRev = Math.max(1, ...d.series.map((x) => x.revenue));
  document.getElementById('revChart').innerHTML = d.series
    .map((x) => {
      const h = Math.max(6, Math.round((x.revenue / maxRev) * 100));
      return `<i title="${x.day}: ${money(x.revenue)}"><b style="height:${h}%"></b></i>`;
    })
    .join('');

  const f = d.funnel;
  const maxF = Math.max(1, f.signups);
  const steps = [
    ['Signups', f.signups],
    ['Onboarded', f.onboarded],
    ['Paywall', f.paywallSeen],
    ['Paid', f.paid],
    ['Active', f.activeMembers],
  ];
  document.getElementById('funnel').innerHTML = steps
    .map(([lab, val]) => {
      const h = Math.max(10, Math.round((val / maxF) * 100));
      return `<div class="bar" style="height:${h}%"><span>${lab} ${val}</span></div>`;
    })
    .join('');
  document.getElementById('kpiLine').textContent = `Trial→Paid ${d.kpis.trialToPaid}% · Msg/user ${d.kpis.msgPerUser} · Autopay ${d.kpis.autopayRate}%`;

  document.getElementById('dashOrders').innerHTML = (d.recentOrders || []).length
    ? `<table><tr><th>Order</th><th>Plan</th><th>Amt</th><th>Status</th></tr>${d.recentOrders
        .map(
          (o) =>
            `<tr><td class="mono">${o.orderId}</td><td>${o.planId}</td><td>${money(o.amount)}</td><td><span class="tag ${o.status === 'paid' ? 'ok' : ''}">${o.status}</span></td></tr>`,
        )
        .join('')}</table>`
    : '<p class="muted">No orders</p>';

  document.getElementById('providerPill').textContent =
    'Chat: ' + (d.chatProvider?.active || d.chatProvider?.preferred || d.chatProvider?.provider || '—');
  document.getElementById('dashHealth').innerHTML = `
    <p>Pixel <span class="tag ${d.settings.pixelEnabled ? 'ok' : 'warn'}">${d.settings.pixelEnabled ? 'ON' : 'OFF'}</span>
       CAPI <span class="tag ${d.settings.capiEnabled ? 'ok' : 'warn'}">${d.settings.capiEnabled ? 'ON' : 'OFF'}</span></p>
    <p>Free msg limit: <b>${d.settings.freeMessageLimit}</b></p>
    <p>Promos: ${s.promos} · Pushes: ${s.pushes} · Pandits: ${s.pandits}</p>
    <p class="muted mono">${JSON.stringify(d.chatProvider || {}).slice(0, 120)}</p>`;
}

async function loadAnalytics() {
  if (!dashCache) await loadDash();
  const d = dashCache;
  document.getElementById('kpiCards').innerHTML = [
    ['Conversion %', d.kpis.trialToPaid + '%'],
    ['ARPU', money(d.stats.arpu)],
    ['Autopay %', d.kpis.autopayRate + '%'],
    ['Msg / user', d.kpis.msgPerUser],
    ['Active members', d.stats.activeMembers],
    ['Free users', d.stats.freeUsers],
  ]
    .map(([l, v]) => `<div class="card"><div class="label">${l}</div><div class="value">${v}</div></div>`)
    .join('');
  document.getElementById('seriesTable').innerHTML = `<table><tr><th>Day</th><th>Signups</th><th>Paid</th><th>Revenue</th></tr>${d.series
    .map((x) => `<tr><td>${x.day}</td><td>${x.signups}</td><td>${x.paid}</td><td>${money(x.revenue)}</td></tr>`)
    .join('')}</table>`;
}

async function loadUsers() {
  const res = await api('/admin/users');
  usersCache = res.items || [];
  renderUsers();
}

function renderUsers() {
  const q = (document.getElementById('userSearch').value || '').toLowerCase();
  const rows = usersCache.filter(
    (u) => !q || (u.phone || '').includes(q) || (u.name || '').toLowerCase().includes(q),
  );
  document.getElementById('usersTable').innerHTML = `<table>
    <tr><th>User</th><th>Quota</th><th>Plan</th><th>Chats</th><th>Flags</th><th></th></tr>
    ${
      rows
        .map(
          (u) => `<tr>
      <td><b>${u.name || '—'}</b><div class="mono muted">${u.phone}</div></td>
      <td>${u.quota?.unlimited ? '∞' : `${u.quota?.used || 0}/${u.quota?.limit || 0}`}</td>
      <td>${u.membership?.plan_id || 'free'}</td>
      <td>${u.chatCount || 0}</td>
      <td>${u.banned ? '<span class="tag bad">banned</span>' : ''} ${u.quota?.is_premium ? '<span class="tag ok">premium</span>' : '<span class="tag">free</span>'}</td>
      <td><button class="btn sec" onclick="openUser('${u.id}')">Open</button></td>
    </tr>`,
        )
        .join('') || '<tr><td colspan="6">No users</td></tr>'
    }
  </table>`;
}

async function openUser(id) {
  const res = await api('/admin/users/' + id);
  const u = res.user;
  const panel = document.getElementById('userDetailPanel');
  panel.classList.remove('hidden');
  const chatsHtml =
    Object.entries(res.chats || {})
      .map(
        ([cid, msgs]) => `<div style="margin-bottom:10px"><div class="muted">Thread ${cid}</div>
      <div class="chat-preview">${msgs
        .slice(-20)
        .map((m) => `<div class="bubble ${m.role}">${(m.text || '').replace(/</g, '&lt;')}</div>`)
        .join('')}</div></div>`,
      )
      .join('') || '<p class="muted">No chats</p>';
  const notes = (res.notes || [])
    .map((n) => `<div class="muted">• ${n.text} <span class="mono">(${new Date(n.ts).toLocaleString()})</span></div>`)
    .join('');
  document.getElementById('userDetail').innerHTML = `
  <div class="grid2">
    <div>
      <p><b>${u.name || '—'}</b> · ${u.phone}<br/><span class="mono muted">${u.id}</span></p>
      <p>${res.banned ? `<span class="tag bad">BANNED: ${res.banned.reason}</span>` : '<span class="tag ok">Active</span>'}</p>
      <p class="muted">Onboarding ${u.onboardingComplete ? '✓' : '✗'} · Paywall ${u.paymentGateSeen ? '✓' : '✗'} · Lang ${u.language || 'en'}</p>
      <div class="row">
        <input id="qUsed" type="number" style="width:80px;margin:0" value="${res.quota?.used || 0}"/>
        <input id="qLimit" type="number" style="width:80px;margin:0" value="${res.quota?.limit || 5}"/>
        <label class="switch" style="margin:0"><input type="checkbox" id="qPrem" ${res.quota?.is_premium ? 'checked' : ''}/> Premium</label>
        <label class="switch" style="margin:0"><input type="checkbox" id="qUnlim" ${res.quota?.unlimited ? 'checked' : ''}/> Unlimited</label>
        <button class="btn" onclick="saveQuota('${u.id}')">Update quota</button>
      </div>
      <div class="row" style="margin-top:10px">
        <input id="noteText" placeholder="Add support note" style="flex:1;margin:0"/>
        <button class="btn sec" onclick="addNote('${u.id}')">Note</button>
        <button class="btn danger" onclick="banUser('${u.id}', true)">Ban</button>
        <button class="btn sec" onclick="banUser('${u.id}', false)">Unban</button>
      </div>
      <h4>Notes</h4>${notes || '<p class="muted">None</p>'}
      <h4>Orders</h4>${(res.orders || []).map((o) => `<div class="mono">${o.orderId} · ${money(o.amount)} · ${o.status}</div>`).join('') || '<p class="muted">None</p>'}
    </div>
    <div><h4>Chats</h4>${chatsHtml}</div>
  </div>`;
}

async function saveQuota(id) {
  await api('/admin/users/' + id + '/quota', {
    method: 'PATCH',
    body: JSON.stringify({
      used: Number(document.getElementById('qUsed').value),
      limit: Number(document.getElementById('qLimit').value),
      is_premium: document.getElementById('qPrem').checked,
      unlimited: document.getElementById('qUnlim').checked,
    }),
  });
  openUser(id);
  loadUsers();
}

async function addNote(id) {
  const text = document.getElementById('noteText').value.trim();
  if (!text) return;
  await api('/admin/users/' + id + '/notes', { method: 'POST', body: JSON.stringify({ text }) });
  openUser(id);
}

async function banUser(id, banned) {
  const reason = banned ? prompt('Ban reason', 'Policy violation') || 'Banned' : '';
  await api('/admin/users/' + id + '/ban', { method: 'POST', body: JSON.stringify({ banned, reason }) });
  openUser(id);
  loadUsers();
}

async function loadOrders() {
  const res = await api('/admin/orders');
  document.getElementById('ordersTable').innerHTML = `<table>
    <tr><th>Order</th><th>User</th><th>Plan</th><th>Amount</th><th>UPI</th><th>Status</th><th>Autopay</th></tr>
    ${(res.items || [])
      .map(
        (o) => `<tr>
      <td class="mono">${o.orderId}</td><td class="mono">${(o.userId || '').slice(0, 10)}</td>
      <td>${o.planId}</td><td>${money(o.amount)}</td><td>${o.upiId || '—'}</td>
      <td><span class="tag ${o.status === 'paid' ? 'ok' : ''}">${o.status}</span></td>
      <td>${o.autopay ? 'yes' : 'no'}</td></tr>`,
      )
      .join('')}</table>`;
}

async function loadSupport() {
  if (!usersCache.length) await loadUsers();
  const risky = usersCache.filter((u) => u.banned || (!u.membership?.active && (u.quota?.used || 0) >= (u.quota?.limit || 5)));
  document.getElementById('supportTable').innerHTML = `<table>
    <tr><th>User</th><th>Issue</th><th>Notes</th><th></th></tr>
    ${risky
      .map(
        (u) => `<tr>
      <td>${u.name || u.phone}</td>
      <td>${u.banned ? '<span class="tag bad">banned</span>' : '<span class="tag warn">limit hit / free</span>'}</td>
      <td>${u.notesCount || 0}</td>
      <td><button class="btn sec" onclick="showTab('users');openUser('${u.id}')">Open</button></td>
    </tr>`,
      )
      .join('') || '<tr><td colspan="4">Queue clear 🎉</td></tr>'}</table>`;
}

async function loadPromos() {
  const res = await api('/admin/promos');
  document.getElementById('promosTable').innerHTML = `<table>
    <tr><th>Code</th><th>Type</th><th>Value</th><th>Redeemed</th><th>Active</th><th>Note</th></tr>
    ${(res.items || [])
      .map(
        (p) => `<tr><td class="mono"><b>${p.code}</b></td><td>${p.type}</td><td>${p.value}</td>
      <td>${p.redeemed || 0}/${p.maxRedemptions || '∞'}</td>
      <td>${p.active ? '<span class="tag ok">on</span>' : '<span class="tag">off</span>'}</td>
      <td>${p.note || ''}</td></tr>`,
      )
      .join('')}</table>`;
}

async function savePromo() {
  await api('/admin/promos', {
    method: 'POST',
    body: JSON.stringify({
      code: document.getElementById('promoCode').value.trim().toUpperCase(),
      type: document.getElementById('promoType').value,
      value: Number(document.getElementById('promoValue').value),
      appliesTo: document
        .getElementById('promoPlans')
        .value.split(',')
        .map((x) => x.trim())
        .filter(Boolean),
      note: document.getElementById('promoNote').value,
      active: true,
    }),
  });
  loadPromos();
}

async function loadPushes() {
  const res = await api('/admin/pushes');
  document.getElementById('pushesTable').innerHTML = `<table>
    <tr><th>Title</th><th>Segment</th><th>Delivered</th><th>Opened</th><th>When</th></tr>
    ${(res.items || [])
      .map(
        (p) => `<tr><td><b>${p.title}</b><div class="muted">${p.body}</div></td>
      <td>${p.segment}</td><td>${p.delivered}</td><td>${p.opened}</td>
      <td class="mono">${p.sentAt ? new Date(p.sentAt).toLocaleString() : ''}</td></tr>`,
      )
      .join('')}</table>`;
}

async function sendPush() {
  const res = await api('/admin/pushes', {
    method: 'POST',
    body: JSON.stringify({
      title: document.getElementById('pushTitle').value,
      body: document.getElementById('pushBody').value,
      segment: document.getElementById('pushSeg').value,
    }),
  });
  document.getElementById('pushMsg').textContent = `Sent · delivered ~${res.item.delivered}`;
  loadPushes();
}

async function loadAnn() {
  const res = await api('/admin/announcements');
  document.getElementById('annTable').innerHTML = `<table>
    <tr><th>Title</th><th>Placement</th><th>Active</th></tr>
    ${(res.items || []).map((a) => `<tr><td><b>${a.title}</b><div class="muted">${a.body}</div></td><td>${a.placement}</td><td>${a.active ? 'yes' : 'no'}</td></tr>`).join('')}</table>`;
}

async function saveAnn() {
  await api('/admin/announcements', {
    method: 'POST',
    body: JSON.stringify({
      title: document.getElementById('annTitle').value,
      body: document.getElementById('annBody').value,
      placement: document.getElementById('annPlace').value,
      active: true,
    }),
  });
  loadAnn();
}

const PIXEL_EVENT_KEYS = [
  'PageView',
  'ViewContent',
  'CompleteRegistration',
  'Lead',
  'InitiateCheckout',
  'AddPaymentInfo',
  'Purchase',
  'Subscribe',
  'Contact',
];

async function loadSettings() {
  const res = await api('/admin/settings');
  settingsCache = res.settings;
  const s = settingsCache;
  document.getElementById('pixelEnabled').checked = !!s.pixel.enabled;
  document.getElementById('pixelId').value = s.pixel.pixelId || '';
  document.getElementById('pixelEvents').innerHTML = PIXEL_EVENT_KEYS.map(
    (k) => `<div class="switch"><input type="checkbox" data-pe="${k}" ${s.pixel.events?.[k] ? 'checked' : ''}/> ${k}</div>`,
  ).join('');
  document.getElementById('capiEnabled').checked = !!s.capi.enabled;
  document.getElementById('capiPixelId').value = s.capi.pixelId || '';
  document.getElementById('capiToken').value = '';
  document.getElementById('capiToken').placeholder = s.capi.accessTokenSet
    ? 'Saved: ' + (s.capi.accessTokenMasked || '••••')
    : 'EAAB…';
  document.getElementById('capiTest').value = s.capi.testEventCode || '';
  document.getElementById('capiVersion').value = s.capi.apiVersion || 'v21.0';
  document.getElementById('capiPurchase').checked = s.capi.sendPurchase !== false;
  document.getElementById('capiReg').checked = s.capi.sendRegistration !== false;
  document.getElementById('capiCheckout').checked = s.capi.sendInitiateCheckout !== false;
  document.getElementById('capiLead').checked = s.capi.sendLead !== false;
  document.getElementById('ctEnabled').checked = !!s.clevertap.enabled;
  document.getElementById('ctAccount').value = s.clevertap.accountId || '';
  document.getElementById('ctToken').value = s.clevertap.token || '';
  document.getElementById('ctRegion').value = s.clevertap.region || 'in1';
  document.getElementById('fbEnabled').checked = !!s.firebase.enabled;
  document.getElementById('fbMeasure').value = s.firebase.measurementId || '';
  document.getElementById('cfEnabled').checked = !!s.cashfree.enabled;
  document.getElementById('cfAppId').value = s.cashfree.appId || '';
  document.getElementById('cfSecret').value = s.cashfree.secretKey || '';
  document.getElementById('cfEnv').value = s.cashfree.env || 'sandbox';
  document.getElementById('freeLimit').value = s.app.freeMessageLimit || 5;
  document.getElementById('maintMode').checked = !!s.app.maintenanceMode;
  document.getElementById('maintMsg').value = s.app.maintenanceMessage || '';
  document.getElementById('supportWa').value = s.app.supportWhatsapp || '';
  document.getElementById('supportEmail').value = s.app.supportEmail || '';
}

async function savePixelCapi() {
  document.getElementById('pixelErr').textContent = '';
  document.getElementById('pixelMsg').textContent = '';
  const events = {};
  document.querySelectorAll('[data-pe]').forEach((el) => {
    events[el.dataset.pe] = el.checked;
  });
  const capi = {
    enabled: document.getElementById('capiEnabled').checked,
    pixelId: document.getElementById('capiPixelId').value.trim(),
    testEventCode: document.getElementById('capiTest').value.trim(),
    apiVersion: document.getElementById('capiVersion').value.trim() || 'v21.0',
    sendPurchase: document.getElementById('capiPurchase').checked,
    sendRegistration: document.getElementById('capiReg').checked,
    sendInitiateCheckout: document.getElementById('capiCheckout').checked,
    sendLead: document.getElementById('capiLead').checked,
  };
  const tok = document.getElementById('capiToken').value.trim();
  if (tok) capi.accessToken = tok;
  try {
    await api('/admin/settings', {
      method: 'PUT',
      body: JSON.stringify({
        pixel: {
          enabled: document.getElementById('pixelEnabled').checked,
          pixelId: document.getElementById('pixelId').value.trim(),
          events,
        },
        capi,
      }),
    });
    document.getElementById('pixelMsg').textContent = 'Saved';
  } catch (e) {
    document.getElementById('pixelErr').textContent = e.message;
  }
}

async function saveIntegrations() {
  await api('/admin/settings', {
    method: 'PUT',
    body: JSON.stringify({
      clevertap: {
        enabled: document.getElementById('ctEnabled').checked,
        accountId: document.getElementById('ctAccount').value.trim(),
        token: document.getElementById('ctToken').value.trim(),
        region: document.getElementById('ctRegion').value.trim() || 'in1',
      },
      firebase: {
        enabled: document.getElementById('fbEnabled').checked,
        measurementId: document.getElementById('fbMeasure').value.trim(),
      },
      cashfree: {
        enabled: document.getElementById('cfEnabled').checked,
        appId: document.getElementById('cfAppId').value.trim(),
        secretKey: document.getElementById('cfSecret').value.trim(),
        env: document.getElementById('cfEnv').value,
      },
    }),
  });
  alert('Integrations saved');
}

async function testCapi() {
  document.getElementById('pixelMsg').textContent = 'Sending…';
  try {
    const res = await api('/admin/tracking/test-capi', {
      method: 'POST',
      body: JSON.stringify({ eventName: 'Purchase', value: 1 }),
    });
    document.getElementById('pixelMsg').textContent = res.result?.ok
      ? 'Test OK — check Events Manager'
      : 'Result: ' + (res.result?.reason || res.result?.error || JSON.stringify(res.result));
  } catch (e) {
    document.getElementById('pixelErr').textContent = e.message;
  }
}

async function loadPlans() {
  const res = await api('/admin/plans');
  document.getElementById('plansJson').value = JSON.stringify(res.items || [], null, 2);
}
async function savePlans() {
  await api('/admin/plans', { method: 'PUT', body: document.getElementById('plansJson').value });
  alert('Plans saved');
}
async function loadPandits() {
  const res = await api('/admin/pandits');
  document.getElementById('panditsTable').innerHTML = `<table><tr><th>Name</th><th>Persona</th><th>Rating</th><th>ID</th></tr>${(res.items || [])
    .map((p) => `<tr><td>${p.name}</td><td>${p.persona || ''}</td><td>${p.rating || ''}</td><td class="mono">${p.id}</td></tr>`)
    .join('')}</table>`;
}
async function loadSuggested() {
  const res = await api('/admin/content/suggested');
  document.getElementById('suggestedJson').value = JSON.stringify(res.items || [], null, 2);
}
async function saveSuggested() {
  const items = JSON.parse(document.getElementById('suggestedJson').value);
  await api('/admin/content/suggested', { method: 'PUT', body: JSON.stringify({ items }) });
  alert('CMS saved');
}
async function loadFlags() {
  const res = await api('/admin/flags');
  flagsCache = res.flags || {};
  document.getElementById('flagsForm').innerHTML = Object.keys(flagsCache)
    .map(
      (k) =>
        `<div class="switch"><input type="checkbox" data-flag="${k}" ${flagsCache[k] ? 'checked' : ''}/> <code>${k}</code></div>`,
    )
    .join('');
}
async function saveFlags() {
  const flags = {};
  document.querySelectorAll('[data-flag]').forEach((el) => {
    flags[el.dataset.flag] = el.checked;
  });
  await api('/admin/flags', { method: 'PUT', body: JSON.stringify({ flags }) });
  alert('Flags saved');
}
async function loadEvents() {
  const res = await api('/admin/tracking/events');
  document.getElementById('eventsTable').innerHTML = `<table><tr><th>Time</th><th>Channel</th><th>Event</th><th>OK</th><th>Detail</th></tr>${(res.items || [])
    .map(
      (e) => `<tr><td class="mono">${new Date(e.ts).toLocaleString()}</td><td><span class="tag">${e.channel}</span></td>
    <td>${e.event_name}</td><td>${e.ok ? '<span class="tag ok">yes</span>' : '<span class="tag bad">no</span>'}</td>
    <td class="mono">${(e.error || e.status || JSON.stringify(e.custom_data || e.meta || {})).toString().slice(0, 100)}</td></tr>`,
    )
    .join('') || '<tr><td colspan="5">No events</td></tr>'}</table>`;
}
async function loadAudit() {
  const res = await api('/admin/audit');
  document.getElementById('auditTable').innerHTML = `<table><tr><th>Time</th><th>Actor</th><th>Action</th><th>Detail</th></tr>${(res.items || [])
    .map(
      (a) => `<tr><td class="mono">${new Date(a.ts).toLocaleString()}</td><td>${a.actor}</td><td>${a.action}</td>
    <td class="mono">${JSON.stringify(a.detail || {}).slice(0, 120)}</td></tr>`,
    )
    .join('') || '<tr><td colspan="4">Empty</td></tr>'}</table>`;
}
async function saveAppSettings() {
  await api('/admin/settings', {
    method: 'PUT',
    body: JSON.stringify({
      app: {
        freeMessageLimit: Number(document.getElementById('freeLimit').value) || 5,
        maintenanceMode: document.getElementById('maintMode').checked,
        maintenanceMessage: document.getElementById('maintMsg').value,
        supportWhatsapp: document.getElementById('supportWa').value.trim(),
        supportEmail: document.getElementById('supportEmail').value.trim(),
      },
    }),
  });
  document.getElementById('appMsg').textContent = 'Saved';
}

function exportCsv(kind) {
  const a = document.createElement('a');
  a.href = API + '/admin/export/' + kind + '.csv';
  // fetch with header then download
  fetch(a.href, { headers: { 'X-Admin-Key': token } })
    .then((r) => r.text())
    .then((txt) => {
      const blob = new Blob([txt], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      a.href = url;
      a.download = kind + '.csv';
      a.click();
      URL.revokeObjectURL(url);
    });
  return false;
}

document.getElementById('password').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') doLogin();
});
if (token) boot();
