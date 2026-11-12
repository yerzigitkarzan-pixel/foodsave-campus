'use strict';

// The normal, server-hosted entry point does not load this transport.
window.FOODSAVE_JURY_MODE = true;
window.FoodSaveJury = (() => {
  const workerUrl = new URL('./worker.mjs', document.currentScript.src);
  let sessionId;
  try {
    sessionId = sessionStorage.getItem('foodsave:browser-session');
    if (!sessionId) {
      sessionId = crypto.randomUUID();
      sessionStorage.setItem('foodsave:browser-session', sessionId);
    }
  } catch {
    sessionId = crypto.randomUUID();
  }

  const pending = new Map();
  let port;
  let instance;
  let nextId = 0;

  function receive(event) {
    const {id, result, error} = event.data;
    const waiting = pending.get(id);
    if (!waiting) return;
    pending.delete(id);
    if (error) waiting.reject(new Error(error));
    else waiting.resolve(result);
  }

  function connect() {
    if (port) return;
    if (typeof SharedWorker === 'function') {
      try {
        instance = new SharedWorker(workerUrl, {type: 'module', name: 'foodsave-jury-v1'});
        port = instance.port;
      } catch { /* Private browsing can disable shared workers. */ }
    }
    if (!port) {
      workerUrl.searchParams.set('workspace', sessionId);
      instance = new Worker(workerUrl, {type: 'module'});
      port = instance;
    }
    port.onmessage = receive;
    instance.onerror = () => {
      for (const item of pending.values()) item.reject(new Error('Не удалось открыть приложение. Обновите страницу и повторите вход.'));
      pending.clear();
      if (port && port.close) port.close();
      port = null;
    };
    if (port.start) port.start();
  }

  function call(kind, data) {
    connect();
    const id = ++nextId;
    return new Promise((resolve, reject) => {
      pending.set(id, {resolve, reject});
      try { port.postMessage({id, kind, data, sessionId}); }
      catch (error) { pending.delete(id); reject(error); }
    });
  }

  return {
    credentials(username) { return call('credentials', {username}); },
    exampleReport() { return call('exampleReport', {}); },
    async fetch(path, options = {}) {
      const url = new URL(path, location.origin);
      if (url.origin !== location.origin || !url.pathname.startsWith('/api/v1/')) throw new Error('Некорректный адрес API');
      const result = await call('request', {
        path: url.pathname + url.search,
        method: options.method || 'GET',
        headers: Object.fromEntries(new Headers(options.headers)),
        body: options.body == null ? '' : String(options.body)
      });
      const body = result.status === 204 || result.status === 304 ? null : result.bytes;
      return new Response(body, {status: result.status, headers: result.headers});
    }
  };
})();
