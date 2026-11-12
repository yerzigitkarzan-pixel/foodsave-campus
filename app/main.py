"""FoodSave API: organization-scoped authorization and transactional review workflow."""
from pathlib import Path
from datetime import date,datetime,timedelta
from decimal import Decimal,InvalidOperation
from collections import defaultdict
import calendar
import json
import math
import os
import re
import secrets
import sqlite3
import time
from threading import Lock
from fastapi import FastAPI,Request
from fastapi.responses import JSONResponse,FileResponse,Response
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from .db import connection,init_db,setting
from .auth import COOKIE,SESSION_SECONDS,new_session,get_session,user_dict,hash_password,verify_password,token_hash,now_iso,today
from .catalog import snapshot,ecology_teaching_example
from .analytics import summarize,calculate_ecology,calculate_economy,row_mass
from .xlsx_export import build_xlsx
from .assistant import respond,detect_anomalies
from .entry_context import WASTE_REASONS,REASON_LABELS
from .metrics import calculate_intensity

ROOT=Path(__file__).resolve().parents[1]
STATUSES={'draft','submitted','in_review','returned','accepted'}

class APIError(Exception):
    def __init__(self,status,code,message,fields=None):
        self.status=status;self.code=code;self.message=message;self.fields=fields

def fail(status,code,message,fields=None): raise APIError(status,code,message,fields)

def text_value(value,name,max_length=200):
    if not isinstance(value,str) or not value.strip() or len(value.strip())>max_length:
        fail(422,'invalid_field',f'Поле «{name}» должно содержать от 1 до {max_length} символов.')
    return value.strip()

def integer(value,name,minimum=1,maximum=2**31-1):
    if isinstance(value,bool): fail(422,'invalid_field',f'Некорректное поле «{name}».')
    if isinstance(value,int): n=value
    elif isinstance(value,str) and re.fullmatch(r'\d+',value): n=int(value)
    else: fail(422,'invalid_field',f'Поле «{name}» должно быть целым числом.')
    if not minimum<=n<=maximum: fail(422,'invalid_field',f'Поле «{name}» вне допустимого диапазона.')
    return n

def number(value,name,positive=False,max_value=1e12):
    if isinstance(value,bool) or value is None: fail(422,'invalid_number',f'Введите число в поле «{name}».')
    try: n=Decimal(str(value))
    except (InvalidOperation,ValueError,TypeError): fail(422,'invalid_number',f'Введите число в поле «{name}».')
    if not n.is_finite() or n<0 or (positive and n==0) or n>Decimal(str(max_value)):
        fail(422,'invalid_number',f'Некорректное значение в поле «{name}».')
    return n

def iso_date(value,name='Дата'):
    try:
        if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value): raise ValueError()
        return date.fromisoformat(value)
    except ValueError: fail(422,'invalid_date',f'Поле «{name}»: используйте дату ГГГГ-ММ-ДД.')

def month_value(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}',value):fail(422,'invalid_period','Месяц должен иметь формат ГГГГ-ММ.')
    iso_date(value+'-01','Месяц')
    if value>today().strftime('%Y-%m'): fail(422,'future_period','Отчёт за будущий месяц создать нельзя.')
    return value

def active_bool(value):
    if value not in (True,False,0,1) or isinstance(value,str):fail(422,'invalid_active','Активность должна быть логическим значением.')
    return int(bool(value))

def authenticate(conn,request,mutation=False):
    session=get_session(conn,request.cookies.get(COOKIE))
    if not session or not session['user_id']: fail(401,'not_authenticated','Войдите в систему.')
    user=user_dict(conn,session['user_id'])
    if not user or not user['active']:fail(401,'not_authenticated','Учётная запись недоступна. Войдите снова.')
    if user['role']=='operator' and not user['organization_active']: fail(403,'organization_inactive','Организация неактивна.')
    if mutation and not secrets.compare_digest(request.headers.get('x-csrf-token',''),session['csrf_token']):
        fail(403,'csrf_failed','Защита формы: обновите страницу и повторите действие.')
    return user,session

def require_reviewer(user):
    if user['role']!='reviewer': fail(403,'forbidden','Действие доступно проверяющему.')

def scoped_org(conn,user,value=None,required=False):
    if user['role']=='operator':
        oid=user['organization_id']
        if value is not None and integer(value,'Организация')!=oid:fail(404,'not_found','Организация не найдена.')
        return oid
    if value in (None,''):
        if required:fail(422,'organization_required','Выберите организацию.')
        return None
    oid=integer(value,'Организация')
    if not conn.execute('SELECT 1 FROM organizations WHERE id=?',(oid,)).fetchone():fail(404,'not_found','Организация не найдена.')
    return oid

def require_report(conn,user,report_id):
    row=conn.execute('SELECT * FROM reports WHERE id=?',(report_id,)).fetchone()
    if not row or (user['role']=='operator' and row['organization_id']!=user['organization_id']):fail(404,'not_found','Отчёт не найден.')
    return row

def editable(report,user):
    if user['role']!='operator':fail(403,'operator_required','Записи изменяет ответственное лицо организации.')
    if report['status'] not in ('draft','returned'):fail(409,'report_locked','Отчёт заблокирован для изменения. Исправление возможно после возврата.')

def check_revision(report,value):
    if integer(value,'Версия')!=report['revision']:fail(409,'stale_revision','Отчёт изменился. Обновите данные и повторите действие.')

def add_history(conn,report,user,action,destination=None,comment='',details=None):
    conn.execute('INSERT INTO report_history(report_id,action,from_status,to_status,actor_id,comment,timestamp,details) VALUES(?,?,?,?,?,?,?,?)',
      (report['id'],action,report['status'],destination or report['status'],user['id'],comment,now_iso(),json.dumps(details or {},ensure_ascii=False)))

