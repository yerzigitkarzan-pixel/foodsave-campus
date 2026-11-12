"""Run the original FoodSave ASGI application inside a serialized browser worker.

Only synthetic state created by app.seed is accepted. This module never reads
the desktop installation's databases, passwords, environment files or logs.
The JavaScript host owns /jury-state persistence and package loading.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
from contextlib import closing
from datetime import date, timedelta
import hashlib
from http.cookies import SimpleCookie
import importlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
from urllib.parse import unquote, urlsplit


_app = None
_db_path: Path | None = None
_credentials: dict[str, str] = {}
_example_report_id: int | None = None
_cookie_jars: dict[str, dict[str, str]] = {}
_request_lock = asyncio.Lock()
_compatibility_installed = False
_EXAMPLE_SETTING = 'browser_teaching_report_v1'
_EXAMPLE_MARKER = 'foodsave-browser-teaching-example-v1'


def _install_worker_compatibility():
    """Adapt unavailable OS facilities without changing application rules."""
    global _compatibility_installed
    if _compatibility_installed:
        return
    import anyio.to_thread

    if sys.platform == 'emscripten':
        # Original API handlers are synchronous. They already run off the UI
        # thread in the Web Worker; AnyIO must not create another OS thread.
        async def inline_run_sync(function, *args, abandon_on_cancel=False,
                                  cancellable=None, limiter=None):
            return function(*args)

        anyio.to_thread.run_sync = inline_run_sync

    if not callable(getattr(hashlib, 'scrypt', None)):
        # Pyodide 314 removed OpenSSL. The compiled PyCryptodome package
        # provides the same RFC 7914 algorithm and original hash parameters.
        from Crypto.Protocol.KDF import scrypt as crypto_scrypt

        def compatible_scrypt(password, *, salt, n, r, p, maxmem=0, dklen=64):
            if maxmem and 128 * n * r > maxmem:
                raise ValueError('scrypt memory limit exceeded')
            return crypto_scrypt(password, salt, dklen, n, r, p)

        hashlib.scrypt = compatible_scrypt
    _compatibility_installed = True


def _validate_existing_demo(path):
    if not path.exists() or path.stat().st_size == 0:
        return
    try:
        with closing(sqlite3.connect(str(path))) as connection:
            integrity = connection.execute('PRAGMA quick_check').fetchall()
            demo = connection.execute("SELECT value FROM settings WHERE key='demo'").fetchone()
            if integrity != [('ok',)] or not demo or demo[0] != '1':
                raise ValueError('Only an intact synthetic demo database is supported')
    except (sqlite3.Error, ValueError) as error:
        raise RuntimeError('Сохранённая браузерная демобаза повреждена или не является демонстрационной. Сбросьте только браузерные демоданные.') from error


def _checkpoint():
    if _db_path is not None:
        with closing(sqlite3.connect(str(_db_path))) as connection:
            connection.execute('PRAGMA wal_checkpoint(TRUNCATE)')


def _ensure_browser_teaching_report(path):
    """Create one marked example atomically; never reset an author's edits."""
    from app.auth import now_iso
    from app.catalog import snapshot
    from app.db import connection, setting

    with connection(path, write=True) as conn:
        if setting(conn, 'demo') != '1':
            return None

        def marked_history(report_id):
            for row in conn.execute("SELECT details FROM report_history WHERE report_id=? AND action='create'", (report_id,)):
                try:
                    if json.loads(row['details']).get('browser_example_marker') == _EXAMPLE_MARKER:
                        return True
                except (ValueError, TypeError, AttributeError):
                    pass
            return False

        stored = setting(conn, _EXAMPLE_SETTING)
        if stored is not None:
            try:
                report_id = json.loads(stored)['report_id']
                if isinstance(report_id, bool) or not isinstance(report_id, int):
                    return None
                if conn.execute('SELECT 1 FROM reports WHERE id=?', (report_id,)).fetchone() and marked_history(report_id):
                    return report_id
            except (ValueError, TypeError, KeyError):
                pass
            # A removed/corrupted marker is not permission to recreate a
            # previously accepted, edited or deliberately removed example.
            return None

        def remember(report_id):
            conn.execute('INSERT INTO settings(key,value) VALUES(?,?)',
                         (_EXAMPLE_SETTING, json.dumps({'report_id': report_id})))
            return report_id

        # Recovery if an older state retained history but lost the setting.
        for row in conn.execute("SELECT DISTINCT r.id FROM reports r JOIN report_history h ON h.report_id=r.id WHERE h.action='create' ORDER BY r.id"):
            if marked_history(row['id']):
                return remember(row['id'])

        operator = conn.execute("""SELECT u.id,u.organization_id FROM users u
          JOIN organizations o ON o.id=u.organization_id
          WHERE u.username='iskander' AND u.role='operator' AND u.active=1 AND o.active=1""").fetchone()
        if not operator:
            return None
        waste = conn.execute("""SELECT w.* FROM waste_types w
          JOIN org_waste_types ow ON ow.waste_type_id=w.id
          WHERE ow.organization_id=? AND w.active=1 AND w.unit='kg' AND w.category='Органические'
          ORDER BY CASE WHEN w.name='Остатки нереализованной продукции' THEN 0 ELSE 1 END,w.id LIMIT 1""",
          (operator['organization_id'],)).fetchone()
        method = conn.execute("SELECT * FROM methods WHERE code='TBO' AND active=1").fetchone()
        if not waste or not method:
            return None
        try:
            quarter_start = date.fromisoformat(setting(conn, 'default_from')).replace(day=1)
            candidate = quarter_start - timedelta(days=1)
        except (TypeError, ValueError, OverflowError):
            return None
        for _ in range(120):
            period = candidate.strftime('%Y-%m')
            if not conn.execute('SELECT 1 FROM reports WHERE organization_id=? AND period=?',
                                (operator['organization_id'], period)).fetchone():
                break
            try:
                candidate = candidate.replace(day=1) - timedelta(days=1)
            except OverflowError:
                return None
        else:
            return None

        day = period + '-12'
        stamp = now_iso()
        note = 'Учебный пример браузерной версии: 3 кг и 200 порций. Синтетические данные, не реальные измерения АТУ.'
        report_id = conn.execute("""INSERT INTO reports(organization_id,period,status,revision,created_by,created_at)
          VALUES(?,?,'draft',3,?,?)""", (operator['organization_id'], period, operator['id'], stamp)).lastrowid
        entry_id = conn.execute("""INSERT INTO entries(report_id,date,waste_type_id,quantity,method_id,
          responsible_user_id,snapshot,client_request_id,created_at,updated_at,reason_code,note)
          VALUES(?,?,?,'3',?,?,?,?,?,?,'overproduction',?)""",
          (report_id, day, waste['id'], method['id'], operator['id'],
           json.dumps(snapshot(waste, method), ensure_ascii=False), _EXAMPLE_MARKER, stamp, stamp, note)).lastrowid
        conn.execute('INSERT INTO service_days(report_id,date,portions,updated_by,updated_at) VALUES(?,?,200,?,?)',
                     (report_id, day, operator['id'], stamp))
        for action, details in (
            ('create', {'browser_example_marker': _EXAMPLE_MARKER, 'synthetic': True}),
            ('entry.created', {'entry_id': entry_id, 'date': day, 'quantity': '3', 'unit': 'kg',
                               'waste_name': waste['name'], 'reason_code': 'overproduction', 'note': note}),
            ('service_day.upserted', {'date': day, 'before_portions': None, 'portions': 200}),
        ):
            conn.execute("""INSERT INTO report_history(report_id,action,from_status,to_status,actor_id,timestamp,details)
              VALUES(?,?,?,'draft',?,?,?)""", (report_id, action, None if action == 'create' else 'draft',
               operator['id'], stamp, json.dumps(details, ensure_ascii=False)))
        return remember(report_id)


