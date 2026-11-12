// Each browser gets its own SQLite database. Tabs share one serial request queue.
const distribution = 'https://cdn.jsdelivr.net/pyodide/v314.0.7/full/';
const sourceArchive = new URL('./foodsave_backend.zip', import.meta.url);
const workspace = new URL(import.meta.url).searchParams.get('workspace') || 'shared';
const mount = '/jury-state/foodsave-campus-v1' + (workspace === 'shared' ? '' : '-' + workspace.replace(/[^a-z0-9-]/gi, ''));
let runtimePromise;
let pendingRequests = Promise.resolve();

async function initialize() {
  const {loadPyodide} = await import(distribution + 'pyodide.mjs');
  const py = await loadPyodide({indexURL: distribution});
  const bundle = await fetch(sourceArchive);
  if (!bundle.ok) throw new Error('Не удалось загрузить файлы FoodSave.');
  await py.loadPackage(['fastapi', 'pycryptodome']);
  py.FS.mkdirTree('/foodsave');
  py.unpackArchive(await bundle.arrayBuffer(), 'zip', {extractDir: '/foodsave'});
  py.FS.mkdirTree(mount);
  function sync(populate) {
    return new Promise((resolve, reject) => py.FS.syncfs(populate, err => err ? reject(err) : resolve()));
  }
  let storageAvailable = false;
  if (typeof indexedDB !== 'undefined' && py.FS.filesystems.IDBFS) {
    py.FS.mount(py.FS.filesystems.IDBFS, {}, mount);
    try { await sync(true); storageAvailable = true; }
    catch { py.FS.unmount(mount); }
  }
  py.FS.chdir('/foodsave');
  py.runPython("import sys\nsys.path.insert(0, '/foodsave')\nfrom runtime_adapter import boot, dispatch_json");
  const boot = py.globals.get('boot');
  let initial;
  try { initial = JSON.parse(boot(mount + '/demo.sqlite3')); }
  finally { boot.destroy(); }
  const save = storageAvailable ? () => sync(false) : async () => {};
  await save();
  return {py, dispatch: py.globals.get('dispatch_json'), credentials: initial.credentials, exampleId: initial.example_report_id, save};
}

function getRuntime() {
  if (!runtimePromise) runtimePromise = initialize().catch(error => {
    runtimePromise = null;
    console.error('FoodSave startup:', error);
    throw error;
  });
  return runtimePromise;
}

function encodeBody(text) {
  if (!text) return '';
  const bytes = new TextEncoder().encode(text);
  let binary = '';
  for (let start = 0; start < bytes.length; start += 8192) {
    binary += String.fromCharCode(...bytes.subarray(start, start + 8192));
  }
  return btoa(binary);
}

async function handle(message) {
  const {py, dispatch, credentials, exampleId, save} = await getRuntime();
  if (message.kind === 'exampleReport') return exampleId || null;
  if (message.kind === 'credentials') {
    const name = message.data.username;
    if (name !== 'iskander' && name !== 'reviewer') throw new Error('Выберите роль для входа.');
    return {username: name, password: credentials[name]};
  }
  const {path, method, headers, body} = message.data;
  if (!path.startsWith('/api/v1/')) throw new Error('Некорректный запрос');
  if (path.startsWith('/api/v1/agent/')) await py.loadPackage('scikit-learn');
  const command = JSON.stringify({path, method, headers, session_id: message.sessionId, body_base64: encodeBody(body)});
  const response = JSON.parse(await dispatch(command));
  if ((method !== 'GET' && method !== 'HEAD') || path === '/api/v1/auth/csrf') await save();
  const bytes = Uint8Array.from(atob(response.body_base64), c => c.charCodeAt(0));
  // The adapter keeps the virtual HttpOnly cookie in its session jar.
  const publicHeaders = response.headers.filter(([name]) => name.toLowerCase() !== 'set-cookie');
  return {status: response.status, headers: publicHeaders, bytes};
}

function attach(port) {
  port.onmessage = event => {
    const {id} = event.data;
    pendingRequests = pendingRequests.then(async () => {
      try {
        const result = await handle(event.data);
        port.postMessage({id, result}, result?.bytes ? [result.bytes.buffer] : []);
      } catch (error) {
        console.error('FoodSave request:', error);
        port.postMessage({id, error: String(error.message || error)});
      }
    });
  };
  if (port.start) port.start();
}
if ('onconnect' in self) self.onconnect = event => attach(event.ports[0]);
else attach(self);