def entry_rows(conn,where='1=1',params=()):
    result=[]
    query='''SELECT e.*,r.organization_id,o.name organization_name,u.full_name responsible_name
      FROM entries e JOIN reports r ON r.id=e.report_id JOIN organizations o ON o.id=r.organization_id
      JOIN users u ON u.id=e.responsible_user_id WHERE '''+where+' ORDER BY e.date,e.id'
    for row in conn.execute(query,params):
        item=dict(row);item.update(json.loads(item.pop('snapshot')));item['quantity']=float(Decimal(item['quantity']))
        result.append(item)
    return result

def entry_totals(rows):
    raw=Decimal(0);volume=Decimal(0);known=Decimal(0);unknown=Decimal(0);daily={};by_type={}
    def add_type(groups,row,quantity,mass):
        item=groups.setdefault(row['waste_type_id'],{'id':row['waste_type_id'],'name':row['waste_name'],'kg':Decimal(0),'l':Decimal(0),'known_mass_kg':Decimal(0),'records':0})
        item[row['unit']]+=quantity
        if mass is not None:item['known_mass_kg']+=mass
        item['records']+=1
    def type_totals(groups):
        return [{**item,**{key:float(item[key]) for key in ('kg','l','known_mass_kg')}} for item in sorted(groups.values(),key=lambda item:(item['name'],item['id']))]
    for row in rows:
        q=Decimal(str(row['quantity']));mass=row_mass(row)
        if mass is not None: known+=mass
        if row['unit']=='kg':raw+=q
        else:
            volume+=q
            if mass is None:unknown+=q
        day=daily.setdefault(row['date'],{'date':row['date'],'kg':Decimal(0),'l':Decimal(0),'by_type':{}})
        day[row['unit']]+=q
        add_type(by_type,row,q,mass);add_type(day['by_type'],row,q,mass)
    days=[{**day,'kg':float(day['kg']),'l':float(day['l']),'by_type':type_totals(day['by_type'])} for _,day in sorted(daily.items())]
    return {'known_mass_kg':float(known),'raw_kg':float(raw),'volume_l':float(volume),'unconverted_l':float(unknown),'records':len(rows),'daily':days,'by_type':type_totals(by_type)}

def report_detail(conn,report_id,detail=True):
    row=conn.execute('SELECT r.*,o.name organization_name FROM reports r JOIN organizations o ON o.id=r.organization_id WHERE r.id=?',(report_id,)).fetchone()
    result=dict(row);rows=entry_rows(conn,'r.id=?',(report_id,));totals=entry_totals(rows)
    service=service_day_rows(conn,'r.id=?',(report_id,))
    totals['intensity']=calculate_intensity(rows,service)
    result.update(entry_count=len(rows),total_kg=totals['known_mass_kg'],total_l=totals['volume_l'],totals=totals)
    if detail:
        result['entries']=rows;result['history']=history_rows(conn,report_id)
        result['service_days']=[{'date':day['date'],'portions':day['portions']} for day in service]
    return result

def history_rows(conn,report_id):
    rows=[]
    for r in conn.execute('SELECT h.*,u.full_name actor_name FROM report_history h JOIN users u ON u.id=h.actor_id WHERE h.report_id=? ORDER BY h.id',(report_id,)):
        d=dict(r);d['details']=json.loads(d['details']);rows.append(d)
    return rows

def available_waste(conn,oid,wid):
    return conn.execute('SELECT w.* FROM waste_types w JOIN org_waste_types ow ON ow.waste_type_id=w.id WHERE w.id=? AND ow.organization_id=? AND w.active=1',(wid,oid)).fetchone()

def parse_report_date(report,value):
    d=iso_date(value)
    if d>today():fail(422,'future_date','Дата записи не может быть в будущем.')
    if d.strftime('%Y-%m')!=report['period']:fail(422,'outside_period','Дата записи должна относиться к месяцу отчёта.')
    return d.isoformat()


def parse_entry_context(body,previous=None):
    previous=dict(previous) if previous is not None else {}
    reason=body.get('reason_code',previous.get('reason_code','unspecified'))
    note=body.get('note',previous.get('note',''))
    if not isinstance(reason,str) or reason not in REASON_LABELS:
        fail(422,'invalid_reason','Выберите причину из справочника или «Не указана».')
    if not isinstance(note,str) or len(note)>1000:
        fail(422,'invalid_note','Комментарий должен быть строкой длиной до 1000 символов.')
    return reason,note.strip()


def parse_entry(conn,report,body,previous=None):
    day=parse_report_date(report,body.get('date'))
    qty=number(body.get('quantity'),'Количество',True,10000)
    if qty!=qty.quantize(Decimal('0.001')):fail(422,'quantity_precision','Допустимо не более трёх знаков после запятой.')
    wid=integer(body.get('waste_type_id'),'Вид отходов');mid=integer(body.get('method_id'),'Способ')
    waste=available_waste(conn,report['organization_id'],wid)
    if not waste:fail(422,'invalid_waste_type','Выберите активный вид отходов своей организации.')
    method=conn.execute('SELECT * FROM methods WHERE id=? AND active=1',(mid,)).fetchone()
    if not method:fail(422,'invalid_method','Выберите активный способ утилизации.')
    reason,note=parse_entry_context(body,previous)
    return day,wid,str(qty),mid,snapshot(waste,method),reason,note


def service_day_rows(conn,where='1=1',params=()):
    return [dict(row) for row in conn.execute('''SELECT sd.report_id,r.organization_id,
      o.name organization_name,sd.date,sd.portions FROM service_days sd
      JOIN reports r ON r.id=sd.report_id JOIN organizations o ON o.id=r.organization_id
      WHERE '''+where+' ORDER BY sd.date,r.organization_id',params)]