def boot(db_path: str) -> str:
    """Initialize private synthetic state and return recoverable demo access.

    The host must restore /jury-state from IndexedDB before calling boot and
    sync it afterwards. Only newly generated demo passwords are stored there;
    no credentials are packaged in the source ZIP. Sessions are intentionally
    memory-local, so a reload requires signing in again.
    """
    global _app, _db_path, _credentials, _example_report_id
    if not isinstance(db_path, str) or not db_path:
        raise ValueError('A browser database path is required')
    path = Path(db_path).resolve()
    if sys.platform == 'emscripten' and not path.is_relative_to('/jury-state'):
        raise ValueError('Browser state must remain in /jury-state')
    if _app is not None:
        if path != _db_path:
            raise RuntimeError('Restart the worker before selecting another demo database')
        return json.dumps({'credentials': _credentials, 'example_report_id': _example_report_id}, ensure_ascii=False)

    _install_worker_compatibility()
    _validate_existing_demo(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    access_path = path.parent / 'demo-credentials.json'
    os.environ['FOODSAVE_DB'] = str(path)
    os.environ['FOODSAVE_SECURE_COOKIE'] = '0'
    # Static files are hosted by Pages, but the original app's StaticFiles
    # mount checks that its directory exists during construction.
    (Path(__file__).resolve().parent / 'static').mkdir(exist_ok=True)
    from app.seed import seed_demo
    fresh = seed_demo(path)
    if fresh:
        credentials = fresh
        temporary = access_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(credentials, ensure_ascii=False), encoding='utf-8')
        temporary.replace(access_path)
    else:
        try:
            credentials = json.loads(access_path.read_text(encoding='utf-8'))
            if not isinstance(credentials, dict) or not credentials or any(
                not isinstance(key, str) or not isinstance(value, str) or not value
                for key, value in credentials.items()
            ):
                raise ValueError('Invalid stored demo credentials')
        except (OSError, ValueError, TypeError) as error:
            raise RuntimeError('У этой браузерной демобазы отсутствуют сохранённые демонстрационные пароли. Сбросьте браузерные демоданные, чтобы создать новый синтетический пример.') from error

    example_report_id = _ensure_browser_teaching_report(path)
    backend = importlib.import_module('app.main')
    _app = backend.create_app(path)
    _db_path = path
    _credentials = credentials
    _example_report_id = example_report_id
    _checkpoint()
    return json.dumps({'credentials': credentials, 'example_report_id': example_report_id}, ensure_ascii=False)


