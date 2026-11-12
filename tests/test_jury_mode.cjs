/* Transport contract checks only. Real Worker/backend E2E is separate. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const {JSDOM} = require('jsdom');
const read = name => fs.readFileSync(path.join(__dirname, '..', 'static', name), 'utf8');
const tick = () => new Promise(resolve => setTimeout(resolve, 0));
async function until(check) {
  for (let i = 0; i < 100; i++) { if (check()) return; await tick(); }
  throw Error('UI condition not reached');
}
async function mount(t, {jury = true, bridge = true, query = '', delayMeta = false, exampleId = 9, exampleError = false} = {}) {
  const dom = new JSDOM(read('index.html'), {url: 'https://example.test/foodsave-campus/' + query, runScripts: 'outside-only'});
  const win = dom.window, doc = win.document;
  t.after(() => win.close());
  win.FOODSAVE_JURY_MODE = jury;
  win.HTMLDialogElement.prototype.close = function () { this.open = false; };
  win.HTMLDialogElement.prototype.showModal = function () { this.open = true; };
  const calls = [], downloads = [];
  let user = null, csrf = 'anonymous-csrf', nativeCount = 0, bridgeCount = 0, exampleCount = 0, capturedBlob;
  let releaseMeta;
  const metaGate = delayMeta ? new Promise(resolve => { releaseMeta = resolve; }) : Promise.resolve();
  const meta = {demo: true, version: '1.0.0', today: '2026-11-12', current_month: '2026-11', default_from: '2026-07-01', default_to: '2026-09-30', waste_reasons: []};
  const zipBytes = Uint8Array.from([80, 75, 3, 4, 0, 255, 42]);
  win.URL.createObjectURL = blob => { capturedBlob = blob; return 'blob:fixture'; };
  win.URL.revokeObjectURL = () => {};
  win.HTMLAnchorElement.prototype.click = function () { downloads.push({name: this.download, href: this.href}); };
  async function response(url, options = {}) {
    const address = new URL(url, win.location.href), route = address.pathname.replace('/api/v1', '');
    const method = options.method || 'GET';
    calls.push({route, method, headers: options.headers, body: options.body});
    const json = (data, status = 200) => new Response(JSON.stringify(data), {status, headers: {'Content-Type': 'application/json'}});
    if (route === '/meta') { await metaGate; return json(meta); }
    if (route === '/auth/csrf') return json({csrf_token: csrf});
    if (route === '/auth/me') return user ? json({user, csrf_token: csrf}) : json({error: {message: 'Войдите'}}, 401);
    if (route === '/auth/login') {
      assert.equal(options.headers['X-CSRF-Token'], csrf);
      assert.equal(options.credentials, 'same-origin');
      const body = JSON.parse(options.body);
      assert.equal(body.password, 'synthetic-worker-password');
      user = {id: body.username === 'reviewer' ? 1 : 2, username: body.username, role: body.username === 'reviewer' ? 'reviewer' : 'operator', full_name: body.username, organization_id: body.username === 'reviewer' ? null : 5, organization_name: body.username === 'reviewer' ? null : 'Искандер'};
      csrf = 'signed-in-' + body.username;
      return json({user, csrf_token: csrf});
    }
    if (route === '/auth/logout') {
      assert.equal(options.headers['X-CSRF-Token'], csrf);
      user = null; csrf = 'anonymous-after-logout'; return json({ok: true});
    }
    if (route === '/organizations') return json({items: [{id: 5, name: 'Искандер', short_name: 'Искандер'}]});
    if (route === '/disposal-methods') return json({items: []});
    if (route === '/waste-types') return json({items: []});
    if (route === '/dashboard') return json({totals: {known_mass_kg: 3, raw_kg: 3, volume_l: 0, records: 1, organizations: 1}, monthly: [], by_type: [], by_organization: [], ecology: {}, comparison: {}, by_reason: [], intensity: {total_days: 0}});
    if (route === '/missing-reports') return json({items: [{organization_id: 5, organization_name: 'Искандер', report_id: 9, status: 'draft'}]});
    if (route === '/reports') return json({items: [], total: 0, page: 1, page_size: 25});
    if (route === '/reports/9') return json({id: 9, period: '2026-11', organization_id: 5, organization_name: 'Искандер', status: 'draft', revision: 1, entries: [], service_days: [{date: '2026-11-12', portions: 200}], totals: {known_mass_kg: 3, raw_kg: 3, records: 1, intensity: {total_days: 1, covered_days: 1, complete: true, kg_per_100_portions: 1.5, covered_mass_kg: 3, portions: 200}}, history: []});
    if (route === '/reports/9/service-days') {
      assert.equal(options.headers['X-CSRF-Token'], csrf);
      assert.deepEqual(JSON.parse(options.body), {date: '2026-11-12', portions: 200, revision: 1});
      return json({id: 9, revision: 2});
    }
    if (route === '/exports/summary.xlsx') return new Response(zipBytes, {headers: {'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}});
    throw Error('Unexpected fixture route: ' + route);
  }
  win.fetch = (...args) => { nativeCount++; return response(...args); };
  if (bridge) win.FoodSaveJury = {
    fetch(...args) { bridgeCount++; return response(...args); },
    async credentials(username) { assert.ok(['iskander', 'reviewer'].includes(username)); return {username, password: 'synthetic-worker-password'}; },
    async exampleReport() { exampleCount++; if (exampleError) throw Error('Example not available'); return exampleId; }
  };
  for (const name of ['routes.js', 'app.js']) vm.runInContext(read(name), dom.getInternalVMContext(), {filename: name});
  return {win, doc, calls, downloads, zipBytes, releaseMeta, state: () => ({user, csrf, nativeCount, bridgeCount, exampleCount, capturedBlob})};
}

test('normal FastAPI mode ignores the jury bridge and role query, retaining form login and CSRF', async t => {
  const env = await mount(t, {jury: false, query: '?role=reviewer'});
  await until(() => env.doc.querySelector('#login-form'));
  assert.equal(env.doc.querySelector('[data-action="jury-login"]'), null);
  assert.equal(env.state().bridgeCount, 0);
  const form = env.doc.querySelector('#login-form');
  form.elements.username.value = 'iskander'; form.elements.password.value = 'synthetic-worker-password';
  form.dispatchEvent(new env.win.Event('submit', {bubbles: true, cancelable: true}));
  await until(() => env.doc.querySelector('#content .campus-hero'));
  assert.equal(env.state().user.role, 'operator');
  assert.equal(env.state().bridgeCount, 0);
  assert.ok(env.state().nativeCount > 0);
  assert.equal(env.doc.querySelector('.jury-session'), null);
});

test('jury roles and documents appear before initialization; JSON, CSRF and XLSX use the bridge', async t => {
  const env = await mount(t, {delayMeta: true});
  const role = env.doc.querySelector('[data-action="jury-login"][data-value="iskander"]');
  assert.ok(role);
  assert.ok(env.doc.querySelector('a[href="./docs/presentation/FoodSave-Campus-KK.pdf"]'));
  assert.equal(env.doc.querySelector('input[type="password"]'), null);
  assert.equal(env.doc.body.dataset.juryState, 'preparing');
  role.click();
  assert.equal(role.disabled, true);
  env.releaseMeta();
  await until(() => env.doc.querySelector('#content .campus-hero'));
  assert.equal(env.doc.body.dataset.juryState, 'ready');
  assert.equal(env.win.location.hash, '#overview');
  assert.equal(env.state().nativeCount, 0);
  assert.ok(env.state().bridgeCount > 0);
  assert.equal(env.doc.body.textContent.includes('synthetic-worker-password'), false);
  await env.win.api('/reports/9/service-days', {method: 'POST', body: {date: '2026-11-12', portions: 200, revision: 1}});
  await env.win.downloadExport();
  assert.deepEqual(new Uint8Array(await env.state().capturedBlob.arrayBuffer()), env.zipBytes);
  assert.match(env.downloads[0].name, /^FoodSave_.*\.xlsx$/);
  env.win.localStorage.setItem('foodsave:draft:2:5:9', 'real-local-draft');
  env.win.localStorage.setItem('foodsave:jury:draft:2:5:9', 'synthetic-draft');
  env.doc.querySelector('.jury-session [data-action="logout"]').click();
  await until(() => env.doc.querySelector('[data-action="jury-login"]'));
  assert.equal(env.win.localStorage.getItem('foodsave:draft:2:5:9'), 'real-local-draft');
  assert.equal(env.win.localStorage.getItem('foodsave:jury:draft:2:5:9'), null);
  env.doc.querySelector('[data-action="jury-login"][data-value="reviewer"]').click();
  await until(() => env.doc.querySelector('#content .campus-hero'));
  assert.equal(env.state().user.role, 'reviewer');
  assert.ok(env.doc.querySelector('.nav [href="#review"]'));
  assert.equal(env.state().nativeCount, 0);
});

test('explicit jury role links enter once; choosing another role after logout does not repeat automatic login', async t => {
  const env = await mount(t, {query: '?role=reviewer'});
  await until(() => env.doc.querySelector('#content .campus-hero'));
  assert.equal(env.state().user.role, 'reviewer');
  assert.equal(env.win.location.hash, '#overview');
  assert.equal(env.calls.filter(call => call.route === '/auth/login').length, 1);
  env.doc.querySelector('.jury-session [data-action="logout"]').click();
  await until(() => env.doc.querySelector('[data-action="jury-login"]'));
  await tick(); await tick();
  assert.equal(env.state().user, null);
  assert.equal(env.calls.filter(call => call.route === '/auth/login').length, 1);
  env.doc.querySelector('[data-action="jury-login"][data-value="iskander"]').click();
  await until(() => env.doc.querySelector('#content .campus-hero'));
  assert.equal(env.state().user.role, 'operator');
});

test('a missing jury bridge fails locally without falling back to remote fetch', async t => {
  const env = await mount(t, {bridge: false});
  await until(() => env.doc.body.dataset.juryState === 'error');
  assert.ok(env.doc.querySelector('[data-action="jury-login"]'));
  assert.ok(env.doc.querySelector('#login-error [role="alert"]'));
  assert.equal(env.state().nativeCount, 0);
  assert.equal(env.state().bridgeCount, 0);
  assert.equal(env.state().exampleCount, 0);
});

test('explicit jury role links preserve a report permalink while manual role selection returns to overview', async t => {
  const env = await mount(t, {query: '?role=iskander#reports'});
  await until(() => env.doc.querySelector('#content [data-action="new-report"]'));
  assert.equal(env.win.location.hash, '#reports');
  assert.equal(env.state().user.role, 'operator');
  assert.ok(env.calls.some(call => call.route === '/reports'));
  env.doc.querySelector('.jury-session [data-action="logout"]').click();
  await until(() => env.doc.querySelector('[data-action="jury-login"]'));
  env.doc.querySelector('[data-action="jury-login"][data-value="reviewer"]').click();
  await until(() => env.doc.querySelector('#content .campus-hero'));
  assert.equal(env.win.location.hash, '#overview');
  assert.equal(env.state().user.role, 'reviewer');
});

test('the explicit portions example opens the backend-provided report with the guide', async t => {
  const env = await mount(t, {query: '?role=iskander&example=portions'});
  await until(() => env.doc.querySelector('#entry-form'));
  assert.equal(env.state().exampleCount, 1);
  assert.equal(env.win.location.hash, '#reports/9?guide=1');
  assert.ok(env.calls.some(call => call.route === '/reports/9'));
  assert.equal(env.state().user.role, 'operator');
});

test('an unavailable optional example falls back to the ordinary report list', async t => {
  for (const options of [{exampleId: null}, {exampleId: -1}, {exampleError: true}]) {
    const env = await mount(t, {query: '?role=iskander&example=portions', ...options});
    await until(() => env.doc.querySelector('#content [data-action="new-report"]'));
    assert.equal(env.win.location.hash, '#reports');
    assert.equal(env.state().user.role, 'operator');
    assert.equal(env.state().exampleCount, 1);
    assert.equal(env.calls.some(call => call.route === '/reports/9'), false);
  }
});
