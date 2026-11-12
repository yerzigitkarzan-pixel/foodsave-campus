"""Run the entire local application. First launch provisions unique local credentials."""
from pathlib import Path
import argparse
import os
import secrets
import sys
from app.db import init_db,connection
from app.seed import seed_demo,USER_ORGS
from app.catalog import load_catalog
from app.auth import hash_password,today

ROOT=Path(__file__).resolve().parent

def bootstrap_real(db_path):
    init_db(db_path);creds={}
    with connection(db_path,True) as conn:
        if conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]:return creds
        load_catalog(conn)
        for username,oid in [('reviewer',None),*USER_ORGS.items()]:
            password=secrets.token_urlsafe(12);creds[username]=password
            conn.execute('INSERT INTO users(username,full_name,password_hash,role,organization_id) VALUES(?,?,?,?,?)',(username,'Проверяющий' if oid is None else 'Ответственный '+username,hash_password(password),'reviewer' if oid is None else 'operator',oid))
        for key,value in {'demo':'0','default_from':today().replace(day=1).isoformat(),'default_to':today().isoformat()}.items():conn.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(key,value))
    return creds

def main():
    parser=argparse.ArgumentParser(description='FoodSave Campus: полный локальный сервер, интерфейс и аналитический агент.')
    parser.add_argument('--host',default=None)
    parser.add_argument('--port',type=int,default=None)
    parser.add_argument('--db',default=None)
    parser.add_argument('--real',action='store_true',help='Отдельная база без синтетических измерений')
    parser.add_argument('--preview',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--strictPort',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args()
    db_path=Path(args.db or os.environ.get('FOODSAVE_DB') or ROOT/'data'/('real.sqlite3' if args.real else 'demo.sqlite3')).resolve()
    creds=bootstrap_real(db_path) if args.real else seed_demo(db_path)
    local=ROOT/'.local';local.mkdir(exist_ok=True)
    if creds:
        lines=['FoodSave Campus — локальные учётные записи','База: '+str(db_path),'Пароли сгенерированы при первом запуске. Храните этот файл локально.','']
        for username,password in creds.items():lines.append(f'{username}: {password}')
        target=local/('REAL_ACCESS.txt' if args.real else 'DEMO_ACCESS.txt')
        if target.exists():target=local/(target.stem+'_'+secrets.token_hex(4)+'.txt')
        target.write_text('\n'.join(lines)+'\n',encoding='utf-8')
        try:target.chmod(0o600)
        except OSError:pass
        print('\n'.join(lines),flush=True)
        print('\nФайл доступа: '+str(target),flush=True)
    os.environ['FOODSAVE_DB']=str(db_path)
    host=args.host or ('0.0.0.0' if args.preview else '127.0.0.1')
    port=args.port or int(os.environ.get('PORT') or (3000 if args.preview else 8000))
    print(f'\nFoodSave Campus: http://{host}:{port}\nБаза: {db_path}\nОстановка: Ctrl+C',flush=True)
    import uvicorn
    uvicorn.run('app.main:app',host=host,port=port,reload=False,proxy_headers=True,forwarded_allow_ips='127.0.0.1')

if __name__=='__main__':main()