def filtered_service_days(conn,user,filters):
    # Type/method filters select the numerator and eligible measured pairs in
    # calculate_intensity. One organization/day denominator is never copied
    # for each matching waste row.
    oid=scoped_org(conn,user,filters.get('organization_id'))
    where=["r.status='accepted'",'sd.date>=?','sd.date<=?']
    values=[filters['from'],filters['to']]
    if oid is not None:where.append('r.organization_id=?');values.append(oid)
    return service_day_rows(conn,' AND '.join(where),values)

def filtered_rows(conn,user,params,include_dates=True):
    start=params.get('from') or setting(conn,'default_from',today().replace(day=1).isoformat())
    end=params.get('to') or setting(conn,'default_to',today().isoformat())
    d1=iso_date(start,'Начало периода');d2=iso_date(end,'Конец периода')
    if d1>d2:fail(422,'invalid_range','Начало периода должно быть раньше конца.')
    oid=scoped_org(conn,user,params.get('organization_id'))
    where=["r.status='accepted'"];values=[]
    if include_dates:where+=['e.date>=?','e.date<=?'];values+=[start,end]
    if oid is not None:where.append('r.organization_id=?');values.append(oid)
    for key,column in [('waste_type_id','e.waste_type_id'),('method_id','e.method_id')]:
        if params.get(key) not in (None,''):where.append(column+'=?');values.append(integer(params[key],key))
    rows=entry_rows(conn,' AND '.join(where),values)
    return rows,{'from':start,'to':end,'organization_id':oid,'waste_type_id':params.get('waste_type_id'),'method_id':params.get('method_id')}

