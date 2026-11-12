"""Reproducible synthetic measurements, five organizations and unique demo credentials."""
from datetime import date,datetime,timedelta,timezone
import calendar
import json
import random
import secrets
from .db import init_db,connection
from .auth import hash_password,today,now_iso
from .catalog import load_catalog,snapshot,reference_recommendations

USER_ORGS={'tpp':1,'thipp':2,'atuinn':3,'canella':4,'iskander':5}

def synthetic_reason(waste,day):
    """Explicit synthetic context; never used to backfill an existing DB."""
    if waste['category']!='Органические':return 'other'
    name=waste['name'].lower()
    if any(word in name for word in ('очистк','скорлуп','кост')):return 'preparation'
    if 'нереализован' in name:return 'overproduction'
    return ('preparation','spoilage','plate_leftovers')[(day+waste['id'])%3]


def synthetic_portions(organization_id,day,month):
    return {1:70,2:55,3:180,4:95,5:620}[organization_id]+((day+month+organization_id)%5)*7

def previous_quarter(anchor):
    start=date(anchor.year,((anchor.month-1)//3)*3+1,1)
    end=start-timedelta(days=1)
    return date(end.year,((end.month-1)//3)*3+1,1),end

def seed_demo(db_path,as_of=None,passwords=None):
    anchor=date.fromisoformat(as_of) if isinstance(as_of,str) else (as_of or today())
    if anchor>today(): raise ValueError('Дата демо не может быть в будущем.')
    init_db(db_path)
    rng=random.Random(20261112)
    creds={}
    with connection(db_path,write=True) as conn:
        if conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]: return {}
        load_catalog(conn)
        for username,oid in [('reviewer',None),*USER_ORGS.items()]:
            password=(passwords or {}).get(username) or secrets.token_urlsafe(12)
            creds[username]=password
            conn.execute('INSERT INTO users(username,full_name,password_hash,role,organization_id) VALUES(?,?,?,?,?)',
             (username,'Демо · Проверяющий' if oid is None else 'Демо · Ответственный '+username,hash_password(password),'reviewer' if oid is None else 'operator',oid))
        reviewer=conn.execute("SELECT id FROM users WHERE username='reviewer'").fetchone()[0]
        users={r['organization_id']:r['id'] for r in conn.execute("SELECT id,organization_id FROM users WHERE role='operator'")}
        methods={r['code']:dict(r) for r in conn.execute('SELECT * FROM methods')}
        recommendations=reference_recommendations()
        start,end=previous_quarter(anchor)
        stamp=now_iso()
        for key,value in {'demo':'1','demo_as_of':anchor.isoformat(),'default_from':start.isoformat(),'default_to':end.isoformat()}.items():
            conn.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(key,value))
        for oid,uid in users.items():
            wastes=[dict(r) for r in conn.execute('SELECT w.* FROM waste_types w JOIN org_waste_types ow ON ow.waste_type_id=w.id WHERE ow.organization_id=?',(oid,))]
            for month in range(start.month,end.month+1):
                period=f'{start.year:04d}-{month:02d}'
                rid=conn.execute("INSERT INTO reports(organization_id,period,status,created_by,created_at,submitted_at,reviewer_id,decided_at) VALUES(?,?,'accepted',?,?,?,?,?)",(oid,period,uid,stamp,stamp,reviewer,stamp)).lastrowid
                for day in range(1,calendar.monthrange(start.year,month)[1]+1):
                    d=date(start.year,month,day)
                    if d.weekday()>=5: continue
                    conn.execute('INSERT INTO service_days(report_id,date,portions,updated_by,updated_at) VALUES(?,?,?,?,?)',
                      (rid,d.isoformat(),synthetic_portions(oid,day,month),uid,stamp))
                    chosen=rng.sample(wastes,min(3,len(wastes)))
                    for w in chosen:
                        scale={1:2.4,2:1.8,3:13.0,4:3.8,5:24.0}[oid]
                        if w['unit']=='l': scale*=0.23
                        if w['category']!='Органические': scale*=0.25
                        quantity=max(0.05,round(scale*(0.7+rng.random()*0.6)*(1+0.04*d.weekday()),3))
                        if oid==5 and month==end.month and day in (22,24) and w['category']=='Органические': quantity=round(quantity*4.6,3)
                        alternative=methods[recommendations[w['name']]]
                        method=methods['TBO'] if rng.random()<0.63 else alternative
                        snap=snapshot(w,method)
                        conn.execute('INSERT INTO entries(report_id,date,waste_type_id,quantity,method_id,responsible_user_id,snapshot,client_request_id,created_at,updated_at,reason_code,note) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                          (rid,d.isoformat(),w['id'],str(quantity),method['id'],uid,json.dumps(snap,ensure_ascii=False),f'seed-{rid}-{d}-{w["id"]}',stamp,stamp,synthetic_reason(w,day),'Синтетическая причина для демонстрации; не фактическое наблюдение.'))
                for src,dest,action,actor in [('draft','submitted','submit',uid),('submitted','in_review','start-review',reviewer),('in_review','accepted','accept',reviewer)]:
                    conn.execute('INSERT INTO report_history(report_id,action,from_status,to_status,actor_id,comment,timestamp) VALUES(?,?,?,?,?,?,?)',(rid,action,src,dest,actor,'Синтетическая история демо',stamp))
            status={1:'submitted',2:'returned',3:'in_review',4:'draft',5:'draft'}[oid]
            comment='Уточните количество и способ утилизации. Демонстрационный возврат.' if status=='returned' else None
            rid=conn.execute('INSERT INTO reports(organization_id,period,status,created_by,created_at,last_comment) VALUES(?,?,?,?,?,?)',(oid,anchor.strftime('%Y-%m'),status,uid,stamp,comment)).lastrowid
            conn.execute('INSERT INTO service_days(report_id,date,portions,updated_by,updated_at) VALUES(?,?,?,?,?)',
              (rid,anchor.isoformat(),synthetic_portions(oid,anchor.day,anchor.month),uid,stamp))
            for i,w in enumerate(wastes[:2]):
                method=methods['TBO'];snap=snapshot(w,method)
                quantity=round(2.5+(oid*1.3)+i,3)
                conn.execute('INSERT INTO entries(report_id,date,waste_type_id,quantity,method_id,responsible_user_id,snapshot,client_request_id,created_at,updated_at,reason_code,note) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(rid,anchor.isoformat(),w['id'],str(quantity),method['id'],uid,json.dumps(snap,ensure_ascii=False),f'current-{oid}-{i}',stamp,stamp,synthetic_reason(w,anchor.day),'Синтетическая причина для демонстрации; не фактическое наблюдение.'))
            transitions=[(None,'draft','create',uid)]
            if status in ('submitted','returned','in_review'): transitions.append(('draft','submitted','submit',uid))
            if status in ('returned','in_review'): transitions.append(('submitted','in_review','start-review',reviewer))
            if status=='returned':transitions.append(('in_review','returned','return',reviewer))
            for src,dest,action,actor in transitions:
                conn.execute('INSERT INTO report_history(report_id,action,from_status,to_status,actor_id,comment,timestamp) VALUES(?,?,?,?,?,?,?)',(rid,action,src,dest,actor,comment if action=='return' else '',stamp))
    return creds