def _error_response(status, code, message):
    body = json.dumps({'error': {'code': code, 'message': message}}, ensure_ascii=False).encode('utf-8')
    return {'status': status, 'headers': [['content-type', 'application/json; charset=utf-8']],
            'body_base64': base64.b64encode(body).decode('ascii')}


def _prepare_request(envelope):
    if not isinstance(envelope, dict):
        raise ValueError('Request must be an object')
    target = envelope.get('path', '')
    if not isinstance(target, str):
        raise ValueError('Request path must be a string')
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or parsed.fragment or not parsed.path.startswith('/api/v1/'):
        raise ValueError('Only relative FoodSave API paths are supported')
    method = envelope.get('method', 'GET')
    if not isinstance(method, str) or method.upper() not in {'GET', 'HEAD', 'POST', 'PATCH', 'DELETE', 'PUT', 'OPTIONS'}:
        raise ValueError('Unsupported HTTP method')
    session_id = envelope.get('session_id', 'default')
    if not isinstance(session_id, str) or not session_id or len(session_id) > 128:
        raise ValueError('Invalid browser session identifier')
    raw_headers = envelope.get('headers', {})
    if not isinstance(raw_headers, dict):
        raise ValueError('Headers must be an object')
    headers = []
    for key, value in raw_headers.items():
        if not isinstance(key, str) or not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9!#$%&\x27*+.^_`|~-]+', key):
            raise ValueError('Invalid HTTP header')
        if any(character in value for character in '\r\n\x00'):
            raise ValueError('Invalid HTTP header value')
        if key.lower() not in {'cookie', 'host', 'content-length'}:
            headers.append((key.lower().encode('ascii'), value.encode('latin-1')))
    encoded = envelope.get('body_base64', '')
    if not isinstance(encoded, str):
        raise ValueError('Body must be base64 text')
    body = base64.b64decode(encoded, validate=True)
    jar = _cookie_jars.setdefault(session_id, {})
    if jar:
        headers.append((b'cookie', '; '.join(f'{name}={value}' for name, value in jar.items()).encode('latin-1')))
    headers.extend([(b'host', b'foodsave.browser'), (b'content-length', str(len(body)).encode('ascii'))])
    scope = {'type': 'http', 'asgi': {'version': '3.0', 'spec_version': '2.3'},
             'http_version': '1.1', 'method': method.upper(), 'scheme': 'https',
             'path': unquote(parsed.path), 'raw_path': parsed.path.encode('utf-8'),
             'query_string': parsed.query.encode('utf-8'), 'root_path': '',
             'headers': headers, 'client': ('browser-demo', 0), 'server': ('foodsave.browser', 443)}
    return scope, body, jar


async def _dispatch(envelope):
    if _app is None:
        return _error_response(503, 'browser_not_ready', 'Браузерная среда ещё загружается.')
    try:
        scope, body, jar = _prepare_request(envelope)
    except (ValueError, TypeError, UnicodeError, binascii.Error):
        return _error_response(400, 'invalid_browser_request', 'Некорректный запрос браузерной среды.')
    sent_body = False
    complete = asyncio.Event()
    status = 500
    response_headers = []
    chunks = []

    async def receive():
        nonlocal sent_body
        if not sent_body:
            sent_body = True
            return {'type': 'http.request', 'body': body, 'more_body': False}
        await complete.wait()
        return {'type': 'http.disconnect'}

    async def send(message):
        nonlocal status, response_headers
        if message['type'] == 'http.response.start':
            status = message['status']
            response_headers = list(message.get('headers', []))
        elif message['type'] == 'http.response.body':
            chunks.append(bytes(message.get('body', b'')))
            if not message.get('more_body', False):
                complete.set()

    await _app(scope, receive, send)
    for key, value in response_headers:
        if key.lower() != b'set-cookie':
            continue
        cookie = SimpleCookie()
        cookie.load(value.decode('latin-1'))
        for name, morsel in cookie.items():
            if morsel['max-age'] == '0' or not morsel.value:
                jar.pop(name, None)
            else:
                jar[name] = morsel.value
    _checkpoint()
    return {'status': status,
            'headers': [[key.decode('latin-1'), value.decode('latin-1')] for key, value in response_headers],
            'body_base64': base64.b64encode(b''.join(chunks)).decode('ascii')}


async def dispatch_json(envelope_json: str) -> str:
    """Dispatch one genuine ASGI request; errors retain the normal API shape."""
    try:
        envelope = json.loads(envelope_json)
    except (ValueError, TypeError):
        return json.dumps(_error_response(400, 'invalid_browser_request', 'Некорректный JSON запроса.'), ensure_ascii=False)
    async with _request_lock:
        result = await _dispatch(envelope)
    return json.dumps(result, ensure_ascii=False)
