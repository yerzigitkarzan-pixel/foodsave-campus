"""Password hashing and opaque server-side sessions; no external auth service."""
import hashlib
import secrets
import time
from datetime import datetime,timezone,timedelta

SESSION_SECONDS=8*60*60
COOKIE='foodsave_session'

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def today():
    return datetime.now(timezone(timedelta(hours=5))).date()

def hash_password(password):
    salt=secrets.token_hex(16)
    digest=hashlib.scrypt(password.encode('utf-8'),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
    return f'scrypt${salt}${digest}'

def verify_password(password,encoded):
    try:
        algorithm,salt,expected=encoded.split('$')
        if algorithm!='scrypt': return False
        actual=hashlib.scrypt(password.encode('utf-8'),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
        return secrets.compare_digest(actual,expected)
    except (ValueError,TypeError):
        return False

def token_hash(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()

def new_session(conn,user_id=None):
    token=secrets.token_urlsafe(32)
    csrf=secrets.token_urlsafe(24)
    now=int(time.time())
    conn.execute('DELETE FROM sessions WHERE expires_at<?',(now,))
    conn.execute('INSERT INTO sessions VALUES(?,?,?,?,?)',(token_hash(token),csrf,user_id,now,now+SESSION_SECONDS))
    return token,csrf

def get_session(conn,token):
    if not token or len(token)>200: return None
    return conn.execute('SELECT * FROM sessions WHERE id_hash=? AND expires_at>?',(token_hash(token),int(time.time()))).fetchone()

def user_dict(conn,user_id):
    row=conn.execute('''SELECT u.id,u.username,u.full_name,u.role,u.organization_id,u.active,
        o.name organization_name,o.active organization_active FROM users u
        LEFT JOIN organizations o ON o.id=u.organization_id WHERE u.id=?''',(user_id,)).fetchone()
    return dict(row) if row else None