def previous_period(start,end):
    s=date.fromisoformat(start);e=date.fromisoformat(end)
    fullmonths=s.day==1 and e.day==calendar.monthrange(e.year,e.month)[1]
    if fullmonths:
        n=(e.year-s.year)*12+e.month-s.month+1
        prev_end=s-timedelta(days=1)
        serial=s.year*12+s.month-1-n
        return date(serial//12,serial%12+1,1).isoformat(),prev_end.isoformat()
    duration=(e-s).days+1
    return (s-timedelta(days=duration)).isoformat(),(s-timedelta(days=1)).isoformat()

def missing_reports(conn,user,month,organization_id=None):
    month=month_value(month)
    args=[month];scope=''
    oid=scoped_org(conn,user,organization_id)
    if oid is not None:scope=' AND o.id=?';args.append(oid)
    return [dict(r) for r in conn.execute('''SELECT o.id organization_id,o.name organization_name,
      COALESCE(r.status,'missing') status,r.id report_id FROM organizations o
      LEFT JOIN reports r ON r.organization_id=o.id AND r.period=?
      WHERE o.active=1 AND (r.id IS NULL OR r.status!='accepted')'''+scope+' ORDER BY o.id',args)]

def create_app(db_path=None):
    path=Path(db_path or os.environ.get('FOODSAVE_DB') or ROOT/'data/demo.sqlite3')
    init_db(path)
    app=FastAPI(title='FoodSave Campus API',version='1.0.0',description='Учёт отходов, проверка отчётов и локальный аналитический агент.')
    app.state.db_path=path
    attempts={};attempts_lock=Lock()
    secure=os.environ.get('FOODSAVE_SECURE_COOKIE','0')=='1'

    def session_cookie(response,token):
        response.set_cookie(COOKIE,token,max_age=SESSION_SECONDS,httponly=True,samesite='lax',secure=secure,path='/')

    @app.middleware('http')
    async def response_headers(request,call_next):
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='same-origin'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'"
        if request.url.path.startswith('/api/') or request.url.path=='/':response.headers['Cache-Control']='no-store'
        return response

    @app.exception_handler(APIError)
    async def api_error(request,error):
        payload={'code':error.code,'message':error.message}
        if error.fields is not None:payload['fields']=error.fields
        return JSONResponse({'error':payload},status_code=error.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request,error):
        return JSONResponse({'error':{'code':'invalid_request','message':'Некорректный запрос: проверьте обязательные поля и формат JSON.'}},status_code=422)

    @app.exception_handler(sqlite3.IntegrityError)
    async def integrity_error(request,error):
        return JSONResponse({'error':{'code':'integrity_conflict','message':'Такая запись уже существует или изменение нарушает связи данных.'}},status_code=409)

    @app.get('/api/v1/health')
    def health():return {'status':'ok','version':'1.0.0'}

    @app.get('/api/v1/meta')
    def meta():
        with connection(path) as conn:return {'app_name':'FoodSave Campus','version':'1.0.0','demo':setting(conn,'demo')=='1','today':today().isoformat(),'current_month':today().strftime('%Y-%m'),'default_from':setting(conn,'default_from',today().replace(day=1).isoformat()),'default_to':setting(conn,'default_to',today().isoformat()),'timezone':'Asia/Almaty (UTC+05:00)','waste_reasons':list(WASTE_REASONS)}

    @app.get('/api/v1/auth/csrf')
    def csrf(request:Request):
        with connection(path,True) as conn:
            session=get_session(conn,request.cookies.get(COOKIE))
            if session:return {'csrf_token':session['csrf_token']}
            token,csrf_token=new_session(conn)
            response=JSONResponse({'csrf_token':csrf_token});session_cookie(response,token);return response

    @app.post('/api/v1/auth/login')
    def login(request:Request,body:dict):
        username=text_value(body.get('username'),'Логин',120).lower()
        password=text_value(body.get('password'),'Пароль',1024)
        key=((request.client.host if request.client else 'local'),username)
        with attempts_lock:
            prior=[t for t in attempts.get(key,[]) if t>time.time()-900]
            if len(prior)>=10:fail(429,'rate_limited','Слишком много попыток. Повторите вход через 15 минут.')
            attempts[key]=prior
        with connection(path,True) as conn:
            session=get_session(conn,request.cookies.get(COOKIE))
            if not session or not secrets.compare_digest(request.headers.get('x-csrf-token',''),session['csrf_token']):fail(403,'csrf_failed','Обновите форму входа и повторите попытку.')
            found=conn.execute('SELECT * FROM users WHERE username=? AND active=1',(username,)).fetchone()
            valid=verify_password(password,found['password_hash']) if found else False
            if not valid:
                with attempts_lock:attempts[key].append(time.time())
                fail(401,'invalid_credentials','Неверный логин или пароль.')
            user=user_dict(conn,found['id'])
            if user['role']=='operator' and not user['organization_active']:fail(403,'organization_inactive','Организация неактивна.')
            conn.execute('DELETE FROM sessions WHERE id_hash=?',(session['id_hash'],))
            token,csrf_token=new_session(conn,user['id'])
            response=JSONResponse({'user':user,'csrf_token':csrf_token});session_cookie(response,token)
            with attempts_lock:attempts.pop(key,None)
            return response

    @app.get('/api/v1/auth/me')
    def me(request:Request):
        with connection(path) as conn:
            user,session=authenticate(conn,request)
            return {'user':user,'csrf_token':session['csrf_token']}

    @app.post('/api/v1/auth/logout')
    def logout(request:Request):
        with connection(path,True) as conn:
            user,session=authenticate(conn,request,True)
            conn.execute('DELETE FROM sessions WHERE id_hash=?',(session['id_hash'],))
            response=JSONResponse({'message':'Вы вышли из системы.'});response.delete_cookie(COOKIE,path='/');return response

    @app.get('/api/v1/organizations')
    def organizations(request:Request):
        with connection(path) as conn:
            user,_=authenticate(conn,request)
            rows=[dict(r) for r in conn.execute('SELECT * FROM organizations'+(' WHERE id=?' if user['role']=='operator' else '')+' ORDER BY id', (user['organization_id'],) if user['role']=='operator' else ())]
            return {'items':rows,'total':len(rows)}

    @app.post('/api/v1/organizations')
    def create_organization(request:Request,body:dict):
        with connection(path,True) as conn:
            user,_=authenticate(conn,request,True);require_reviewer(user)
            name=text_value(body.get('name'),'Название',200);typ=text_value(body.get('type'),'Тип',80)
            address=str(body.get('address') or '')[:300]
            oid=conn.execute('INSERT INTO organizations(name,short_name,type,address) VALUES(?,?,?,?)',(name,name[:24],typ,address)).lastrowid
            return dict(conn.execute('SELECT * FROM organizations WHERE id=?',(oid,)).fetchone())

    @app.patch('/api/v1/organizations/{oid}')
    def update_organization(oid:int,request:Request,body:dict):
        with connection(path,True) as conn:
            user,_=authenticate(conn,request,True);require_reviewer(user)
            row=conn.execute('SELECT * FROM organizations WHERE id=?',(oid,)).fetchone()
            if not row:fail(404,'not_found','Организация не найдена.')
            values=dict(row)
            for key in ('name','short_name','type'):
                if key in body:values[key]=text_value(body[key],key,200)
            if 'address' in body:values['address']=str(body['address'] or '')[:300]
            if 'active' in body:values['active']=active_bool(body['active'])
            conn.execute('UPDATE organizations SET name=?,short_name=?,type=?,address=?,active=? WHERE id=?',tuple(values[k] for k in ('name','short_name','type','address','active'))+(oid,))
            return values

    @app.get('/api/v1/users')
    def users(request:Request):
        with connection(path) as conn:
            user,_=authenticate(conn,request);require_reviewer(user)
            items=[user_dict(conn,r['id']) for r in conn.execute('SELECT id FROM users ORDER BY id')]
            return {'items':items,'total':len(items)}

    @app.post('/api/v1/users')
    def create_user(request:Request,body:dict):
        with connection(path,True) as conn:
            user,_=authenticate(conn,request,True);require_reviewer(user)
            username=text_value(body.get('username'),'Логин',120).lower()
            if not re.fullmatch(r'[a-z0-9_.@+-]{3,120}',username):fail(422,'invalid_username','Логин: латиница, цифры, точка, @, _, + или дефис; от трёх символов.')
            fullname=text_value(body.get('full_name'),'ФИО',160)
            password=text_value(body.get('password'),'Пароль',1024)
            if len(password)<10:fail(422,'weak_password','Пароль должен содержать минимум 10 символов.')
            role=body.get('role')
            if role not in ('operator','reviewer'):fail(422,'invalid_role','Неизвестная роль.')
            oid=scoped_org(conn,user,body.get('organization_id'),role=='operator') if role=='operator' else None
            uid=conn.execute('INSERT INTO users(username,full_name,password_hash,role,organization_id) VALUES(?,?,?,?,?)',(username,fullname,hash_password(password),role,oid)).lastrowid
            return user_dict(conn,uid)

    @app.patch('/api/v1/users/{uid}')
    def update_user(uid:int,request:Request,body:dict):
        with connection(path,True) as conn:
            user,_=authenticate(conn,request,True);require_reviewer(user)
            row=conn.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
            if not row:fail(404,'not_found','Пользователь не найден.')
            v=dict(row)
            if 'full_name' in body:v['full_name']=text_value(body['full_name'],'ФИО',160)
            if 'role' in body:
                if body['role'] not in ('operator','reviewer'):fail(422,'invalid_role','Неизвестная роль.')
                v['role']=body['role']
            if 'active' in body:v['active']=active_bool(body['active'])
            if uid==user['id'] and (not v['active'] or v['role']!='reviewer'):fail(422,'self_lockout','Нельзя отключить или понизить собственную учётную запись проверяющего.')
            if v['role']=='operator':v['organization_id']=scoped_org(conn,user,body.get('organization_id',v['organization_id']),True)
            else:v['organization_id']=None
            if 'password' in body:
                password=text_value(body['password'],'Пароль',1024)
                if len(password)<10:fail(422,'weak_password','Пароль должен содержать минимум 10 символов.')
                v['password_hash']=hash_password(password)
                conn.execute('DELETE FROM sessions WHERE user_id=?',(uid,))
            conn.execute('UPDATE users SET full_name=?,password_hash=?,role=?,organization_id=?,active=? WHERE id=?',tuple(v[k] for k in ('full_name','password_hash','role','organization_id','active'))+(uid,))
            return user_dict(conn,uid)

    @app.get('/api/v1/waste-types')
    def waste_types(request:Request):
        with connection(path) as conn:
            user,_=authenticate(conn,request);oid=scoped_org(conn,user,request.query_params.get('organization_id'))
            query='SELECT DISTINCT w.* FROM waste_types w';args=[]
            if oid is not None:query+=' JOIN org_waste_types ow ON ow.waste_type_id=w.id WHERE ow.organization_id=?';args.append(oid)
            items=[dict(r) for r in conn.execute(query+' ORDER BY w.name',args)]
            return {'items':items,'total':len(items)}

    @app.post('/api/v1/waste-types')
    def create_waste_type(request:Request,body:dict):
        with connection(path,True) as conn:
            user,_=authenticate(conn,request,True)
            oid=scoped_org(conn,user,body.get('organization_id'),True)
            name=text_value(body.get('name'),'Вид отходов',180);unit=body.get('unit')
            if unit not in ('kg','l'):fail(422,'invalid_unit','Единица должна быть кг или л.')
            category=str(body.get('category') or 'Не указано')[:100];rec=body.get('recyclability','no')
            if rec not in ('yes','partial','no'):fail(422,'invalid_recyclability','Укажите пригодность к переработке.')
            mid=integer(body.get('default_method_id'),'Способ')
            if not conn.execute('SELECT 1 FROM methods WHERE id=? AND active=1',(mid,)).fetchone():fail(422,'invalid_method','Способ не найден.')
            if conn.execute('SELECT 1 FROM waste_types w JOIN org_waste_types ow ON ow.waste_type_id=w.id WHERE ow.organization_id=? AND lower(w.name)=lower(?)',(oid,name)).fetchone():fail(409,'duplicate_type','Такой вид уже доступен организации.')
            wid=conn.execute('INSERT INTO waste_types(name,unit,category,recyclability,default_method_id,organization_id,source_note,coefficient_source) VALUES(?,?,?,?,?,?,?,?)',(name,unit,category,rec,mid,oid,'Добавлено ответственным лицом. Коэффициенты и плотность требуют обоснования.','Пользовательский вид; коэффициент не задан')).lastrowid
            conn.execute('INSERT INTO org_waste_types VALUES(?,?)',(oid,wid))
            return dict(conn.execute('SELECT * FROM waste_types WHERE id=?',(wid,)).fetchone())

    @app.patch('/api/v1/waste-types/{wid}')
    def update_waste_type(wid:int,request:Request,body:dict):
        with connection(path,True) as conn:
            user,_=authenticate(conn,request,True)
            row=conn.execute('SELECT * FROM waste_types WHERE id=?',(wid,)).fetchone()
            if not row or (user['role']=='operator' and row['organization_id']!=user['organization_id']):fail(404,'not_found','Вид отходов не найден или недоступен для изменения.')
            v=dict(row)
            if 'name' in body:v['name']=text_value(body['name'],'Название',180)
            if 'active' in body:v['active']=active_bool(body['active'])
            if 'unit' in body:
                if body['unit'] not in ('kg','l'):fail(422,'invalid_unit','Некорректная единица.')
                if body['unit']!=v['unit'] and conn.execute('SELECT 1 FROM entries WHERE waste_type_id=? LIMIT 1',(wid,)).fetchone():fail(409,'used_unit','Нельзя изменить единицу вида с историческими записями.')
                v['unit']=body['unit']
            if 'recyclability' in body:
                if body['recyclability'] not in ('yes','partial','no'):fail(422,'invalid_recyclability','Некорректный признак переработки.')
                v['recyclability']=body['recyclability']
            if 'default_method_id' in body:
                mid=integer(body['default_method_id'],'Способ')
                if not conn.execute('SELECT 1 FROM methods WHERE id=? AND active=1',(mid,)).fetchone():fail(422,'invalid_method','Способ не найден.')
                v['default_method_id']=mid
            conn.execute('UPDATE waste_types SET name=?,unit=?,recyclability=?,default_method_id=?,active=? WHERE id=?',tuple(v[k] for k in ('name','unit','recyclability','default_method_id','active'))+(wid,))
            return v

    @app.get('/api/v1/disposal-methods')
    def disposal_methods(request:Request):
        with connection(path) as conn:
            authenticate(conn,request)
            items=[dict(r) for r in conn.execute('SELECT * FROM methods ORDER BY priority,id')]
            return {'items':items,'total':len(items)}

    @app.post('/api/v1/disposal-methods')
    def create_method(request:Request,body:dict):
        with connection(path,True) as conn:
            user,_=authenticate(conn,request,True);require_reviewer(user)
            code=text_value(body.get('code'),'Код',20).upper()
            if not re.fullmatch(r'[A-Z0-9_]{2,20}',code):fail(422,'invalid_code','Код: 2–20 латинских букв, цифр или _.')
            name=text_value(body.get('name'),'Название',200)
            mid=conn.execute('INSERT INTO methods(code,name,priority,note) VALUES(?,?,?,?)',(code,name,integer(body.get('priority',5),'Приоритет',1,99),str(body.get('note') or 'Коэффициент не задан.')[:1000])).lastrowid
            return dict(conn.execute('SELECT * FROM methods WHERE id=?',(mid,)).fetchone())

    @app.patch('/api/v1/disposal-methods/{mid}')
    def update_method(mid:int,request:Request,body:dict):
        with connection(path,True) as conn:
            user,_=authenticate(conn,request,True);require_reviewer(user)
            row=conn.execute('SELECT * FROM methods WHERE id=?',(mid,)).fetchone()
            if not row:fail(404,'not_found','Способ не найден.')
            v=dict(row)
            if 'name' in body:v['name']=text_value(body['name'],'Название',200)
            if 'active' in body:v['active']=active_bool(body['active'])
            if 'note' in body:v['note']=str(body['note'] or '')[:1000]
            conn.execute('UPDATE methods SET name=?,note=?,active=? WHERE id=?',(v['name'],v['note'],v['active'],mid))
            return v

    @app.get('/api/v1/reports')
    def list_reports(request:Request):
        with connection(path) as conn:
            user,_=authenticate(conn,request);q=request.query_params
            oid=scoped_org(conn,user,q.get('organization_id'));where=[];values=[]
            if oid is not None:where.append('organization_id=?');values.append(oid)
            if q.get('period'):where.append('period=?');values.append(month_value(q['period']))
            if q.get('status'):
                if q['status'] not in STATUSES:fail(422,'invalid_status','Неизвестный статус отчёта.')
                where.append('status=?');values.append(q['status'])
            clause=' WHERE '+' AND '.join(where) if where else ''
            page=integer(q.get('page','1'),'Страница');size=integer(q.get('page_size','50'),'Размер страницы',1,200)
            total=conn.execute('SELECT COUNT(*) FROM reports'+clause,values).fetchone()[0]
            ids=[r['id'] for r in conn.execute('SELECT id FROM reports'+clause+' ORDER BY period DESC,id DESC LIMIT ? OFFSET ?',values+[size,(page-1)*size])]
            return {'items':[report_detail(conn,rid,False) for rid in ids],'total':total,'page':page,'page_size':size}

    @app.post('/api/v1/reports')
    def create_report(request:Request,body:dict):
        with connection(path,True) as conn:
            user,_=authenticate(conn,request,True)
            if user['role']!='operator':fail(403,'operator_required','Отчёт создаёт ответственное лицо организации.')
            oid=scoped_org(conn,user,body.get('organization_id'),True);period=month_value(body.get('period'))
            if conn.execute('SELECT 1 FROM reports WHERE organization_id=? AND period=?',(oid,period)).fetchone():fail(409,'report_exists','Отчёт за этот месяц уже существует. Откройте его в списке.')
            rid=conn.execute('INSERT INTO reports(organization_id,period,created_by,created_at) VALUES(?,?,?,?)',(oid,period,user['id'],now_iso())).lastrowid
            report=conn.execute('SELECT * FROM reports WHERE id=?',(rid,)).fetchone()
            add_history(conn,report,user,'create')
            return report_detail(conn,rid)

    @app.get('/api/v1/reports/{rid}')
    def get_report(rid:int,request:Request):
        with connection(path) as conn:
            user,_=authenticate(conn,request);require_report(conn,user,rid)
            return report_detail(conn,rid)

    @app.get('/api/v1/reports/{rid}/history')
    def report_history(rid:int,request:Request):
        with connection(path) as conn:
            user,_=authenticate(conn,request);require_report(conn,user,rid)
            return {'items':history_rows(conn,rid)}

    @app.post('/api/v1/reports/{rid}/entries')
    def add_entry(rid:int,request:Request,body:dict):
        with connection(path,True) as conn:
            user,_=authenticate(conn,request,True);report=require_report(conn,user,rid)
            if user['role']!='operator':fail(403,'operator_required','Записи вносит ответственное лицо.')
            request_id=text_value(body.get('client_request_id'),'Идентификатор запроса',120)
            reason,note=parse_entry_context(body)
            existing=conn.execute('SELECT * FROM entries WHERE report_id=? AND client_request_id=?',(rid,request_id)).fetchone()
            if existing:
                same=existing['date']==body.get('date') and existing['waste_type_id']==body.get('waste_type_id') and existing['method_id']==body.get('method_id') and Decimal(existing['quantity'])==number(body.get('quantity'),'Количество',True,10000) and existing['reason_code']==reason and existing['note']==note
                if not same:fail(409,'idempotency_conflict','Этот идентификатор уже использован для другой записи.')
                return report_detail(conn,rid)
            editable(report,user);check_revision(report,body.get('revision'))
            day,wid,quantity,mid,snap,reason,note=parse_entry(conn,report,body)
            duplicate=conn.execute('SELECT id FROM entries WHERE report_id=? AND date=? AND waste_type_id=? AND CAST(quantity AS REAL)=? AND method_id=? LIMIT 1',(rid,day,wid,float(quantity),mid)).fetchone()
            if duplicate and body.get('confirm_duplicate') is not True:fail(409,'possible_duplicate','Похожая запись уже существует. Подтвердите, что это отдельное взвешивание.')
            stamp=now_iso()
            eid=conn.execute('INSERT INTO entries(report_id,date,waste_type_id,quantity,method_id,responsible_user_id,snapshot,client_request_id,created_at,updated_at,reason_code,note) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(rid,day,wid,quantity,mid,user['id'],json.dumps(snap,ensure_ascii=False),request_id,stamp,stamp,reason,note)).lastrowid
            conn.execute('UPDATE reports SET revision=revision+1 WHERE id=?',(rid,))
            add_history(conn,report,user,'entry.created',details={'entry_id':eid,'date':day,'quantity':quantity,'unit':snap['unit'],'waste_name':snap['waste_name'],'reason_code':reason,'note':note})
            return report_detail(conn,rid)

    @app.patch('/api/v1/reports/{rid}/entries/{eid}')
    def update_entry(rid:int,eid:int,request:Request,body:dict):
        with connection(path,True) as conn:
            user,_=authenticate(conn,request,True);report=require_report(conn,user,rid);editable(report,user);check_revision(report,body.get('revision'))
            old=conn.execute('SELECT * FROM entries WHERE id=? AND report_id=?',(eid,rid)).fetchone()
            if not old:fail(404,'not_found','Запись не найдена.')
            day,wid,quantity,mid,snap,reason,note=parse_entry(conn,report,body,old)
            conn.execute('UPDATE entries SET date=?,waste_type_id=?,quantity=?,method_id=?,snapshot=?,reason_code=?,note=?,updated_at=? WHERE id=?',(day,wid,quantity,mid,json.dumps(snap,ensure_ascii=False),reason,note,now_iso(),eid))
            conn.execute('UPDATE reports SET revision=revision+1 WHERE id=?',(rid,))
            add_history(conn,report,user,'entry.updated',details={'entry_id':eid,'before':{'date':old['date'],'waste_type_id':old['waste_type_id'],'quantity':old['quantity'],'method_id':old['method_id'],'reason_code':old['reason_code'],'note':old['note']},'after':{'date':day,'waste_type_id':wid,'quantity':quantity,'method_id':mid,'reason_code':reason,'note':note}})
            return report_detail(conn,rid)

    @app.delete('/api/v1/reports/{rid}/entries/{eid}')
    def delete_entry(rid:int,eid:int,request:Request):
        with connection(path,True) as conn:
            user,_=authenticate(conn,request,True);report=require_report(conn,user,rid);editable(report,user);check_revision(report,request.query_params.get('revision'))
            old=conn.execute('SELECT * FROM entries WHERE id=? AND report_id=?',(eid,rid)).fetchone()
            if not old:fail(404,'not_found','Запись не найдена.')
            conn.execute('DELETE FROM entries WHERE id=?',(eid,));conn.execute('UPDATE reports SET revision=revision+1 WHERE id=?',(rid,))
            add_history(conn,report,user,'entry.deleted',details={'entry_id':eid,'date':old['date'],'quantity':old['quantity'],'snapshot':json.loads(old['snapshot']),'reason_code':old['reason_code'],'note':old['note']})
            return report_detail(conn,rid)

    @app.post('/api/v1/reports/{rid}/service-days')
    def upsert_service_day(rid:int,request:Request,body:dict):
        with connection(path,True) as conn:
            user,_=authenticate(conn,request,True);report=require_report(conn,user,rid)
            editable(report,user);check_revision(report,body.get('revision'))
            day=parse_report_date(report,body.get('date'))
            portions=body.get('portions')
            if isinstance(portions,bool) or not isinstance(portions,int) or not 0<=portions<=100000:
                fail(422,'invalid_portions','Количество порций должно быть целым числом от 0 до 100 000.')
            old=conn.execute('SELECT portions FROM service_days WHERE report_id=? AND date=?',(rid,day)).fetchone()
            conn.execute('''INSERT INTO service_days(report_id,date,portions,updated_by,updated_at)
              VALUES(?,?,?,?,?) ON CONFLICT(report_id,date) DO UPDATE SET
              portions=excluded.portions,updated_by=excluded.updated_by,updated_at=excluded.updated_at''',
              (rid,day,portions,user['id'],now_iso()))
            conn.execute('UPDATE reports SET revision=revision+1 WHERE id=?',(rid,))
            add_history(conn,report,user,'service_day.upserted',details={'date':day,'before_portions':old['portions'] if old else None,'portions':portions})
            return report_detail(conn,rid)

    @app.delete('/api/v1/reports/{rid}/service-days/{day}')
    def delete_service_day(rid:int,day:str,request:Request):
        with connection(path,True) as conn:
            user,_=authenticate(conn,request,True);report=require_report(conn,user,rid)
            editable(report,user);check_revision(report,request.query_params.get('revision'))
            day=parse_report_date(report,day)
            old=conn.execute('SELECT portions FROM service_days WHERE report_id=? AND date=?',(rid,day)).fetchone()
            if not old:fail(404,'not_found','Количество порций за этот день не задано.')
            conn.execute('DELETE FROM service_days WHERE report_id=? AND date=?',(rid,day))
            conn.execute('UPDATE reports SET revision=revision+1 WHERE id=?',(rid,))
            add_history(conn,report,user,'service_day.deleted',details={'date':day,'portions':old['portions']})
            return report_detail(conn,rid)

    def transition(rid,request,body,action):
        with connection(path,True) as conn:
            user,_=authenticate(conn,request,True);report=require_report(conn,user,rid)
            check_revision(report,body.get('revision'))
            if action=='submit':
                editable(report,user)
                if not conn.execute('SELECT 1 FROM entries WHERE report_id=? LIMIT 1',(rid,)).fetchone():fail(422,'empty_report','Добавьте хотя бы одно взвешивание перед отправкой.')
                dest='submitted';comment=''
                conn.execute('UPDATE reports SET status=?,revision=revision+1,submitted_at=?,decided_at=NULL,reviewer_id=NULL WHERE id=?',(dest,now_iso(),rid))
            else:
                require_reviewer(user)
                allowed='submitted' if action=='start-review' else 'in_review'
                if report['status']!=allowed:fail(409,'invalid_transition','Действие недоступно в текущем статусе отчёта.')
                dest={'start-review':'in_review','return':'returned','accept':'accepted'}[action]
                comment=text_value(body.get('comment'),'Комментарий',2000) if action=='return' else str(body.get('comment') or '')[:2000]
                conn.execute('UPDATE reports SET status=?,revision=revision+1,reviewer_id=?,decided_at=?,last_comment=? WHERE id=?',(dest,user['id'],now_iso() if action!='start-review' else None,comment if action=='return' else report['last_comment'],rid))
            add_history(conn,report,user,action,dest,comment)
            return report_detail(conn,rid)

    @app.post('/api/v1/reports/{rid}/submit')
    def submit(rid:int,request:Request,body:dict):return transition(rid,request,body,'submit')

    @app.post('/api/v1/reports/{rid}/start-review')
    def start_review(rid:int,request:Request,body:dict):return transition(rid,request,body,'start-review')

    @app.post('/api/v1/reports/{rid}/return')
    def return_report(rid:int,request:Request,body:dict):return transition(rid,request,body,'return')

    @app.post('/api/v1/reports/{rid}/accept')
    def accept_report(rid:int,request:Request,body:dict):return transition(rid,request,body,'accept')

    @app.get('/api/v1/registry')
    def registry(request:Request):
        with connection(path) as conn:
            user,_=authenticate(conn,request);rows,filters=filtered_rows(conn,user,request.query_params)
            page=integer(request.query_params.get('page','1'),'Страница');size=integer(request.query_params.get('page_size','50'),'Размер страницы',1,200)
            rows.sort(key=lambda row:(row['date'],row['id']),reverse=True)
            return {'items':rows[(page-1)*size:page*size],'total':len(rows),'page':page,'page_size':size,'filters':filters}

    def dashboard_data(conn,user,params):
        rows,filters=filtered_rows(conn,user,params)
        pfrom,pto=previous_period(filters['from'],filters['to'])
        previous_params=dict(params);previous_params.update({'from':pfrom,'to':pto})
        previous,_=filtered_rows(conn,user,previous_params)
        result=summarize(rows,previous)
        service=filtered_service_days(conn,user,filters)
        result.update(service_days=service,intensity=calculate_intensity(rows,service))
        result.setdefault('comparison',{}).update(previous_from=pfrom,previous_to=pto)
        result.update(ecology=calculate_ecology(rows),filters=filters)
        return rows,result

    @app.get('/api/v1/dashboard')
    def dashboard(request:Request):
        with connection(path) as conn:
            user,_=authenticate(conn,request)
            return dashboard_data(conn,user,request.query_params)[1]

    @app.get('/api/v1/missing-reports')
    def missing(request:Request):
        with connection(path) as conn:
            user,_=authenticate(conn,request);month=request.query_params.get('month') or today().strftime('%Y-%m')
            return {'items':missing_reports(conn,user,month,request.query_params.get('organization_id')),'month':month}

    @app.get('/api/v1/ecology')
    def ecology(request:Request):
        with connection(path) as conn:
            user,_=authenticate(conn,request);rows,filters=filtered_rows(conn,user,request.query_params)
            return {**calculate_ecology(rows),'filters':filters,'teaching_example':ecology_teaching_example()}

    @app.post('/api/v1/scenarios/economy')
    def economy(request:Request,body:dict):
        with connection(path) as conn:authenticate(conn,request,True)
        try:return calculate_economy(body)
        except (ValueError,TypeError,InvalidOperation) as exc:fail(422,'invalid_scenario',str(exc))

    @app.get('/api/v1/exports/summary.xlsx')
    def export(request:Request):
        with connection(path) as conn:
            user,_=authenticate(conn,request);rows,dash=dashboard_data(conn,user,request.query_params)
            filters={**dash['filters'],'demo':setting(conn,'demo')=='1','generated_at':now_iso()}
            data=build_xlsx(rows,dash,dash['ecology'],filters)
            filename=f'FoodSave_{filters["from"]}_{filters["to"]}.xlsx'
            return Response(data,media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':f'attachment; filename="{filename}"'})

    @app.post('/api/v1/agent/chat')
    def agent_chat(request:Request,body:dict):
        message=text_value(body.get('message'),'Вопрос агенту',2000)
        with connection(path) as conn:
            user,_=authenticate(conn,request,True)
            rows,filters=filtered_rows(conn,user,body)
            history,_=filtered_rows(conn,user,body,include_dates=False)
            oid=filters['organization_id']
            # A multi-month filter controls the final month of that period.
            # Calendar-year filters may end in the future; do not require
            # reports that cannot yet be created.
            missing_month=min(filters['to'][:7],today().strftime('%Y-%m'))
            missing=missing_reports(conn,user,missing_month,oid)
            intensity=calculate_intensity(rows,filtered_service_days(conn,user,filters))
            org=conn.execute('SELECT name FROM organizations WHERE id=?',(oid,)).fetchone()['name'] if oid else 'Все доступные организации'
        return respond(message,rows,history,{'items':missing,'month':missing_month},{'from':filters['from'],'to':filters['to'],'organization':org,'missing_month':missing_month,'intensity':intensity})

    @app.get('/api/v1/agent/anomalies')
    def agent_anomalies(request:Request):
        with connection(path) as conn:
            user,_=authenticate(conn,request)
            rows,_=filtered_rows(conn,user,request.query_params)
            history,_=filtered_rows(conn,user,request.query_params,include_dates=False)
        return detect_anomalies(rows,history)

    @app.get('/')
    def home():return FileResponse(ROOT/'static/index.html')

    app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')
    return app


app=create_app()
