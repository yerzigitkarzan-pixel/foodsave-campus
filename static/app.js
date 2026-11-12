/* FoodSave Campus. No external assets, libraries or client-side secrets. */
'use strict';

const API = '/api/v1';
const juryMode = () => window.FOODSAVE_JURY_MODE === true;
let juryPreparation = null;
const foodPlanFields=[
  {name:'portions_per_day',label:'Лишних порций в день',base:5,max:100000},
  {name:'cost_per_portion',label:'Продукты на порцию, ₸',base:200,max:1000000},
  {name:'work_days',label:'Рабочих дней в месяце',base:20,max:31}
];
const defaultFoodPlan=()=>Object.fromEntries(foodPlanFields.map(f=>[f.name,String(f.base)]));
const S = {
  meta: {}, user: null, csrf: '', organizations: [], methods: [], wasteTypes: [],
  route: 'overview', filters: {}, reportPeriod: '', reportStatus: '', reportOrg: '',
  reportId: null, report: null, reportGuide: false, reportsPage: 1, registryPage: 1,
  settingsTab: 'types', chat: [], agentBusy: false, loadToken: 0,
  modal: null, pendingEntry: null, economyResult: null, authEpoch: 0,
  juryBusy: false, juryStatus: '', jurySelection: 0,
  foodPlan: defaultFoodPlan(),
  ecologyExampleMass: '100',
  economy: {records_per_period:300,reports_per_period:5,manual_minutes_per_entry:2,system_minutes_per_entry:1,manual_minutes_per_report:60,system_minutes_per_report:10,periods_per_year:12,hourly_cost:0,realizable_fraction:0,capex:0,annual_opex:0}
};

const icons = {
  leaf:'M20 4c-8 0-14 1-14 8a6 6 0 0 0 6 6c7 0 8-6 8-14Z M4 21l11-11 M10 14l-1-4 M10 14l4 1',
  grid:'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
  clipboard:'M9 5H6a2 2 0 0 0-2 2v13h16V7a2 2 0 0 0-2-2h-3 M9 3h6v5H9z M8 13h8 M8 17h5',
  check:'m5 12 4 4L19 6',
  shield:'M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6l-8-3Z m-4 9 3 3 5-5',
  list:'M8 5h13 M8 12h13 M8 19h13 M3 5h.01 M3 12h.01 M3 19h.01',
  agent:'m12 3 2.2 6.8L21 12l-6.8 2.2L12 21l-2.2-6.8L3 12l6.8-2.2L12 3Z M20 2v4 M18 4h4',
  chart:'M4 3v17h17 M8 15V9 M13 15V5 M18 15v-4',
  settings:'M4 7h16 M4 17h16 M8 4v6 M16 14v6',
  building:'M4 21V7l8-4 8 4v14 M2 21h20 M8 9h1 M15 9h1 M8 13h1 M15 13h1 M10 21v-5h4v5',
  logout:'M9 4H4v16h5 M13 8l4 4-4 4 M8 12h13',
  menu:'M4 6h16 M4 12h16 M4 18h16',
  plus:'M12 5v14 M5 12h14',
  arrow:'M5 12h14 m-5-5 5 5-5 5',
  back:'M19 12H5 m5-5-5 5 5 5',
  download:'M12 3v12 m-5-5 5 5 5-5 M4 16v5h16v-5',
  calendar:'M5 5h14v16H5z M8 3v4 M16 3v4 M5 10h14',
  weight:'M5 7h14l3 14H2L5 7Z M9 7V5a3 3 0 0 1 6 0v2',
  recycle:'m9 4 3-2 4 7 M15 5l1 4-4 1 M20 12l2 3-4 6h-5 M17 18l-4 3 3 2 M8 21H4L1 14l3-5 M1 10l3-1 2 4',
  cloud:'M6 18a4 4 0 1 1 .6-7.95A6 6 0 0 1 18 9a4.5 4.5 0 0 1 0 9H6Z',
  clock:'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z M12 7v5l3 2',
  alert:'M12 3 2 21h20L12 3Z M12 9v5 M12 17h.01',
  info:'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z M12 11v6 M12 7h.01',
  edit:'m15 4 5 5 M4 20l5-1L21 7l-5-5L4 14v6Z',
  trash:'M3 6h18 M8 6V3h8v3 M6 6l1 15h10l1-15 M10 10v7 M14 10v7',
  close:'m6 6 12 12 M6 18 18 6',
  send:'m22 2-7 20-4-9-9-4L22 2Z M11 13 22 2',
  lock:'M5 10h14v11H5z M8 10V6a4 4 0 0 1 8 0v4 M12 14v3',
  phone:'M7 2h10v20H7z M11 18h2',
  search:'M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14Z m5 12 6 6',
  refresh:'M20 7V3l-3 3a8 8 0 1 0 3 9 M20 7h-4',
  chevron:'m9 5 7 7-7 7',
  users:'M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z M2 21v-2a7 7 0 0 1 14 0v2 M17 4a4 4 0 0 1 0 8 M18 15a6 6 0 0 1 4 6',
  folder:'M3 6h7l2 3h9v12H3V6Z M3 6V3h7l2 3h9v3',
  globe:'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z M3 12h18 M12 3c-4 5-4 13 0 18 M12 3c4 5 4 13 0 18'
};
const statusLabels = {draft:'Черновик',submitted:'Отправлено',in_review:'На проверке',returned:'На доработке',accepted:'Принято',missing:'Не создан'};
const statusColors = {draft:'gray',submitted:'blue',in_review:'amber',returned:'red',accepted:'green',missing:'gray'};
const routeLabels = {overview:'Обзор',reports:'Мои отчёты',review:'Проверка отчётов',registry:'Единый реестр',agent:'ИИ-агент',effect:'Экономика и экология',settings:'Справочники'};
const palette = ['#b7472a','#29312e','#b8c73f','#c59363','#8b9b91','#d7c9aa'];
const $ = (s,root=document) => root.querySelector(s);
const e = v => String(v ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const icon = (name,cls='') => `<svg class="icon ${e(cls)}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${icons[name] || icons.info}"/></svg>`;
const n = (v,d=2) => v === null || v === undefined || !Number.isFinite(Number(v)) ? '—' : Number(v).toLocaleString('ru-RU',{maximumFractionDigits:d});
const qty = v => n(v,3);
const unit = u => u==='l' ? 'л' : 'кг';
const isoDate = value => {if(!value)return '—';try{return new Date(String(value).slice(0,10)+'T12:00:00').toLocaleDateString('ru-RU');}catch{return String(value);}};
const monthEnd = value => {const [y,m]=String(value).split('-').map(Number);return new Date(Date.UTC(y,m,0)).toISOString().slice(0,10);};
const monthLabel = value => {if(!value)return '—';try{return new Date(value+'-01T12:00:00').toLocaleDateString('ru-RU',{month:'long',year:'numeric'}).replace(' г.','');}catch{return value;}};
const timeLabel = value => {if(!value)return '';try{return new Date(value).toLocaleString('ru-RU',{dateStyle:'short',timeStyle:'short',timeZone:(S.meta.timezone||'Asia/Almaty').split(' ')[0]});}catch{return value;}};
const badge = status => `<span class="pill ${statusColors[status] || 'gray'}"><i class="dot"></i>${e(statusLabels[status]||status)}</span>`;
const items = value => Array.isArray(value)?value:(value?.items || []);
const option = (value,label,selected) => `<option value="${e(value)}"${String(value)===String(selected)?' selected':''}>${e(label)}</option>`;
const isReviewer = () => S.user?.role==='reviewer';
const isEditable = report => S.user?.role==='operator' && ['draft','returned'].includes(report?.status);
const qs = obj => {const q=new URLSearchParams();for(const [k,v] of Object.entries(obj || {})){if(v!=='' && v!==null && v!==undefined)q.set(k,String(v));}return q.toString();};
const orgName = id => S.organizations.find(x=>String(x.id)===String(id))?.name || S.user?.organization_name || 'Все организации';

class ApiError extends Error {constructor(message,status,code,fields){super(message);this.status=status;this.code=code;this.fields=fields;}}
async function fetchApi(url, options={}) {
  if(juryMode()){
    const bridge=window.FoodSaveJury;
    if(!bridge||typeof bridge.fetch!=='function')throw new Error('Браузерная демонстрация ещё не подготовлена. Обновите страницу и повторите вход.');
    return bridge.fetch(url,options);
  }
  return fetch(url,options);
}
function clearSessionState(){
  clearUserDrafts();S.authEpoch++;S.loadToken++;S.agentBusy=false;S.economyResult=null;S.pendingEntry=null;
  S.user=null;S.csrf='';S.chat=[];S.report=null;S.reportId=null;S.reportGuide=false;S.reportTypes=null;
  S.organizations=[];S.methods=[];S.wasteTypes=[];S.users=[];S.settingsTab='types';S.filters={};
  closeModal();
}
async function api(path, options={}) {
  const method=options.method || 'GET';
  const requestEpoch=S.authEpoch;
  const headers={Accept:'application/json',...(options.headers || {})};
  if(options.body!==undefined)headers['Content-Type']='application/json';
  if(!['GET','HEAD'].includes(method))headers['X-CSRF-Token']=S.csrf;
  let response;
  try {response=await fetchApi(API+path,{method,headers,credentials:'same-origin',...(options.body!==undefined?{body:JSON.stringify(options.body)}:{})});}
  catch {throw new ApiError(juryMode()?'Не удалось выполнить запрос в браузерной демонстрации. Повторите действие; при необходимости обновите страницу.':'Не удалось связаться с сервером. Проверьте, запущено ли приложение, и повторите действие.',0,'network');}
  const data=await response.json().catch(()=>({}));
  if(requestEpoch!==S.authEpoch)throw new ApiError('Сессия изменилась. Повторите действие в выбранной роли.',409,'stale_session');
  if(!response.ok){
    const error=data.error || {};
    const details=Array.isArray(data.detail)?data.detail.map(x=>x.msg).join('; '):data.detail;
    if(response.status===401 && S.user && requestEpoch===S.authEpoch){clearSessionState();renderLogin('Сессия закончилась. Войдите ещё раз.');}
    throw new ApiError(error.message || details || `Ошибка запроса (${response.status})`,response.status,error.code || '',error.fields);
  }
  return data;
}
async function prepareJury(){
  if(!juryPreparation){
    juryPreparation=(async()=>{
      const meta=await api('/meta');
      if(meta.demo!==true)throw new Error('Для режима жюри требуется отдельная демонстрационная база.');
      S.meta=meta;S.reportPeriod=S.meta.current_month;S.filters={from:S.meta.default_from,to:S.meta.default_to};
      S.csrf=(await api('/auth/csrf')).csrf_token;
      S.juryStatus='Демонстрационная база готова. Выберите роль.';
      document.body.dataset.juryState='ready';
    })().catch(error=>{juryPreparation=null;document.body.dataset.juryState='error';S.juryStatus='Подготовку можно повторить кнопкой выбранной роли.';throw error;});
  }
  return juryPreparation;
}
async function signIn(credentials,openOverview=false){
  const token=await api('/auth/csrf');S.csrf=token.csrf_token;
  const data=await api('/auth/login',{method:'POST',body:credentials});
  S.user=data.user;S.csrf=data.csrf_token||S.csrf;S.authEpoch++;S.loadToken++;
  S.agentBusy=false;S.pendingEntry=null;S.economyResult=null;S.report=null;S.reportTypes=null;S.modal=null;S.settingsTab='types';
  S.economy={records_per_period:300,reports_per_period:5,manual_minutes_per_entry:2,system_minutes_per_entry:1,manual_minutes_per_report:60,system_minutes_per_report:10,periods_per_year:12,hourly_cost:0,realizable_fraction:0,capex:0,annual_opex:0};
  await loadCatalogs();S.filters={from:S.meta.default_from,to:S.meta.default_to,organization_id:isReviewer()?'':S.user.organization_id};
  S.reportPeriod=isReviewer()?S.meta.current_month:'';S.reportStatus='';S.reportOrg='';S.reportsPage=1;S.registryPage=1;S.reportId=null;S.reportGuide=false;S.chat=[];
  if(openOverview)history.replaceState(null,'','#overview');
  await navigateLocation();
}
function juryPresentationLinks(){
  return '<nav class="jury-documents" aria-label="Презентация"><a href="./docs/presentation/FoodSave-Campus-KK.pdf">Презентация · PDF ↗</a><a href="./docs/presentation/FoodSave-Campus-KK.pptx">Скачать PPTX ↗</a></nav>';
}
function juryLoginContent(error=''){
  return `<div class="login-form-index">Демонстрация для жюри</div><h2>Открыть FoodSave</h2><p>Выберите роль и откройте основной интерфейс с работающими формами.</p><div id="login-error" class="login-error">${error?`<div class="notice error" role="alert">${e(error)}</div>`:''}</div><div class="jury-roles" aria-busy="${S.juryBusy}"><button type="button" class="btn full" data-action="jury-login" data-value="iskander"${S.juryBusy?' disabled':''}><span>Открыть как сотрудник<small>Столовая «Искандер» · ввод взвешиваний</small></span>${icon('arrow')}</button><button type="button" class="btn secondary full" data-action="jury-login" data-value="reviewer"${S.juryBusy?' disabled':''}><span>Открыть как проверяющий<small>Возврат, принятие и общая аналитика</small></span>${icon('shield')}</button></div><p id="jury-status" class="jury-status" role="status">${e(S.juryStatus||'Подготавливаем демонстрационную базу в браузере. Можно выбрать роль уже сейчас.')}</p>${juryPresentationLinks()}<p class="jury-scope">Данные примера сохраняются в этом браузере.</p>`;
}
function jurySessionBar(){
  return `<div class="jury-session"><div><strong>Режим для жюри</strong><small>Основное приложение · демонстрационные данные</small></div>${juryPresentationLinks()}${button('Выбрать роль','logout',{class:'secondary small',icon:'users'})}</div>`;
}
async function enterJuryRole(username,preserveLocation=false){
  if(!juryMode()||S.juryBusy||!['iskander','reviewer'].includes(username))return;
  S.juryBusy=true;
  $('.jury-roles')?.setAttribute('aria-busy','true');
  const controls=[...document.querySelectorAll('[data-action="jury-login"]')];
  for(const control of controls)control.disabled=true;
  const status=$('#jury-status');if(status)status.textContent='Подготавливаем выбранную роль…';
  const errorBox=$('#login-error');if(errorBox)errorBox.innerHTML='';
  try{
    await prepareJury();
    if(typeof window.FoodSaveJury?.credentials!=='function')throw new Error('Вход в демонстрацию ещё не готов. Повторите выбор роли.');
    const credentials=await window.FoodSaveJury.credentials(username);
    if(!credentials||credentials.username!==username||typeof credentials.password!=='string'||!credentials.password)throw new Error('Не удалось подготовить выбранную демонстрационную роль.');
    await signIn({username:credentials.username,password:credentials.password},!preserveLocation);
  }catch(error){
    if($('#login-error'))$('#login-error').innerHTML=`<div class="notice error" role="alert">${e(error.message)}</div>`;
    if($('#jury-status'))$('#jury-status').textContent='Выберите роль, чтобы повторить вход.';
  }finally{
    S.juryBusy=false;
    $('.jury-roles')?.setAttribute('aria-busy','false');
    for(const control of controls)control.disabled=false;
  }
}

function toast(message,error=false) {
  const box=document.createElement('div');box.className='toast'+(error?' error':'');box.setAttribute('role',error?'alert':'status');
  box.innerHTML=icon(error?'alert':'check')+`<span>${e(message)}</span>`;$('#toast-region').append(box);
  setTimeout(()=>box.remove(),error?7500:4300);
}
function loading(text='Загружаем данные…'){return `<div class="loading" role="status"><span class="spinner"></span>${e(text)}</div>`;}
function empty(title='Пока нет данных',text='Измените период или добавьте первые записи.',action=''){return `<div class="empty">${icon('folder')}<h3>${e(title)}</h3><p>${e(text)}</p>${action}</div>`;}
function heading(title,subtitle,actions='',eyebrow='Управление отходами'){return `<div class="page-heading"><div><div class="eyebrow">${e(eyebrow)}</div><h1>${e(title)}</h1><p>${e(subtitle)}</p></div>${actions?`<div class="actions">${actions}</div>`:''}</div>`;}
function button(text,action,opts={}){return `<button type="button" class="btn ${e(opts.class||'')}" data-action="${e(action)}"${opts.id!==undefined?` data-id="${e(opts.id)}"`:''}${opts.value!==undefined?` data-value="${e(opts.value)}"`:''}${opts.disabled?' disabled':''}>${opts.icon?icon(opts.icon):''}${e(text)}</button>`;}
function stat(label,value,units,foot,iconName,featured=false){return `<div class="card stat-card ${featured?'featured':''}"><div class="stat-top"><span>${e(label)}</span><span class="stat-icon">${icon(iconName)}</span></div><div class="stat-value mono">${e(value)}${units?`<small>${e(units)}</small>`:''}</div><div class="stat-foot">${e(foot)}</div></div>`;}

function filterBar(extra=false){
  return `<form id="filter-form" class="filters"><label>С даты<input type="date" name="from" required value="${e(S.filters.from)}" max="${e(S.meta.today)}"></label><label>По дату<input type="date" name="to" required value="${e(S.filters.to)}" max="${e(S.meta.today)}"></label>${isReviewer()?`<label class="org-filter">Организация<select name="organization_id">${option('','Все организации',S.filters.organization_id)}${S.organizations.map(o=>option(o.id,o.short_name||o.name,S.filters.organization_id)).join('')}</select></label>`:''}${extra?`<label>Вид отходов<select name="waste_type_id">${option('','Все виды',S.filters.waste_type_id)}${S.wasteTypes.map(t=>option(t.id,t.name,S.filters.waste_type_id)).join('')}</select></label><label>Способ<select name="method_id">${option('','Все способы',S.filters.method_id)}${S.methods.map(m=>option(m.id,m.name,S.filters.method_id)).join('')}</select></label>`:''}<button class="btn secondary" type="submit">${icon('search')}Показать</button>${button('Квартал','default-period',{class:'ghost'})}<div class="filter-caption">${icon('shield')}Только принятые отчёты</div></form>`;
}
function demoBanner(){return S.meta.demo?`<div class="demo-banner"><span>${icon('info')}Демонстрационные данные<span class="demo-detail">· Синтетические измерения, не фактические результаты АТУ</span></span><span class="pill green">Демо</span></div>`:'';}

function renderLogin(error=''){
  S.foodPlan=defaultFoodPlan();
  S.ecologyExampleMass='100';
  document.body.classList.remove('sidebar-open');
  document.body.classList.toggle('jury-mode',juryMode());
  $('#app').innerHTML=`<div class="login-screen journal-login"><aside class="login-story"><a class="brand" href="#"><span class="brand-mark monogram" aria-hidden="true">FS</span><span class="brand-name">FoodSave<span>Campus / АТУ</span></span></a><div class="login-ledger-index"><span>Университетский комплекс</span><strong>АТУ / ${e((S.meta.today||'').slice(0,4)||'—')}</strong></div><div class="login-copy"><div class="eyebrow">FoodSave Campus</div><h1>Журнал учёта<br><em>отходов.</em></h1><p>Сотрудник вносит взвешивания. Проверяющий принимает месячный отчёт.</p><p class="login-note">Килограммы и литры учитываются отдельно.</p></div><div class="login-bottom"><span>Smart Food Industries</span><span>${S.meta.demo?'Демонстрационный журнал':'Рабочий журнал'}</span></div></aside><main class="login-main"><div class="login-box">${juryMode()?juryLoginContent(error):`<div class="login-form-index">Вход</div><h2>Войти в журнал</h2><p>Используйте учётную запись своей организации.</p><div id="login-error" class="login-error">${error?`<div class="notice error" role="alert">${e(error)}</div>`:''}</div><form id="login-form"><label>Логин<input name="username" autocomplete="username" placeholder="${S.meta.demo?'Например, iskander':'Например, reviewer'}" required autofocus></label><label>Пароль<input type="password" name="password" autocomplete="current-password" placeholder="Введите пароль" required></label><button type="submit" class="btn full">Войти${icon('arrow')}</button></form><details class="login-guide"><summary>Как получить доступ</summary><p>Индивидуальные пароли находятся в терминале запуска или в <code>.local/${S.meta.demo?'DEMO_ACCESS.txt':'REAL_ACCESS.txt'}</code> на компьютере с сервером.</p><p>${S.meta.demo?'Проверяющий: <code>reviewer</code><br>Столовая: <code>iskander</code>':'Учётную запись организации выдаёт администратор.'}</p></details>`}<div class="login-version">FoodSave Campus · ${e(S.meta.version||'1.0')} · ${S.meta.demo?'Демоданные':'Локально'}</div></div></main></div>`;
}

function renderShell(){
  const nav=[['overview','grid','Кампус в цифрах'],['reports','clipboard',isReviewer()?'Отчёты организаций':'Мои отчёты'],...(isReviewer()?[['review','shield','Проверка отчётов']]:[]),['registry','list','Единый реестр'],['agent','agent','Аналитический агент'],['effect','leaf','Экология и экономика'],['settings','settings','Справочники']];
  const initials=(S.user.full_name||S.user.username).split(/\s+/).slice(0,2).map(x=>x[0]).join('').toUpperCase();
  const current=nav.find(([key])=>key===S.route);
  const dateLabel=S.meta.today?new Date(S.meta.today+'T12:00:00').toLocaleDateString('ru-RU',{day:'numeric',month:'long',year:'numeric'}):'Дата сервера недоступна';
  $('#app').innerHTML=`<button class="sidebar-backdrop" data-action="menu" aria-label="Закрыть меню"></button><aside class="sidebar"><a class="brand" href="#overview" data-route="overview"><span class="brand-mark monogram" aria-hidden="true">FS</span><span class="brand-name">FoodSave<span>Campus / АТУ</span></span></a><div class="workspace"><div class="workspace-code">АТУ / ${isReviewer()?'00':e(String(S.user.organization_id||'').padStart(2,'0'))}</div><div class="workspace-name">${isReviewer()?'Все организации':e(S.user.organization_name||'Организация')}<small>${isReviewer()?'Проверка и сводная отчётность':'Журнал подразделения'}</small></div></div><div class="nav-label">Разделы журнала</div><nav class="nav" aria-label="Основная навигация">${nav.map(([key,img,label],index)=>`<a href="#${key}" data-route="${key}" class="${S.route===key?'active':''}"${S.route===key?' aria-current="page"':''}><span class="nav-number" aria-hidden="true">${String(index+1).padStart(2,'0')}</span><span class="nav-text">${e(label)}</span><i class="nav-arrow"></i></a>`).join('')}</nav><div class="sidebar-bottom"><div class="sidebar-edition"><span>${S.meta.demo?'Демонстрационный журнал':'Рабочий журнал'}</span><p>В общий реестр входят только принятые отчёты.</p></div><div class="profile"><div class="avatar">${e(initials)}</div><div class="profile-details"><strong title="${e(S.user.full_name)}">${e(S.user.full_name||S.user.username)}</strong><span>${isReviewer()?'Проверяющий':'Ответственное лицо'}</span></div><button class="btn ghost icon-only" data-action="logout" title="Выйти" aria-label="Выйти">${icon('logout')}</button></div></div></aside><main class="main"><header class="topbar"><button class="btn ghost menu-btn" data-action="menu" aria-label="Открыть меню">${icon('menu')}</button><div class="breadcrumb"><span>Журнал кампуса</span><span class="separator">/</span><strong>${e(current?.[2]||routeLabels[S.route]||'Обзор')}</strong></div><div class="topbar-right"><span class="topbar-status"><i class="dot"></i>${S.meta.demo?'Демо / локально':'Локальная система'}</span><span class="topbar-date">${e(dateLabel)}</span></div></header><div class="content" id="content">${loading()}</div></main>`;
}

async function loadCatalogs(){
  const [orgs,methods,types]=await Promise.all([api('/organizations'),api('/disposal-methods'),api('/waste-types')]);
  S.organizations=items(orgs);S.methods=items(methods);S.wasteTypes=items(types);
}
async function navigateLocation(){
  const target=FoodSaveRoutes.parse(location.hash);
  S.reportId=target.reportId;S.reportGuide=target.guide;
  await navigate(target.route,true);
}
function pageContent(html){
  return (juryMode()?jurySessionBar():'')+demoBanner()+html+'<footer class="view-footer"><span>'+icon('leaf')+'FoodSave Campus · Smart Food Industries</span></footer>';
}
async function navigate(route='overview',fromAddress=false){
  if(!S.user)return;
  if(!routeLabels[route])route='overview';
  if(route==='review'&&!isReviewer())route='reports';
  if(!['reports','review'].includes(route)){S.reportId=null;S.reportGuide=false;}
  if(route!=='registry'){delete S.filters.waste_type_id;delete S.filters.method_id;}
  S.route=route;const routeHash=FoodSaveRoutes.format(route,S.reportId,S.reportGuide);
  if(location.hash!==routeHash)history[fromAddress?'replaceState':'pushState'](null,'',routeHash);
  document.body.classList.remove('sidebar-open');renderShell();
  const token=++S.loadToken;
  try{
    let html;
    if(route==='overview')html=await overviewPage();
    else if(route==='reports'||route==='review')html=await reportsPage();
    else if(route==='registry')html=await registryPage();
    else if(route==='agent')html=agentPage();
    else if(route==='effect')html=await effectPage();
    else html=await settingsPage();
    if(token!==S.loadToken||!S.user)return;
    $('#content').innerHTML=pageContent(html);
    if(S.report&&['reports','review'].includes(route))restoreEntryDraft();
    if(route==='agent')scrollChat();
  }catch(err){
    if(token===S.loadToken&&S.user)$('#content').innerHTML=heading(routeLabels[route],'Данные сейчас недоступны')+`<div class="notice error" role="alert">${e(err.message)}</div><div class="section-gap">${button('Повторить','reload',{icon:'refresh',class:'secondary'})}</div>`;
  }
}

function lineChart(data){
  if(!data?.length)return empty('Нет принятых измерений','Динамика появится после принятия отчётов за выбранный период.');
  const w=630,h=182,l=42,r=12,top=18,bottom=33,pw=w-l-r,ph=h-top-bottom;
  const max=Math.max(...data.map(x=>Number(x.mass_kg)||0),1)*1.15;
  const points=data.map((d,i)=>[l+(data.length===1?pw/2:i*pw/(data.length-1)),top+ph*(1-(Number(d.mass_kg)||0)/max)]);
  const path=points.map((p,i)=>(i?'L':'M')+p.map(x=>x.toFixed(2)).join(' ')).join(' ');
  const area=path+`L${points.at(-1)[0]} ${top+ph}L${points[0][0]} ${top+ph}Z`;
  const grid=[0,.5,1].map(f=>`<line class="gridline" x1="${l}" x2="${w-r}" y1="${top+ph*f}" y2="${top+ph*f}"/><text x="${l-10}" y="${top+ph*f+3}" text-anchor="end">${e(n(max*(1-f),0))}</text>`).join('');
  const labels=data.map((d,i)=>`<text x="${points[i][0]}" y="${h-8}" text-anchor="middle">${e(new Date(d.label+'-01T12:00:00').toLocaleDateString('ru-RU',{month:'short'}))}</text>`).join('');
  return `<div class="chart-legend">Известная масса, кг</div><div class="chart-scroll" tabindex="0" aria-label="График динамики; на узком экране доступна горизонтальная прокрутка"><svg class="chart line-chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="Динамика массы отходов по месяцам"><defs><linearGradient id="areaGradient" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stop-color="#c86442" stop-opacity=".3"/><stop offset="100%" stop-color="#f4e6ce" stop-opacity=".05"/></linearGradient></defs>${grid}<path d="${area}" fill="url(#areaGradient)"/><path d="${path}" fill="none" stroke="#b7472a" stroke-width="2.5" stroke-linecap="round"/>${points.map((p,i)=>`<circle cx="${p[0]}" cy="${p[1]}" r="4" fill="#b7472a" stroke="#fbf7ef" stroke-width="2"><title>${e(monthLabel(data[i].label))}: ${e(qty(data[i].mass_kg))} кг</title></circle>`).join('')}${labels}</svg></div><details class="chart-data"><summary>Значения графика по месяцам</summary><div class="table-wrap"><table><thead><tr><th>Месяц</th><th class="numeric">Известная масса, кг</th></tr></thead><tbody>${data.map(d=>`<tr><td>${e(monthLabel(d.label))}</td><td class="numeric">${qty(d.mass_kg)}</td></tr>`).join('')}</tbody></table></div></details>`;
}
function donutChart(data){
  const sorted=(data||[]).filter(x=>Number(x.mass_kg)>0).sort((a,b)=>b.mass_kg-a.mass_kg);
  const total=sorted.reduce((s,x)=>s+Number(x.mass_kg),0);if(!total)return empty('Структура пока не определена','Выберите период с принятыми данными.');
  const chart=sorted.slice(0,4);if(sorted.length>4)chart.push({name:'Другие виды',mass_kg:sorted.slice(4).reduce((s,x)=>s+Number(x.mass_kg),0)});
  let offset=0;const circle=2*Math.PI*62;
  const segments=chart.map((d,i)=>{const frac=Number(d.mass_kg)/total;const result=`<circle cx="80" cy="80" r="62" fill="none" stroke="${palette[i]}" stroke-width="19" stroke-dasharray="${Math.max(0,frac*circle-2)} ${circle}" stroke-dashoffset="${-offset}"><title>${e(d.name)}: ${e(qty(d.mass_kg))} кг</title></circle>`;offset+=frac*circle;return result;}).join('');
  return `<div class="donut-layout"><div class="donut-wrap"><svg viewBox="0 0 160 160" role="img" aria-label="Структура массы по видам отходов"><circle cx="80" cy="80" r="62" fill="none" stroke="#e9dfca" stroke-width="19"/>${segments}</svg><div class="donut-center"><strong>${e(n(total,0))}</strong><span>килограммов</span></div></div><div class="legend">${chart.map((d,i)=>`<div class="legend-item"><span class="legend-dot" style="background:${palette[i]}"></span><span class="legend-name" title="${e(d.name)}">${e(d.name)}</span><strong>${e(n(Number(d.mass_kg)/total*100,1))}%</strong></div>`).join('')}</div></div>`;
}
function bars(data){
  if(!data?.length)return empty('Нет данных для сравнения','Сравнение появится после принятия отчётов.');
  const sorted=[...data].sort((a,b)=>b.mass_kg-a.mass_kg);const max=Math.max(...sorted.map(x=>Number(x.mass_kg)||0),1);
  return `<div class="hbars">${sorted.map(d=>`<div class="hbar"><div class="hbar-label"><span>${e(d.name)}</span><strong>${e(qty(d.mass_kg))} кг</strong></div><div class="hbar-track"><div class="hbar-fill" style="width:${Math.max(0,Number(d.mass_kg)/max*100)}%"></div></div></div>`).join('')}</div>`;
}
function campusHero(data,delta,missing){
  const organization=S.filters.organization_id?orgName(S.filters.organization_id):isReviewer()?'Все организации':S.user.organization_name||'Моя организация';
  const period=`${isoDate(S.filters.from)} — ${isoDate(S.filters.to)}`;
  const current=items(missing).find(report=>String(report.organization_id)===String(S.user.organization_id));
  const canAdd=!!current&&[null,'missing','draft','returned'].includes(current.status);
  const primary=isReviewer()?`<a class="btn" href="#review" data-route="review">Проверить отчёты${icon('arrow')}</a>`:canAdd?button('Добавить взвешивание','new-entry',{icon:'plus'}):`<a class="btn" href="#reports" data-route="reports">Открыть мои отчёты${icon('arrow')}</a>`;
  const nextStep=isReviewer()?'Проверьте отчёты организаций. Ниже — сводка уже принятых данных.':canAdd?'Добавьте взвешивание в отчёт текущего месяца.':`Текущий месяц: ${statusLabels[current?.status]||'Принято'}. Статусы и записи доступны в ваших отчётах.`;
  return `<section class="campus-hero" aria-labelledby="campus-heading"><div class="hero-copy"><div class="hero-kicker">Журнал кампуса</div><h1 class="hero-title" id="campus-heading">Кампус<br>в цифрах</h1><p>${e(nextStep)}</p><div class="hero-meta"><span><small>Организация</small><strong>${e(organization)}</strong></span><span><small>Период сводки</small><strong>${e(period)}</strong></span></div><div class="hero-actions">${primary}</div></div><aside class="hero-metric weighing-ticket"><div class="ticket-head"><span>Сводка принятых записей</span><strong>На ${e(isoDate(S.meta.today))}</strong></div><svg class="ticket-plate" width="160" height="100" viewBox="0 0 160 100" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true" focusable="false"><g class="ticket-tray"><ellipse cx="80" cy="27" rx="55" ry="14"/><ellipse cx="80" cy="27" rx="42" ry="8"/><path d="M25 27c7 18 18 22 55 22s48-4 55-22"/></g><path d="M65 49v10h30V49M37 60h86l12 29H25l12-29Z"/><rect x="61" y="67" width="38" height="14" rx="2"/><path d="M71 74h18M42 94h76"/></svg><div class="hero-metric-label">Известная масса отходов</div><div class="hero-number">${e(qty(data.totals?.known_mass_kg))}</div><span class="hero-unit">кг / выбранный период</span><div class="ticket-records"><span>Записей в расчёте</span><strong>${e(n(data.totals?.records,0))}</strong></div><p class="hero-metric-note">${e(delta)}</p></aside></section>`;
}
async function overviewPage(){
  const [d,missing]=await Promise.all([api('/dashboard?'+qs(S.filters)),api('/missing-reports?'+qs({month:S.meta.current_month,organization_id:S.filters.organization_id}))]);
  const t=d.totals||{},eco=d.ecology||{},cmp=d.comparison||{};
  const share=Number(t.known_mass_kg)>0?Number(t.recyclable_mass_kg||0)/Number(t.known_mass_kg)*100:null;
  const delta=cmp.change_percent===null||cmp.change_percent===undefined?'Нет базы для сравнения':`${Number(cmp.change_percent)>0?'+':''}${n(cmp.change_percent,1)}% к предыдущему периоду`;
  return campusHero(d,delta,missing)+`<details class="overview-controls"><summary>${isReviewer()?'Период, организация и выгрузка':'Период и выгрузка'}</summary><div class="overview-controls-body">${filterBar()}<div class="overview-tools-actions">${button('Скачать Excel','export',{icon:'download',class:'secondary'})}${isReviewer()?button('Открыть реестр','go-registry',{class:'ghost'}):button('Как внести данные','open-entry-help',{class:'ghost',icon:'info'})}</div></div></details>${Number(t.unconverted_l)>0?`<div class="notice warning section-gap">Есть ${e(qty(t.unconverted_l))} л без коэффициента плотности. Они не включены в общую массу и экологический расчёт.</div>`:''}<div class="grid-two overview-grid"><section class="panel overview-trend"><div class="panel-header"><div><span class="panel-index">01 / По времени</span><h2>Динамика отходов</h2><p>Известная масса по месяцам</p></div><span class="chart-tag">кг / месяц</span></div><div class="panel-body">${lineChart(d.monthly)}</div><div class="panel-foot">${icon('info')}В расчёте только принятые отчёты</div></section><section class="panel overview-structure"><div class="panel-header"><div><span class="panel-index">02 / По видам</span><h2>Структура отходов</h2><p>Распределение известной массы</p></div></div><div class="panel-body">${donutChart(d.by_type)}</div></section></div><div class="grid-two overview-grid"><section class="panel overview-organizations"><div class="panel-header"><div><span class="panel-index">03 / По подразделениям</span><h2>Организации кампуса</h2><p>Масса отходов за выбранный период</p></div></div><div class="panel-body">${bars(d.by_organization)}</div></section><details class="panel overview-attention"><summary class="attention-summary"><span><span class="panel-index">04 / Текущий месяц</span><strong>Ожидают принятия</strong><small>${e(monthLabel(S.meta.current_month))}</small></span><span class="pill amber">${items(missing).length}</span></summary><div class="panel-body"><div class="mini-list">${items(missing).slice(0,5).map(x=>`<div class="mini-row"><div class="mini-row-icon">${icon('building')}</div><div class="mini-row-info"><strong>${e(x.organization_name)}</strong><small>${e(statusLabels[x.status]||'Отчёт пока не создан')}</small></div>${x.report_id?button('Открыть','open-report',{id:x.report_id,class:'ghost small'}):'<span class="pill gray">Ожидается</span>'}</div>`).join('')||`<div class="empty"><h3>Все отчёты приняты</h3><p>За этот месяц нет организаций без принятого отчёта.</p></div>`}</div></div></details></div><details class="overview-more"><summary><strong>Дополнительная аналитика</strong><small>Причины · порции · CO₂</small></summary><div class="overview-more-body"><div class="cards overview-ledger compact-ledger">${stat('Пригодно к переработке',share===null?'—':n(share,1),'%',`${qty(t.recyclable_mass_kg||0)} кг · категория «Да»`,'recycle')}${stat('Разница выбросов',qty(eco.difference_kg),'кг CO₂-экв.','Оценка по справочным коэффициентам','leaf',true)}</div>${measurementInsights(d)}<div class="overview-tools-actions">${button('Разобрать данные с агентом','go-agent',{class:'ghost',icon:'agent'})}</div><p class="footnote">Исходные количества: ${e(qty(t.raw_kg||0))} кг и ${e(qty(t.volume_l||0))} л. Объём масла переведён в массу только по указанному в справочнике допущению. Частично перерабатываемые отходы: ${e(qty(t.partial_mass_kg||0))} кг.</p></div></details>`;
}

function reportFilters(){
  return `<form id="report-filter-form" class="period-controls"><label>Месяц<input type="month" name="period" value="${e(S.reportPeriod)}" max="${e(S.meta.current_month)}"></label><label>Статус<select name="status">${option('','Все статусы',S.reportStatus)}${Object.entries(statusLabels).filter(([k])=>k!=='missing').map(([k,v])=>option(k,v,S.reportStatus)).join('')}</select></label>${isReviewer()?`<label>Организация<select name="organization_id">${option('','Все организации',S.reportOrg)}${S.organizations.map(o=>option(o.id,o.short_name||o.name,S.reportOrg)).join('')}</select></label>`:''}<button class="btn secondary" type="submit">${icon('search')}Показать</button>${button('Все месяцы','all-report-periods',{class:'ghost'})}</form>`;
}
async function reportsPage(){
  if(S.reportId){
    const requestToken=S.loadToken,requestEpoch=S.authEpoch,reportId=S.reportId;
    const r=await api('/reports/'+encodeURIComponent(reportId));
    const types=await api('/waste-types?'+qs({organization_id:r.organization_id}));
    if(requestToken!==S.loadToken||requestEpoch!==S.authEpoch||reportId!==S.reportId)return '';
    S.report=r;S.reportTypes=items(types);return reportDetail(r);
  }
  S.report=null;
  const q={period:S.reportPeriod,status:S.reportStatus,organization_id:S.reportOrg,page:S.reportsPage,page_size:25};
  const data=await api('/reports?'+qs(q));
  const title=S.route==='review'?'Проверка отчётов':isReviewer()?'Отчёты организаций':'Мои отчёты';
  const rows=items(data),mine=!isReviewer(),filtered=Boolean(S.reportPeriod||S.reportStatus||S.reportOrg);
  const working=mine?rows.filter(isEditable):[],other=mine?rows.filter(r=>!isEditable(r)):rows;
  const period=S.reportPeriod?monthLabel(S.reportPeriod):'Все месяцы';
  const filters=[period,S.reportStatus&&statusLabels[S.reportStatus],S.reportOrg&&orgName(S.reportOrg)].filter(Boolean).join(' · ');
  const controls=mine?button('Новый отчёт','new-report',{icon:'plus',class:working.length?'secondary':''}):'';
  return heading(title,mine?'Откройте черновик, чтобы записать отходы или порции.':'Откройте отчёт организации, чтобы посмотреть записи и принять решение.',controls,'Журнал кампуса')+
    `<details class="report-search"><summary>${icon('search')}Фильтры <small>${e(filters)}</small></summary>${reportFilters()}</details>`+
    (working.length?reportListGroup('Можно заполнить',working,true):'')+
    (other.length?reportListGroup(mine?'Отправленные отчёты':'Отчёты за период',other,false):'')+
    (!rows.length?empty('Отчётов не найдено',filtered?'Попробуйте другой месяц или снимите фильтры.':mine?'Создайте отчёт за месяц, чтобы внести первое взвешивание.':'Здесь появятся отчёты организаций.',filtered?button('Снять фильтры','clear-report-filters',{class:'secondary'}):''):'')+
    (data.total>data.page_size?pagination(data,S.reportsPage,'reports-page'):'')+
    (mine?`<p class="report-list-help">${button('Как внести данные','open-entry-help',{class:'ghost small',icon:'info'})}</p>`:'');
}
function reportListGroup(title,rows,working){
  return `<section class="report-stack${working?' report-stack-working':''}"><h2>${e(title)}</h2><ul class="report-slips">${rows.map(r=>{
    const label=isReviewer()?r.organization_name:monthLabel(r.period);
    const context=isReviewer()?monthLabel(r.period):'';
    const detail=FoodSaveRoutes.format(isReviewer()?'review':'reports',r.id);
    const metrics=[context,`Записей: ${n(r.entry_count,0)}`,`Масса: ${qty(r.total_kg)} кг`,Number(r.total_l)>0&&`Объём: ${qty(r.total_l)} л`].filter(Boolean).join(' · ');
    return `<li><a class="report-slip" href="${e(detail)}"><span class="slip-icon" aria-hidden="true">${icon(working?'edit':'clipboard')}</span><span class="slip-copy"><strong>${e(label)}</strong><small>${e(metrics)}</small>${r.last_comment?`<small class="slip-comment">Есть комментарий проверяющего</small>`:''}</span>${badge(r.status)}<span class="slip-arrow" aria-hidden="true">${icon('arrow')}</span></a></li>`;
  }).join('')}</ul></section>`;
}
function pagination(data,page,action){const size=Number(data.page_size)||25,total=Number(data.total)||0;return `<div class="pagination"><span>Показано ${total?((page-1)*size+1):0}–${Math.min(page*size,total)} из ${total}</span><div class="actions">${button('Назад',action,{value:page-1,class:'secondary small',disabled:page<=1})}<span>${page} / ${Math.max(1,Math.ceil(total/size))}</span>${button('Далее',action,{value:page+1,class:'secondary small',disabled:page*size>=total})}</div></div>`;}
function recordTypeOptions(selected=''){return (S.reportTypes||S.wasteTypes).filter(t=>t.active!==false&&t.active!==0||String(t.id)===String(selected)).map(t=>option(t.id,t.name,selected)).join('');}
function activeMethodId(type){
  const active=S.methods.filter(m=>m.active!==false&&m.active!==0);
  return (active.find(m=>String(m.id)===String(type?.default_method_id))||active.find(m=>m.code==='TBO')||active[0])?.id||'';
}
function methodOptions(selected=''){return S.methods.filter(m=>m.active!==false&&m.active!==0||String(m.id)===String(selected)).map(m=>option(m.id,m.name+(m.active===false||m.active===0?' (неактивен — выберите другой)':''),selected)).join('');}
function reasonLabel(code){return (S.meta.waste_reasons||[]).find(x=>x.code===code)?.label||(code&&code!=='unspecified'?code:'Не указана');}
function entryContext(entry){return `<small>Причина: ${e(reasonLabel(entry.reason_code))}</small>${entry.note?`<details class="entry-note"><summary>Примечание</summary><p class="preline">${e(entry.note)}</p></details>`:''}`;}
function entryExtraFields(entry={},edit=false){
  const prefix=edit?'edit-entry':'entry';
  return `<details class="entry-extra"${entry.note?' open':''}><summary>Добавить примечание · необязательно</summary><div class="form-grid"><label class="full-width" for="${prefix}-note">Примечание к измерению<textarea id="${prefix}-note" name="note" rows="2" maxlength="1000" placeholder="Например, отменили заказ или проверяют вес">${e(entry.note||'')}</textarea></label></div></details>`;
}
function entryFields(entry={},edit=false){
  const types=S.reportTypes||S.wasteTypes;
  const first=types.find(t=>String(t.id)===String(entry.waste_type_id))||types.find(t=>t.active!==false&&t.active!==0);
  const date=entry.date||((S.report.period===S.meta.current_month)?S.meta.today:S.report.entries?.at(-1)?.date||S.report.period+'-01');
  const method=entry.method_id||activeMethodId(first);
  const maxDate=monthEnd(S.report.period)<S.meta.today?monthEnd(S.report.period):S.meta.today;
  const reasons=S.meta.waste_reasons?.length?S.meta.waste_reasons:[{code:'unspecified',label:'Не указана'}],prefix=edit?'edit-entry':'entry';
  return `<div class="${edit?'form-grid':'entry-grid'}"><label class="date-field" for="${prefix}-date">Дата<input id="${prefix}-date" type="date" name="date" required value="${e(date)}" min="${e(S.report.period)}-01" max="${e(maxDate)}"></label><label class="waste-field" for="${prefix}-waste-type">Вид отходов<div class="field-row"><select id="${prefix}-waste-type" name="waste_type_id" required data-entry-type>${recordTypeOptions(first?.id)}</select>${!edit?`<button type="button" class="btn secondary icon-only" data-action="new-type" title="Добавить вид отходов" aria-label="Добавить вид отходов">${icon('plus')}</button>`:''}</div></label><label class="quantity-field" for="${prefix}-quantity">Количество<input id="${prefix}-quantity" type="number" name="quantity" required min="0.001" max="10000" step="0.001" inputmode="decimal" placeholder="0,000" value="${e(entry.quantity??'')}"><span class="quantity-unit" data-entry-unit>${unit(first?.unit)}</span></label><label class="method-field" for="${prefix}-method">Способ обращения<select id="${prefix}-method" name="method_id" required>${methodOptions(method)}</select></label><label class="reason-field" for="${prefix}-reason">Причина<select id="${prefix}-reason" name="reason_code" aria-describedby="${prefix}-reason-help">${reasons.map(x=>option(x.code,x.label,entry.reason_code||'unspecified')).join('')}</select><small id="${prefix}-reason-help" class="form-help">Если причина неизвестна, оставьте «Не указана».</small></label></div>${entryExtraFields(entry,edit)}`;
}
function intensityContent(metric={}){
  const hasRate=value=>value!==null&&value!==undefined&&Number.isFinite(Number(value));
  const total=Number(metric.total_days)||0,covered=Number(metric.covered_days)||0;
  const complete=metric.complete&&hasRate(metric.kg_per_100_portions);
  const state=complete?'За все дни со взвешиваниями':!total?'Нет дней со взвешиваниями':Number(metric.missing_days)>0&&!covered?'Нет данных о порциях':'Неполные данные для расчёта';
  return `<div class="intensity-value"><strong>${complete?qty(metric.kg_per_100_portions):'—'}</strong><span>кг на 100 порций</span></div><p class="intensity-state">${e(state)}</p>${!complete&&hasRate(metric.covered_kg_per_100_portions)?`<p class="intensity-partial"><strong>${qty(metric.covered_kg_per_100_portions)} кг на 100 порций</strong> · по ${n(covered,0)} из ${n(total,0)} дней со взвешиваниями</p>`:''}<p class="methodology">${e(metric.message||'Укажите число обслуженных порций за дни со взвешиваниями; неизвестные значения не заменяются нулём.')}</p>${total?`<p class="form-help">Покрытие: ${n(covered,0)} из ${n(total,0)} дней со взвешиваниями. В расчёте: ${qty(metric.covered_mass_kg)} кг и ${n(metric.portions,0)} порций за покрытые дни.</p>`:''}`;
}
function measurementInsights(d){
  const reasons=d.by_reason||[],metric=d.intensity||{};
  return `<div class="grid-equal section-gap"><section class="panel"><div class="panel-header"><div><h2>Отходы на 100 порций</h2><p>Число порций вводят сотрудники; расчёт учитывает полноту данных</p></div>${icon('weight')}</div><div class="panel-body">${intensityContent(metric)}${(metric.by_organization||[]).length>1?`<details><summary>По организациям</summary><div class="intensity-orgs">${metric.by_organization.map(x=>`<div><h3>${e(x.organization_name)}</h3>${intensityContent(x)}</div>`).join('')}</div></details>`:''}</div></section><section class="panel"><div class="panel-header"><div><h2>Причины образования отходов</h2><p>Причины из записей сотрудников, включая неуказанные</p></div>${icon('list')}</div>${reasons.length?`<div class="table-wrap"><table><thead><tr><th>Причина</th><th class="numeric">Вес, кг</th><th class="numeric">Объём, л</th><th class="numeric">Записей</th></tr></thead><tbody>${reasons.map(x=>`<tr><td class="table-name">${e(x.label||reasonLabel(x.code))}</td><td class="numeric">${qty(x.raw_kg)}</td><td class="numeric">${qty(x.volume_l)}</td><td class="numeric">${n(x.records,0)}</td></tr>`).join('')}</tbody></table></div>`:empty('Нет принятых измерений','Причины появятся после принятия отчётов.')}</section></div>`;
}
function serviceDaysPanel(r){
  const editable=isEditable(r),days=r.service_days||[],date=r.period===S.meta.current_month?S.meta.today:r.entries?.at(-1)?.date||r.period+'-01';
  const maxDate=monthEnd(r.period)<S.meta.today?monthEnd(r.period):S.meta.today;
  const saved=days.find(day=>day.date===date),metric=r.totals?.intensity||{};
  const hasRate=value=>value!==null&&value!==undefined&&Number.isFinite(Number(value));
  const complete=metric.complete&&hasRate(metric.kg_per_100_portions);
  return `<section class="panel report-portions-card${editable?'':' section-gap'}" aria-labelledby="service-day-title"><div class="panel-header">${editable?'<span class="input-step" aria-hidden="true">2</span>':''}<div><h2 id="service-day-title">Порции за день</h2><p>Один итог за дату для всех взвешиваний</p></div></div><div class="panel-body">${editable?`<form id="service-day-form" class="service-day-form" aria-labelledby="service-day-title"><div class="form-grid"><label for="service-day-date">Дата<input id="service-day-date" type="date" name="date" required min="${e(r.period)}-01" max="${e(maxDate)}" value="${e(date)}"></label><label for="service-day-portions">Обслужено порций<input id="service-day-portions" type="number" name="portions" required min="0" max="100000" step="1" inputmode="numeric" value="${e(saved?.portions??'')}" placeholder="Укажите целое число" aria-describedby="service-day-help"></label></div><p id="service-day-help" class="form-help">0 — в этот день не обслуживали. Если число неизвестно, не сохраняйте пустое поле. Сохранение той же даты обновит её итог.</p><div class="form-actions"><button type="submit" class="btn secondary">Сохранить порции</button></div><div id="service-day-error"></div></form>`:''}<div class="report-portions-rate"><span>Отходы на 100 порций</span><div class="intensity-value"><strong>${complete?qty(metric.kg_per_100_portions):'—'}</strong><span>кг</span></div>${!complete&&hasRate(metric.covered_kg_per_100_portions)?`<p class="intensity-partial">${qty(metric.covered_kg_per_100_portions)} кг по ${n(metric.covered_days,0)} из ${n(metric.total_days,0)} дней со взвешиваниями</p>`:''}<p class="form-help">${e(metric.message||'Для расчёта нужны взвешивания и порции за одну дату.')}</p>${Number(metric.total_days)>0?`<details><summary>Подробности расчёта</summary><p class="methodology">Учтено ${n(metric.covered_days,0)} из ${n(metric.total_days,0)} дней со взвешиваниями: ${qty(metric.covered_mass_kg)} кг и ${n(metric.portions,0)} порций. Дни без порций или с неизвестной массой не подменяются нулём.</p></details>`:''}</div>${days.length?`<details class="report-portions-list"${editable?'':' open'}><summary>Сохранённые дни · ${days.length}</summary><div class="table-wrap"><table><thead><tr><th>Дата</th><th class="numeric">Порций</th>${editable?'<th>Действия</th>':''}</tr></thead><tbody>${days.map(x=>`<tr><td class="nowrap">${e(isoDate(x.date))}</td><td class="numeric">${n(x.portions,0)}${x.portions===0?'<small>Не обслуживали</small>':''}</td>${editable?`<td><div class="actions">${button('Изменить','edit-service-day',{value:x.date,class:'ghost small'})}${button('Удалить','delete-service-day',{value:x.date,class:'ghost small'})}</div></td>`:''}</tr>`).join('')}</tbody></table></div></details>`:'<p class="form-help section-gap">Сохранённых порций пока нет.</p>'}</div></section>`;
}
function reportTypeTotals(rows,caption){
  return `<div class="table-wrap"><table class="type-totals"><caption class="sr-only">${e(caption)}</caption><thead><tr><th scope="col">Вид отходов</th><th scope="col" class="numeric">Вес, кг</th><th scope="col" class="numeric">Объём, л</th></tr></thead><tbody>${rows.map(x=>`<tr><th scope="row">${e(x.name)}</th><td class="numeric">${qty(x.kg)}</td><td class="numeric">${qty(x.l)}</td></tr>`).join('')}</tbody></table></div>`;
}
function reportTotalsDetails(t,period){
  if(!(t.by_type||[]).length&&!(t.daily||[]).length)return '';
  return `<div class="report-totals"><h3>Итоги по видам отходов</h3><p class="form-help">Исходный вес и объём учитываются отдельно, без сложения килограммов с литрами.</p>${(t.by_type||[]).length?`<details open><summary>За месяц · ${e(monthLabel(period))}</summary>${reportTypeTotals(t.by_type,'Итоги за месяц по видам отходов')}</details>`:''}${(t.daily||[]).length?`<details><summary>По дням (${t.daily.length})</summary><div class="daily-totals">${t.daily.map(x=>`<details><summary><span>${e(isoDate(x.date))}</span><span class="daily-total-value">Всего: ${qty(x.kg)} кг · ${qty(x.l)} л</span></summary>${reportTypeTotals(x.by_type||[],`Итоги за ${isoDate(x.date)} по видам отходов`)}</details>`).join('')}</div></details>`:''}</div>`;
}
function reportEntryGuide(r){
  if(!S.reportGuide)return `<div class="guide-strip"><span>Как связаны взвешивания и порции?</span>${button('Пример расчёта','show-entry-guide',{class:'ghost small',icon:'info'})}</div>`;
  const editable=isEditable(r);
  const explanation=r.status==='accepted'?'Принятый отчёт доступен только для чтения. Для нового ввода откройте черновик другого месяца.':isReviewer()?'Причины и порции вводит сотрудник организации в черновике или после возврата отчёта.':'Этот отчёт уже отправлен. Проверяющий должен вернуть его на доработку, прежде чем вы сможете изменить данные.';
  return `<section class="workflow-guide report-example section-gap" aria-labelledby="report-example-title"><div class="guide-header"><h2 id="report-example-title">Пример расчёта</h2>${button('Скрыть','hide-entry-guide',{class:'ghost small'})}</div>${!editable?`<p class="guide-callout">${e(explanation)}</p>`:''}<p><strong>3 кг и 200 порций за один день = 1,5 кг на 100 порций.</strong></p><p class="report-input-note">Можно сохранить несколько взвешиваний с разными причинами. Порции укажите один раз за ту же дату. Если порции отсутствуют или масса неизвестна, общий показатель останется неполным.</p>${editable?`<div class="guide-actions">${button('К взвешиванию','guide-weighing',{class:'secondary small'})}${button('К причине','guide-reason',{class:'ghost small'})}${button('К порциям','guide-portions',{class:'secondary small'})}</div>`:''}</section>`;
}
function focusGuideTarget(selector,fieldName){
  const target=$(selector);if(!target)return;
  document.querySelectorAll('.guide-target-active').forEach(node=>node.classList.remove('guide-target-active'));
  if(target instanceof HTMLDetailsElement)target.open=true;
  target.classList.add('guide-target-active');
  target.scrollIntoView({block:'center',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});
  const field=fieldName?target.querySelector(`[name="${fieldName}"]`):null;
  field?.focus({preventScroll:true});
}
function reportInputPanels(r){
  if(!isEditable(r))return '';
  const entries=r.entries||[];
  return `<nav class="input-jumps" aria-label="Перейти к форме">${button('Взвешивание','guide-weighing',{class:'secondary',icon:'weight'})}${button('Порции за день','guide-portions',{class:'secondary',icon:'calendar'})}</nav><div class="report-inputs"><section class="panel report-input-card" aria-labelledby="entry-form-title"><div class="panel-header"><span class="input-step" aria-hidden="true">1</span><div><h2 id="entry-form-title">Добавить взвешивание</h2><p>Каждый замер сохраняется отдельной записью</p></div></div><form id="entry-form" class="entry-form" aria-labelledby="entry-form-title">${entryFields()}<div class="entry-toolbar"><p class="report-input-note">Ответственный: ${e(S.user.full_name)}. Черновик формы сохраняется.</p><div class="actions">${entries.length?button('Повторить последнее','repeat-entry',{class:'ghost small',icon:'refresh'}):''}<button type="submit" class="btn">${icon('plus')}Добавить взвешивание</button></div></div><div id="entry-error"></div></form></section>${serviceDaysPanel(r)}</div>`;
}
function reportDetail(r){
  const editable=isEditable(r),t=r.totals||{},entries=r.entries||[];
  let action='';
  if(editable)action=button('Отправить на проверку','report-submit',{class:'secondary',icon:'send',disabled:!entries.length});
  if(isReviewer()&&r.status==='submitted')action=button('Начать проверку','report-start-review',{icon:'shield'});
  if(isReviewer()&&r.status==='in_review')action=button('Вернуть на доработку','report-return',{class:'secondary',icon:'back'})+button('Принять отчёт','report-accept',{icon:'check'});
  return `<button class="text-link report-back" data-action="back-reports">${icon('back')}К списку отчётов</button>`+heading(monthLabel(r.period),r.organization_name,action,'Месячный отчёт')+
    `<div class="report-meta">${badge(r.status)}<span>Отчёт № ${e(r.id)}</span><span>Версия ${e(r.revision)}</span>${r.status==='accepted'?`<span>${icon('lock')} Принятые данные защищены от изменений</span>`:''}</div>${r.last_comment?`<div class="notice ${r.status==='returned'?'warning':'info'} section-gap"><strong>Комментарий проверяющего</strong><p class="preline">${e(r.last_comment)}</p></div>`:''}${reportInputPanels(r)}${reportEntryGuide(r)}
    <section class="panel section-gap"><div class="panel-header"><div><h2>Сохранённые взвешивания</h2><p>${editable?'До отправки записи можно исправить или удалить.':'Записи доступны для просмотра.'}</p></div></div><div class="report-summary"><div>Известная масса<strong>${qty(t.known_mass_kg??r.total_kg??0)} <small>кг</small></strong></div><div>Исходный вес<strong>${qty(t.raw_kg??r.total_kg??0)} <small>кг</small></strong></div><div>Исходный объём<strong>${qty(t.volume_l??r.total_l??0)} <small>л</small></strong></div><div>Количество записей<strong>${n(t.records??entries.length,0)}</strong></div></div>${entries.length?`<div class="table-wrap"><table><thead><tr><th>Дата</th><th>Вид отходов</th><th class="numeric">Количество</th><th>Способ</th><th>Ответственный</th>${editable?'<th></th>':''}</tr></thead><tbody>${entries.map(x=>`<tr><td class="nowrap">${e(isoDate(x.date))}</td><td class="table-name"><strong>${e(x.waste_name)}</strong>${entryContext(x)}</td><td class="numeric nowrap">${qty(x.quantity)} ${unit(x.unit)}</td><td class="table-name">${e(x.method_name)}</td><td>${e(x.responsible_name)}</td>${editable?`<td><div class="actions"><button type="button" class="btn ghost icon-only" data-action="edit-entry" data-id="${e(x.id)}" title="Изменить" aria-label="Изменить запись">${icon('edit')}</button><button type="button" class="btn ghost icon-only" data-action="delete-entry" data-id="${e(x.id)}" title="Удалить" aria-label="Удалить запись">${icon('trash')}</button></div></td>`:''}</tr>`).join('')}</tbody></table></div>`:empty('Сохранённых взвешиваний пока нет',editable?'Добавьте первое измерение в форме выше.':'В этом отчёте нет измерений.')}<div class="panel-body">${reportTotalsDetails(t,r.period)}</div></section>${editable?'':serviceDaysPanel(r)}
    <section class="panel section-gap"><div class="panel-header"><div><h2>История отчёта</h2><p>Действия и решения сохраняются вместе с автором и временем.</p></div>${icon('clock')}</div><div class="panel-body">${renderHistory(r.history||[])}</div></section>`;
}
function renderHistory(history){
  if(!history.length)return '<p class="muted small">Изменения ещё не зафиксированы.</p>';
  const labels={'service_day.upserted':'Сохранено число порций','service_day.deleted':'Удалено число порций','create':'Создан отчёт','created':'Создан отчёт','report.created':'Создан отчёт','entry.created':'Добавлено взвешивание','entry.updated':'Изменено взвешивание','entry.deleted':'Удалено взвешивание','submit':'Отправлено на проверку','start-review':'Начата проверка','return':'Возвращено на доработку','accept':'Отчёт принят'};
  return `<div class="history">${[...history].reverse().map(x=>`<div class="history-item"><div class="history-mark"></div><div class="history-content"><strong>${e(labels[x.action]||statusLabels[x.to_status]||x.action||'Изменение')} · ${e(x.actor_name||'Система')}</strong><time>${e(timeLabel(x.timestamp))}</time>${x.comment?`<p>${e(x.comment)}</p>`:''}</div></div>`).join('')}</div>`;
}

async function registryPage(){
  const data=await api('/registry?'+qs({...S.filters,page:S.registryPage,page_size:30}));
  return heading('Единый реестр','Проверенные измерения всех доступных организаций.',button('Скачать Excel','export',{class:'secondary',icon:'download'}),'Принятые данные')+filterBar(true)+`<section class="panel"><div class="panel-header"><h2>Принятые измерения</h2><span class="muted small">${n(data.total,0)} записей</span></div>${items(data).length?`<div class="table-wrap"><table><thead><tr><th>Дата</th><th>Организация</th><th>Вид отходов</th><th class="numeric">Количество</th><th>Способ</th><th>Отчёт</th></tr></thead><tbody>${items(data).map(x=>`<tr><td class="nowrap">${e(isoDate(x.date))}</td><td class="table-name">${e(x.organization_name)}</td><td class="table-name"><strong>${e(x.waste_name)}</strong>${entryContext(x)}</td><td class="numeric nowrap">${qty(x.quantity)} ${unit(x.unit)}</td><td class="table-name">${e(x.method_name)}</td><td>${button('#'+x.report_id,'open-report',{id:x.report_id,class:'ghost small'})}</td></tr>`).join('')}</tbody></table></div>${pagination(data,S.registryPage,'registry-page')}`:empty('Принятых измерений пока нет','Черновики и отчёты на проверке появятся в реестре после принятия.')}</section><p class="footnote">Выбранные фильтры применяются и к выгрузке. Килограммы и литры сохраняются отдельными величинами.</p>`;
}

function agentPage(){return heading('Агент бережного кампуса','Спросите о данных, отклонениях и расчётах — получите ответ с основаниями.','','Локальный интеллект')+filterBar()+`<div class="agent-layout"><section class="panel chat-panel"><div class="chat-header"><div class="agent-avatar">${icon('agent')}</div><div><h2>FoodSave Analyst</h2><p>Доступны только данные вашей роли · платные API не используются</p></div><span class="pill green" style="margin-left:auto">Локально</span></div><div class="chat-thread" id="chat-thread" role="log" aria-live="polite">${chatMessages()}</div><form id="agent-form" class="chat-composer"><div class="chat-input-row"><label class="sr-only" for="agent-message">Вопрос агенту</label><textarea id="agent-message" name="message" rows="1" placeholder="Например: где вырос объём отходов?" required maxlength="2000"${S.agentBusy?' disabled':''}></textarea><button class="btn icon-only" type="submit" title="Отправить вопрос" aria-label="Отправить вопрос"${S.agentBusy?' disabled':''}>${S.agentBusy?'<span class="spinner"></span>':icon('send')}</button></div><p class="form-help">Enter — отправить · Shift + Enter — новая строка. Агент не изменяет отчёты.</p></form></section><aside class="agent-sidebar"><section class="panel"><div class="panel-header"><h2>Область анализа</h2></div><div class="panel-body"><div class="agent-fact"><strong>Период</strong>${e(isoDate(S.filters.from))} — ${e(isoDate(S.filters.to))}</div><div class="agent-fact"><strong>Организация</strong>${e(S.filters.organization_id?orgName(S.filters.organization_id):isReviewer()?'Весь кампус':S.user.organization_name)}</div><div class="agent-fact"><strong>Источник</strong>Принятые отчёты и справочники системы</div></div></section><section class="panel"><div class="panel-header"><h2>Как работает агент</h2></div><div class="panel-body"><div class="tool-capability">${icon('chart')}Считает показатели и сравнивает периоды</div><div class="tool-capability">${icon('agent')}IsolationForest ищет необычные объёмы в истории</div><div class="tool-capability">${icon('leaf')}Раскрывает коэффициенты и границы CO₂-оценки</div><div class="tool-capability">${icon('shield')}Показывает статус сдачи отчётов</div><p class="footnote">ML применяется для поиска отклонений. Ответы составляются из результатов инструментов по заданным сценариям; это не универсальная языковая модель.</p></div></section></aside></div>`;}
function chatMessages(){
  if(!S.chat.length)return `<div class="welcome-agent"><div class="agent-avatar">${icon('agent')}</div><h3>Посмотрим на данные внимательнее</h3><p>Я помогу найти то, что стоит проверить, и объясню, из чего складываются показатели.</p><div class="quick-questions">${['Покажи сводку отходов','Найди аномалии в измерениях','Объясни расчёт CO₂','Кто ещё не сдал отчёт?'].map(q=>`<button class="question-btn" data-action="agent-question" data-value="${e(q)}">${e(q)}</button>`).join('')}</div></div>`;
  return S.chat.map(m=>{
    if(m.role==='user')return `<div class="message user"><div class="bubble">${e(m.text)}</div></div>`;
    const d=m.data||{};
    return `<div class="message assistant"><div class="agent-avatar">${icon('agent')}</div><div class="bubble"><div class="message-name">FOODSAVE ANALYST</div>${m.loading?`<div class="loading" style="justify-content:flex-start;padding:8px 0"><span class="spinner"></span>Выполняю расчёт по доступным данным…</div>`:`${d.scope?`<p class="message-scope">${e(isoDate(d.scope.from))} — ${e(isoDate(d.scope.to))} · ${e(d.scope.organization)}</p>`:''}${(d.tools||[]).length?`<div class="tool-list">${d.tools.map(t=>`<span class="tool-pill">${icon(t.status==='error'?'alert':'check')}${e(t.label||t.name)}</span>`).join('')}</div>`:''}<div class="preline">${e(d.answer||m.text||'')}</div>${(d.evidence||[]).length?`<div class="evidence-grid">${d.evidence.map(v=>`<div class="evidence-item"><span>${e(v.label)}</span><strong>${typeof v.value==='number'?e(qty(v.value)):e(typeof v.value==='object'?JSON.stringify(v.value):v.value)} ${e(v.unit||'')}</strong></div>`).join('')}</div>`:''}${(d.anomalies||[]).slice(0,6).map(a=>`<div class="anomaly-item"><strong>${e(a.waste_name||a.name||a.organization_name||'Необычное измерение')}</strong>${e(a.explanation||a.reason||[a.date,`${qty(a.mass_kg??a.quantity)} кг`].filter(Boolean).join(' · '))}</div>`).join('')}${(d.suggestions||[]).length?`<div class="actions section-gap">${d.suggestions.slice(0,3).map(q=>`<button class="btn secondary small" data-action="agent-question" data-value="${e(typeof q==='string'?q:q.text||q.label)}">${e(typeof q==='string'?q:q.label||q.text)}</button>`).join('')}</div>`:''}${d.disclaimer?`<p class="footnote">${e(d.disclaimer)}</p>`:''}`}</div></div>`;
  }).join('');
}
function scrollChat(){const thread=$('#chat-thread');if(thread)thread.scrollTop=thread.scrollHeight;}
async function sendAgent(message){
  if(S.agentBusy||!message.trim())return;
  const requestEpoch=S.authEpoch;
  S.chat.push({role:'user',text:message.trim()},{role:'assistant',loading:true});S.agentBusy=true;
  if(S.route==='agent'){await navigate('agent');scrollChat();}
  try{const result=await api('/agent/chat',{method:'POST',body:{message:message.trim(),...S.filters}});if(requestEpoch!==S.authEpoch)return;S.chat[S.chat.length-1]={role:'assistant',data:result};}
  catch(err){if(requestEpoch===S.authEpoch)S.chat[S.chat.length-1]={role:'assistant',text:err.message};}
  finally{if(requestEpoch===S.authEpoch){S.agentBusy=false;if(S.route==='agent'&&S.user){await navigate('agent');$('#agent-message')?.focus();}}}
}

function foodPlanText(values){
  const bad=foodPlanFields.find(f=>{
    const raw=String(values[f.name]??'').trim(),num=Number(raw);
    return raw===''||!Number.isSafeInteger(num)||num<0||num>f.max;
  });
  if(bad)return {total:'—',formula:'Для расчёта заполните три поля.',speech:'',error:`«${bad.label}»: введите целое число от 0 до ${n(bad.max,0)}.`};
  const portions=Number(values.portions_per_day),cost=Number(values.cost_per_portion),days=Number(values.work_days);
  const daily=portions*cost,total=daily*days;
  const amount=x=>n(x,0)+' ₸';
  const rules=new Intl.PluralRules('ru');
  const count=(x,one,few,many)=>n(x,0)+' '+({one,few,many}[rules.select(x)]||many);
  const p=count(portions,'порцию','порции','порций'),d=count(days,'рабочий день','рабочих дня','рабочих дней');
  return {total:amount(total),formula:`${n(portions,0)} × ${amount(cost)} × ${n(days,0)} = ${amount(total)}`,
    speech:`Допустим, столовая готовит на ${p} меньше в день. Если продукты на одну порцию стоят ${amount(cost)}, то за ${d} можно закупить продуктов на ${amount(total)} меньше.`,error:''};
}
function foodPlanPanel(){
  const v=S.foodPlan,copy=foodPlanText(v);
  return `<section id="food-plan" class="food-ticket" aria-labelledby="food-plan-title"><div class="food-ticket-copy">
    <span class="eyebrow">Учебный пример · одна столовая</span><h2 id="food-plan-title">Сколько стоят лишние порции?</h2>
    <p id="food-plan-speech">${e(copy.speech)}</p>
    <details><summary>Изменить числа примера</summary><div class="form-grid three">${foodPlanFields.map(f=>`<label>${e(f.label)}<input id="plan-${f.name}" name="${f.name}" type="number" inputmode="numeric" min="0" max="${f.max}" step="1" required value="${e(v[f.name])}"></label>`).join('')}</div>
    <p id="food-plan-error" class="form-help" role="status">${e(copy.error)}</p>${button('Вернуть исходные числа','reset-food-plan',{class:'ghost small',icon:'refresh'})}</details></div>
    <div class="food-ticket-total"><span>Возможное снижение закупок за месяц</span><output id="food-plan-total" for="plan-portions_per_day plan-cost_per_portion plan-work_days">${e(copy.total)}</output><p id="food-plan-formula">${e(copy.formula)}</p></div>
    <p class="food-ticket-note">Сумма условная: расходы снизятся, только если столовая действительно купит меньше продуктов. Данные о закупках АТУ здесь не используются.</p></section>`;
}
function refreshFoodPlan(root){
  for(const f of foodPlanFields)S.foodPlan[f.name]=root.querySelector(`[name="${f.name}"]`).value;
  const copy=foodPlanText(S.foodPlan);
  for(const [key,id] of Object.entries({total:'total',formula:'formula',speech:'speech',error:'error'}))
    root.querySelector('#food-plan-'+id).textContent=copy[key];
}
function ecologyExampleResult(massText, landfillFactor, compostFactor) {
  const kg = Number(massText);
  const valid = massText.trim() !== '' && Number.isFinite(kg) && kg >= 0 && kg <= 10000
    && kg === Math.round(kg * 1000) / 1000;
  if (!valid) {
    return '<p>Введите массу от 0 до 10 000 кг с точностью до грамма.</p><output id="eco-example-difference" for="example-mass">—</output>';
  }
  const tonnes = kg / 1000;
  const landfill = tonnes * landfillFactor;
  const compost = tonnes * compostFactor;
  const format = value => n(value, 8);
  return `<p class="eco-conversion">${format(kg)} кг ÷ 1 000 = <strong>${format(tonnes)} т</strong></p>
    <dl class="eco-comparison">
      <div><dt>Вывоз на полигон</dt><dd>${format(tonnes)} × ${format(landfillFactor)} = <strong>${format(landfill)} кг CO₂-экв.</strong></dd></div>
      <div><dt>Компостирование</dt><dd>${format(tonnes)} × ${format(compostFactor)} = <strong>${format(compost)} кг CO₂-экв.</strong></dd></div>
    </dl>
    <p class="eco-subtraction">Разница между способами<br>${format(landfill)} − ${format(compost)} = <output id="eco-example-difference" for="example-mass">${format(landfill - compost)} кг CO₂-экв.</output></p>`;
}

function ecologyExamplePanel(reference) {
  const title = '<span class="eyebrow">Учебный пример</span><h2 id="eco-example-title">Откуда берётся цифра CO₂?</h2>';
  if (!reference || ![reference.factor_tbo, reference.factor_selected].every(f => Number.isFinite(f) && f >= 0)) {
    return `<section id="ecology-example" class="panel panel-body" aria-labelledby="eco-example-title">${title}<p>Учебный расчёт недоступен. В справочнике отсутствуют коэффициенты для сравнения.</p></section>`;
  }
  const mass = S.ecologyExampleMass;
  return `<section id="ecology-example" class="food-ticket eco-ticket" aria-labelledby="eco-example-title"
      data-landfill="${e(reference.factor_tbo)}" data-compost="${e(reference.factor_selected)}">
    <div class="food-ticket-copy">${title}
      <p>Возьмём овощные очистки и сравним два способа обращения с одной и той же массой. Коэффициент показывает, сколько килограммов CO₂-эквивалента приходится на тонну отходов при каждом способе.</p>
      <label for="example-mass">Масса очисток, кг</label><input id="example-mass" name="example_mass_kg" type="number" inputmode="decimal" min="0" max="10000" step="0.001" required value="${e(mass)}">
      <details><summary>Откуда взяты коэффициенты</summary><p>${e(reference.source)}</p><p>Для материала «${e(reference.waste_name)}» коэффициент полигона равен ${n(reference.factor_tbo)} кг CO₂-экв./т. Для способа «${e(reference.method_name)}» он равен ${n(reference.factor_selected)} кг CO₂-экв./т.</p></details>
    </div>
    <div class="eco-working" aria-live="polite">${ecologyExampleResult(mass, reference.factor_tbo, reference.factor_selected)}</div>
    <p class="food-ticket-note">Масса в примере условная. В сводке за период система складывает такие разницы по принятым записям, для которых известны масса и оба коэффициента.</p></section>`;
}

async function effectPage(){
  const eco=await api('/ecology?'+qs(S.filters));
  const ecologyExample = ecologyExamplePanel(eco.teaching_example);
  const foodExample = foodPlanPanel();
  const examples = new URLSearchParams(location.search).get('view') === 'ecology'
    ? ecologyExample + foodExample : foodExample + ecologyExample;
  const fields=[['records_per_period','Записей за период','1'],['reports_per_period','Отчётов за период','1'],['periods_per_year','Периодов в году','1'],['manual_minutes_per_entry','Вручную: минут на запись','0.1'],['system_minutes_per_entry','В системе: минут на запись','0.1'],['hourly_cost','Стоимость часа, ₸','0.01'],['manual_minutes_per_report','Вручную: минут на проверку отчёта','0.1'],['system_minutes_per_report','В системе: минут на проверку отчёта','0.1'],['realizable_fraction','Доля денежной реализации, %','1'],['capex','Разовые затраты CAPEX, ₸','0.01'],['annual_opex','Дополнительный OPEX в год, ₸','0.01']];
  return heading('Экология и экономика','Расходы на продукты, время сотрудников и обращение с отходами.','','Журнал кампуса')+examples+'<h2 class="effect-subheading">Экология по принятым отчётам</h2>'+filterBar()+`<div class="cards">${stat('Базовый вариант',qty(eco.baseline_kg),'кг CO₂-экв.','Обращение с отходами по базовым факторам','cloud')}${stat('Выбранные способы',qty(eco.selected_kg),'кг CO₂-экв.','По фактическим способам в журнале','recycle')}${stat('Разница выбросов',qty(eco.difference_kg),'кг CO₂-экв.','Оценка по справочнику, не полный жизненный цикл','leaf',true)}${stat('Покрытие известной массы',n(eco.coverage_known_mass_pct,1),'%',`${n(eco.calculated_count,0)} из ${n(eco.total_count,0)} записей рассчитано`,'shield')}</div><section class="panel"><div class="panel-header"><div><h2>Что учтено в экологической оценке</h2><p>Коэффициенты в кг CO₂-экв. на тонну · масса в кг делится на 1000</p></div><span class="pill amber">Ориентировочно</span></div><div class="panel-body"><div class="notice">Разница = масса в кг ÷ 1000 × (коэффициент базового способа − коэффициент выбранного способа). Коэффициент выбирается по материалу и способу обращения. Международные данные в справочнике применяются к Казахстану как ориентир.</div><div class="grid-equal section-gap"><div><h3>Полнота данных</h3><div class="coverage-bar"><span style="width:${Math.max(0,Math.min(100,Number(eco.coverage_known_mass_pct)||0))}%"></span></div><p class="methodology">Рассчитанная масса: <strong>${qty(eco.calculated_mass_kg)} кг</strong> из ${qty(eco.known_mass_kg)} кг известной массы.<br>Известная масса без расчёта: <strong>${qty(eco.excluded_known_mass_kg)} кг</strong>.<br>Объём без пересчёта в массу: <strong>${qty(eco.unconverted_l)} л</strong>.<br>Покрытие записей: <strong>${n(eco.coverage_records_pct,1)}%</strong>. Литры с неизвестной плотностью не входят в знаменатель покрытия массы.</p></div><div><h3>Границы методики</h3><p class="methodology">Измеряется разница между способами обращения с отходами. Это не доказанное сокращение производства еды и не полный углеродный след продуктов. Пустой коэффициент остаётся неизвестным; он не заменяется нулём.</p>${(eco.assumptions||[]).slice(0,4).map(x=>`<p class="methodology">${e(typeof x==='string'?x:x.note||x.description||JSON.stringify(x))}</p>`).join('')}</div></div>${(eco.rows||[]).length?`<details><summary>Показать расчёт по записям (${Math.min(50,eco.rows.length)} из ${eco.rows.length})</summary><div class="table-wrap"><table><thead><tr><th>Запись</th><th class="numeric">Масса, кг</th><th class="numeric">Базовый фактор</th><th class="numeric">Выбранный фактор</th><th class="numeric">Разница, кг CO₂</th></tr></thead><tbody>${eco.rows.slice(0,50).map(x=>`<tr><td class="table-name">${e(x.waste_name||x.name||'Измерение')}<small>${e(x.method_name||x.method_code||'')}</small>${x.reason?`<small>${e(x.reason)}</small>`:''}</td><td class="numeric">${qty(x.mass_kg)}</td><td class="numeric">${qty(x.factor_tbo??x.factor_baseline)}</td><td class="numeric">${qty(x.factor_selected)}</td><td class="numeric">${qty(x.difference_kg??x.saving_kg)}</td></tr>`).join('')}</tbody></table></div></details>`:''}</div></section><section class="panel section-gap"><div class="panel-header"><div><h2>Время сотрудников и окупаемость</h2><p>Редактируемые допущения. Эти числа не являются измеренным эффектом внедрения.</p></div>${icon('clock')}</div><div class="panel-body"><details><summary>Рассчитать по времени и затратам</summary><form id="economy-form"><div class="form-grid three">${fields.map(([key,label,step])=>`<label>${e(label)}<input type="number" name="${key}" min="0"${key==='realizable_fraction'?' max="100"':''} step="${step}" required value="${e(key==='realizable_fraction'?S.economy[key]*100:S.economy[key])}"></label>`).join('')}</div><p class="form-help section-gap">Время проверки отчёта не включает уже учтённое время ввода записей. Доля денежной реализации показывает, какая часть высвобождённого времени действительно превращается в денежную экономию.</p><div class="form-actions"><button type="submit" class="btn">${icon('chart')}Рассчитать сценарий</button></div></form><div id="economy-result">${economyResult()}</div></details></div></section>`;
}
function economyResult(){
  const r=S.economyResult;if(!r)return '<p class="footnote">Стоимость часа, затраты и доля денежной реализации по умолчанию равны нулю. Укажите свои обоснованные допущения.</p>';
  return `<div class="economy-result"><div class="eyebrow">Результат сценария</div><div class="result-grid section-gap"><div><span>Вручную за год</span><strong>${n(r.annual_manual_hours,1)} <small>ч</small></strong></div><div><span>В системе за год</span><strong>${n(r.annual_system_hours,1)} <small>ч</small></strong></div><div><span>Высвобождённое время</span><strong>${n(r.hours_saved_year,1)} <small>ч/год</small></strong></div><div><span>Оценка стоимости времени</span><strong>${n(r.capacity_value_kzt,0)} <small>₸/год</small></strong></div><div><span>Чистая денежная экономия</span><strong>${n(r.net_cash_saving_year,0)} <small>₸/год</small></strong></div><div><span>Окупаемость</span><strong>${r.payback_months===null?'Не достигается':`${n(r.payback_months,1)} <small>мес.</small>`}</strong></div></div><p class="footnote">${e(r.message||'Высвобождённое время само по себе не является денежной экономией.')}</p></div>`;
}

async function settingsPage(){
  await loadCatalogs();
  let users=[];if(isReviewer()&&S.settingsTab==='users')users=items(await api('/users'));
  const tabs=isReviewer()?[['types','Виды отходов'],['organizations','Организации'],['users','Пользователи'],['methods','Способы']]:[['types','Виды отходов']];
  if(!tabs.some(x=>x[0]===S.settingsTab))S.settingsTab='types';
  let table='',title='',action='';
  if(S.settingsTab==='types'){
    title='Виды отходов';action='new-type';
    table=`<table><thead><tr><th>Название</th><th>Организация</th><th>Единица</th><th>Переработка</th><th>Статус</th><th></th></tr></thead><tbody>${S.wasteTypes.map(x=>`<tr><td class="table-name"><strong>${e(x.name)}</strong><small>${e(x.category||'')}</small></td><td class="table-name">${e(x.organization_id?orgName(x.organization_id):'Общий справочник')}</td><td>${unit(x.unit)}</td><td>${e(({yes:'Да',partial:'Частично',no:'Нет'})[x.recyclability]||'Не указано')}</td><td>${activeBadge(x.active)}</td><td>${isReviewer()||String(x.organization_id)===String(S.user.organization_id)?button('Изменить','edit-type',{id:x.id,class:'ghost small',icon:'edit'}):''}</td></tr>`).join('')}</tbody></table>`;
  }else if(S.settingsTab==='organizations'){
    title='Организации';action='new-organization';
    table=`<table><thead><tr><th>Организация</th><th>Тип</th><th>Адрес / корпус</th><th>Статус</th><th></th></tr></thead><tbody>${S.organizations.map(x=>`<tr><td class="table-name"><strong>${e(x.name)}</strong></td><td>${e(x.type)}</td><td>${e(x.address||'—')}</td><td>${activeBadge(x.active)}</td><td>${button('Изменить','edit-organization',{id:x.id,class:'ghost small',icon:'edit'})}</td></tr>`).join('')}</tbody></table>`;
  }else if(S.settingsTab==='users'){
    S.users=users;title='Пользователи';action='new-user';
    table=`<table><thead><tr><th>Пользователь</th><th>Роль</th><th>Организация</th><th>Статус</th><th></th></tr></thead><tbody>${users.map(x=>`<tr><td class="table-name"><strong>${e(x.full_name)}</strong><small>${e(x.username)}</small></td><td>${x.role==='reviewer'?'Проверяющий':'Ответственный'}</td><td class="table-name">${e(x.organization_name||(x.organization_id?orgName(x.organization_id):'Все организации'))}</td><td>${activeBadge(x.active)}</td><td>${button('Изменить','edit-user',{id:x.id,class:'ghost small',icon:'edit'})}</td></tr>`).join('')}</tbody></table>`;
  }else{
    title='Способы обращения';action='new-method';
    table=`<table><thead><tr><th>Способ</th><th>Код</th><th class="numeric">Фактор CO₂ / т</th><th>Статус</th><th></th></tr></thead><tbody>${S.methods.map(x=>`<tr><td class="table-name"><strong>${e(x.name)}</strong><small>${e(x.note||'')}</small></td><td>${e(x.code)}</td><td class="numeric">${qty(x.factor)}</td><td>${activeBadge(x.active)}</td><td>${button('Изменить','edit-method',{id:x.id,class:'ghost small',icon:'edit'})}</td></tr>`).join('')}</tbody></table>`;
  }
  return heading('Справочники кампуса','Организации, ответственные лица и единые правила учёта.','','Настройки данных')+`<section class="panel"><div class="tabs" role="tablist">${tabs.map(([key,label])=>`<button role="tab" aria-selected="${S.settingsTab===key}" class="tab ${S.settingsTab===key?'active':''}" data-action="settings-tab" data-value="${key}">${label}</button>`).join('')}</div><div class="panel-header"><h2>${title}</h2>${button('Добавить',action,{icon:'plus',class:'small'})}</div><div class="table-wrap">${table}</div><div class="panel-foot">${icon('info')}Использованные записи справочника деактивируются; история учёта сохраняется.</div></section>`;
}
function activeBadge(active){return active===0||active===false?'<span class="pill gray">Неактивен</span>':'<span class="pill green">Активен</span>';}

function openModal(kind,title,body,data={}){
  S.modal={kind,...data};const dialog=$('#modal');
  dialog.innerHTML=`<div class="modal-header"><h2 id="modal-title">${e(title)}</h2><button type="button" class="btn ghost icon-only" data-action="close-modal" aria-label="Закрыть">${icon('close')}</button></div><div class="modal-body"><form id="modal-form">${body}<div id="modal-error"></div><div class="form-actions"><button type="button" class="btn secondary" data-action="close-modal">Отмена</button><button type="submit" class="btn">${e(data.submitLabel||'Сохранить')}</button></div></form></div>`;
  dialog.showModal();setTimeout(()=>dialog.querySelector('input:not([type=checkbox]),textarea,select')?.focus(),30);
}
function closeModal(){const dialog=$('#modal');if(dialog.open)dialog.close();S.modal=null;}
function typeModal(item=null){
  const x=item||{},org=item?(x.organization_id??''):(S.report?.organization_id||S.user.organization_id||S.organizations[0]?.id);
  openModal('type',item?'Изменить вид отходов':'Новый вид отходов',`<div class="form-grid"><label class="full-width">Наименование<input name="name" required maxlength="150" value="${e(x.name||'')}" placeholder="Например, обрезки зелени"></label>${isReviewer()?`<label class="full-width">Организация<select name="organization_id"${item?' disabled':''}>${item&&!x.organization_id?option('','Общий справочник',''):''}${S.organizations.map(o=>option(o.id,o.name,org)).join('')}</select></label>`:''}<label>Единица<select name="unit"${item?' disabled':''}>${option('kg','Килограммы (кг)',x.unit||'kg')}${option('l','Литры (л)',x.unit)}</select></label><label>Пригоден к переработке<select name="recyclability">${option('yes','Да',x.recyclability||'no')}${option('partial','Частично',x.recyclability)}${option('no','Нет / не определено',x.recyclability||'no')}</select></label><label>Категория<select name="category"${item?' disabled':''}>${['Органические','Вторсырьё','Специальные','Смешанные','Другое'].map(c=>option(c,c,x.category||'Другое')).join('')}</select></label><label>Типичный способ<select name="default_method_id" required>${methodOptions(x.default_method_id||S.methods.find(m=>m.code==='TBO')?.id)}</select></label>${item?`<label class="check-label full-width"><input type="checkbox" name="active"${x.active!==0&&x.active!==false?' checked':''}>Активен для новых записей</label>`:''}</div><p class="form-help section-gap">У нового вида нет подтверждённых коэффициентов CO₂. Отсутствующие значения будут показаны как неизвестные; ранее принятые расчёты сохраняются.</p>`,{id:x.id,original:x});
}
function organizationModal(item=null){const x=item||{};openModal('organization',item?'Изменить организацию':'Новая организация',`<div class="form-grid"><label class="full-width">Название<input name="name" value="${e(x.name||'')}" required maxlength="180"></label><label>Тип<select name="type">${['столовая','кафедра','кофейня','гостиница','лаборатория','другое'].map(t=>option(t,t,x.type||'столовая')).join('')}</select></label><label>Адрес / корпус<input name="address" value="${e(x.address||'')}" maxlength="200"></label>${item?`<label class="check-label full-width"><input type="checkbox" name="active"${x.active!==false&&x.active!==0?' checked':''}>Организация активна</label>`:''}</div>`,{id:x.id});}
function userModal(item=null){const x=item||{};openModal('user',item?'Изменить пользователя':'Новый пользователь',`<div class="form-grid"><label class="full-width">ФИО<input name="full_name" value="${e(x.full_name||'')}" required maxlength="120"></label><label>Логин<input name="username" value="${e(x.username||'')}" required minlength="3" maxlength="80" autocomplete="off"${item?' readonly':''}></label><label>${item?'Новый пароль (необязательно)':'Пароль'}<input type="password" name="password" minlength="10" maxlength="128" autocomplete="new-password"${item?'':' required'}></label><label>Роль<select name="role" data-user-role>${option('operator','Ответственное лицо',x.role||'operator')}${option('reviewer','Проверяющий',x.role)}</select></label><label>Организация<select name="organization_id" data-user-org>${option('','Все (для проверяющего)',x.organization_id)}${S.organizations.map(o=>option(o.id,o.name,x.organization_id)).join('')}</select></label>${item?`<label class="check-label full-width"><input type="checkbox" name="active"${x.active!==0&&x.active!==false?' checked':''}>Пользователь активен</label>`:''}</div><p class="form-help section-gap">Ответственное лицо привязано к одной организации. Пароль — минимум 10 символов. Передайте его пользователю отдельно; приложение не показывает сохранённые пароли.</p>`,{id:x.id});}
function methodModal(item=null){const x=item||{};openModal('method',item?'Изменить способ':'Новый способ обращения',`<div class="form-grid"><label class="full-width">Наименование<input name="name" value="${e(x.name||'')}" required maxlength="180"></label><label>Код<input name="code" value="${e(x.code||'')}" required pattern="[A-Z][A-Z0-9_]*" maxlength="20" placeholder="Например, COMPOST"${item?' readonly':''}></label><label>Приоритет<input type="number" name="priority" value="${e(x.priority??5)}" min="1" max="99" step="1" required${item?' disabled':''}></label><label class="full-width">Справочный коэффициент, кг CO₂-экв./т<input value="${e(x.factor===null||x.factor===undefined?'Не задан':x.factor)}" readonly></label><label class="full-width">Источник и примечания<textarea name="note" maxlength="1000" placeholder="Укажите источник, материал и границы применимости">${e(x.note||'')}</textarea></label>${item?`<label class="check-label full-width"><input type="checkbox" name="active"${x.active!==false&&x.active!==0?' checked':''}>Способ активен</label>`:''}</div><p class="form-help section-gap">Новый способ создаётся без коэффициента CO₂. Для задания фактора нужна проверенная методика и обновление исходного справочника. Снимки принятых измерений сохраняются.</p>`,{id:x.id});}

function draftPrefix(){return juryMode()?'foodsave:jury:draft:':'foodsave:draft:';}
function draftKey(){return S.user&&S.report?`${draftPrefix()}${S.user.id}:${S.report.organization_id}:${S.report.id}`:'';}
function saveEntryDraft(){const form=$('#entry-form'),key=draftKey();if(!form||!key)return;try{localStorage.setItem(key,JSON.stringify(Object.fromEntries(new FormData(form))));}catch{/* Storage may be unavailable in private mode. */}}
function restoreEntryDraft(){const form=$('#entry-form'),key=draftKey();if(!form||!key)return;try{const data=JSON.parse(localStorage.getItem(key)||'null');if(!data)return;for(const [k,v] of Object.entries(data)){const field=form.elements.namedItem(k);if(field)field.value=v;}updateEntryUnit(form,false);const extra=$('.entry-extra',form);if(extra&&data.note)extra.open=true;if(data.date)fillServiceDate($('#service-day-form'),form.elements.namedItem('date').value,S.report);}catch{/* Ignore incomplete/expired draft. */}}
function clearEntryDraft(){try{if(draftKey())localStorage.removeItem(draftKey());}catch{}}
function clearUserDrafts(){try{const prefix=`${draftPrefix()}${S.user?.id}:`;for(const key of Object.keys(localStorage))if(key.startsWith(prefix))localStorage.removeItem(key);}catch{}}
function updateEntryUnit(form,changeMethod=true){
  const select=form?.elements.namedItem('waste_type_id');if(!select)return;
  const type=(S.reportTypes||S.wasteTypes).find(t=>String(t.id)===String(select.value));
  const label=$('[data-entry-unit]',form);if(label)label.textContent=unit(type?.unit);
  if(changeMethod)form.elements.namedItem('method_id').value=activeMethodId(type);
}
function formObject(form){return Object.fromEntries(new FormData(form));}
function fillServiceDate(form,date,report){
  if(!form||!date)return;
  form.elements.namedItem('date').value=date;
  form.elements.namedItem('portions').value=report.service_days?.find(day=>day.date===date)?.portions??'';
}
// The POST already returns the updated report. Keep the neighbouring form (including
// unsaved input) and use that response instead of fetching the whole page again.
function showSavedReport(result,form,date){
  if(!form?.isConnected||S.reportId!==result.id||!isEditable(result))return false;
  const weighing=form.id==='entry-form';
  const other=$(weighing?'#service-day-form':'#entry-form'),focused=document.activeElement;
  const focusInOther=other?.contains(focused);
  if(weighing){clearEntryDraft();S.pendingEntry=null;}
  S.report=result;
  $('#content').innerHTML=pageContent(reportDetail(result));
  if(other)$('#'+other.id)?.replaceWith(other);
  if(weighing){
    $('#entry-form [name=date]').value=date;
    if(other&&!other.dataset.edited)fillServiceDate(other,date,result);
  }else fillServiceDate($('#service-day-form'),date,result);
  const next=focusInOther?focused:$(weighing?'#entry-form [name=quantity]':'#service-day-form [name=portions]');
  next?.focus({preventScroll:true});
  return true;
}
function confirmWeighing(result,form,body){
  if(!showSavedReport(result,form,body.date))return;
  const type=(S.reportTypes||S.wasteTypes).find(x=>Number(x.id)===body.waste_type_id);
  toast(`Записано: ${qty(body.quantity)} ${unit(type?.unit)} · ${isoDate(body.date)}`);
}
async function mutateReport(action,comment){
  const result=await api(`/reports/${S.report.id}/${action}`,{method:'POST',body:{revision:S.report.revision,...(comment!==undefined?{comment}:{})}});
  S.report=result;toast(({submit:'Отчёт отправлен на проверку','start-review':'Проверка начата',return:'Отчёт возвращён с комментарием',accept:'Отчёт принят. Реестр и аналитика обновлены'})[action]||'Сохранено');await navigate(S.route);
}
async function downloadExport(){
  const requestEpoch=S.authEpoch;
  toast('Формируем Excel по выбранным фильтрам…');
  const response=await fetchApi(API+'/exports/summary.xlsx?'+qs(S.filters),{credentials:'same-origin'});
  if(requestEpoch!==S.authEpoch)throw new ApiError('Сессия изменилась. Повторите выгрузку в выбранной роли.',409,'stale_session');
  if(!response.ok){const d=await response.json().catch(()=>({}));throw new Error(d.error?.message||'Не удалось сформировать Excel.');}
  const blob=await response.blob();
  if(requestEpoch!==S.authEpoch)throw new ApiError('Сессия изменилась. Повторите выгрузку в выбранной роли.',409,'stale_session');
  const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=`FoodSave_${S.filters.from}_${S.filters.to}.xlsx`;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);toast('Отчёт Excel сформирован');
}

document.addEventListener('submit',async event=>{
  const form=event.target;if(!(form instanceof HTMLFormElement))return;event.preventDefault();
  const submit=form.querySelector('button[type=submit]');if(submit)submit.disabled=true;
  try{
    if(form.id==='login-form'){
      $('#login-error').innerHTML='';await signIn(formObject(form));
    }else if(form.id==='filter-form'){
      const d=formObject(form);if(d.from>d.to)throw new Error('Начало периода должно быть не позже окончания.');S.filters={...S.filters,...d};S.registryPage=1;await navigate(S.route);
    }else if(form.id==='report-filter-form'){
      const d=formObject(form);S.reportPeriod=d.period;S.reportStatus=d.status;S.reportOrg=d.organization_id||'';S.reportsPage=1;await navigate(S.route);
    }else if(form.id==='entry-form'){
      const values=formObject(form);const body={date:values.date,waste_type_id:Number(values.waste_type_id),quantity:Number(values.quantity),method_id:Number(values.method_id),reason_code:values.reason_code||'unspecified',note:values.note||'',revision:S.report.revision,client_request_id:crypto.randomUUID?crypto.randomUUID():`${Date.now()}-${Math.random()}`,confirm_duplicate:false};
      const signature=JSON.stringify([body.date,body.waste_type_id,body.quantity,body.method_id,body.reason_code,body.note,body.revision]);
      if(S.pendingEntry?.signature===signature)body.client_request_id=S.pendingEntry.id;else S.pendingEntry={signature,id:body.client_request_id};
      let result;
      try{result=await api(`/reports/${S.report.id}/entries`,{method:'POST',body});}
      catch(err){
        if(err.status===409&&(/duplicate|дубл|похож/i.test(err.code+' '+err.message))){openModal('duplicate','Похожее взвешивание уже есть',`<div class="notice warning">${e(err.message)}</div><p class="form-help section-gap">Подтвердите только если это отдельное реальное измерение, а не повторное нажатие.</p>`,{body,submitLabel:'Это отдельное измерение'});return;}
        throw err;
      }
      confirmWeighing(result,form,body);
    }else if(form.id==='service-day-form'){
      const values=formObject(form);if(values.portions==='')throw new Error('Укажите число порций; неизвестное значение сохранять не нужно.');
      const portions=Number(values.portions);if(!Number.isInteger(portions)||portions<0||portions>100000)throw new Error('Число порций должно быть целым от 0 до 100 000.');
      const result=await api(`/reports/${S.report.id}/service-days`,{method:'POST',body:{date:values.date,portions,revision:S.report.revision}});
      if(showSavedReport(result,form,values.date))toast(`Сохранено порций: ${n(portions,0)} · ${isoDate(values.date)}`);
    }else if(form.id==='agent-form'){
      const message=formObject(form).message;await sendAgent(message);
    }else if(form.id==='economy-form'){
      const raw=formObject(form),payload={};for(const [k,v] of Object.entries(raw))payload[k]=Number(v);payload.realizable_fraction/=100;
      S.economyResult=await api('/scenarios/economy',{method:'POST',body:payload});S.economy=payload;$('#economy-result').innerHTML=economyResult();toast('Сценарий рассчитан');
    }else if(form.id==='modal-form'){
      await submitModal(form);
    }
  }catch(err){
    if(form.id==='login-form'&&$('#login-error'))$('#login-error').innerHTML=`<div class="notice error" role="alert">${e(err.message)}</div>`;
    else if(form.id==='modal-form'&&$('#modal-error'))$('#modal-error').innerHTML=`<div class="notice error modal-error" role="alert">${e(err.message)}</div>`;
    else if(form.id==='entry-form'&&$('#entry-error'))$('#entry-error').innerHTML=`<div class="notice error section-gap" role="alert">${e(err.message)}${err.status===409?' Обновите отчёт перед повторной отправкой.':''}</div>${err.status===409?`<div class="section-gap">${button('Обновить отчёт','reload',{class:'secondary small',icon:'refresh'})}</div>`:''}`;
    else if(form.id==='service-day-form'&&$('#service-day-error'))$('#service-day-error').innerHTML=`<div class="notice error section-gap" role="alert">${e(err.message)}</div>${err.status===409?`<div class="section-gap">${button('Обновить отчёт','reload',{class:'secondary small',icon:'refresh'})}</div>`:''}`;
    else toast(err.message,true);
  }finally{if(submit)submit.disabled=false;}
});

async function submitModal(form){
  const d=formObject(form),modal=S.modal;if(!modal)return;
  let result,newType=null;
  if(modal.kind==='new-report'){
    result=await api('/reports',{method:'POST',body:{period:d.period,...(isReviewer()?{organization_id:Number(d.organization_id)}:{})}});S.reportId=result.id;
  }else if(modal.kind==='return'){
    if(!d.comment?.trim())throw new Error('Напишите комментарий для ответственного лица.');
    await mutateReport('return',d.comment.trim());
  }else if(modal.kind==='delete-entry'){
    S.report=await api(`/reports/${S.report.id}/entries/${modal.id}?revision=${S.report.revision}`,{method:'DELETE'});
  }else if(modal.kind==='delete-service-day'){
    S.report=await api(`/reports/${S.report.id}/service-days/${encodeURIComponent(modal.date)}?revision=${S.report.revision}`,{method:'DELETE'});
  }else if(modal.kind==='edit-entry'){
    S.report=await api(`/reports/${S.report.id}/entries/${modal.id}`,{method:'PATCH',body:{date:d.date,waste_type_id:Number(d.waste_type_id),quantity:Number(d.quantity),method_id:Number(d.method_id),reason_code:d.reason_code||'unspecified',note:d.note||'',revision:S.report.revision}});
  }else if(modal.kind==='duplicate'){
    const entryForm=$('#entry-form');
    const result=await api(`/reports/${S.report.id}/entries`,{method:'POST',body:{...modal.body,confirm_duplicate:true}});
    closeModal();confirmWeighing(result,entryForm,modal.body);return;
  }else if(modal.kind==='type'){
    const payload={name:d.name.trim(),unit:d.unit||modal.original?.unit,recyclability:d.recyclability,default_method_id:Number(d.default_method_id)};if(!modal.id){payload.category=d.category;if(isReviewer())payload.organization_id=Number(d.organization_id);}
    if(modal.id)payload.active=form.elements.namedItem('active').checked;
    result=await api('/waste-types'+(modal.id?'/'+modal.id:''),{method:modal.id?'PATCH':'POST',body:payload});if(!modal.id)newType=result.id;
    await loadCatalogs();
  }else if(modal.kind==='organization'){
    const payload={name:d.name.trim(),type:d.type,address:d.address.trim()};if(modal.id)payload.active=form.elements.namedItem('active').checked;
    await api('/organizations'+(modal.id?'/'+modal.id:''),{method:modal.id?'PATCH':'POST',body:payload});await loadCatalogs();
  }else if(modal.kind==='user'){
    if(d.role==='operator'&&!d.organization_id)throw new Error('Выберите организацию ответственного лица.');
    const payload={username:d.username.trim(),full_name:d.full_name.trim(),role:d.role,organization_id:d.role==='operator'?Number(d.organization_id):null};if(d.password)payload.password=d.password;if(modal.id)payload.active=form.elements.namedItem('active').checked;
    await api('/users'+(modal.id?'/'+modal.id:''),{method:modal.id?'PATCH':'POST',body:payload});
  }else if(modal.kind==='method'){
    const payload={name:d.name.trim(),note:d.note.trim()};if(modal.id)payload.active=form.elements.namedItem('active').checked;else{payload.code=d.code.trim().toUpperCase();payload.priority=Number(d.priority);}
    await api('/disposal-methods'+(modal.id?'/'+modal.id:''),{method:modal.id?'PATCH':'POST',body:payload});await loadCatalogs();
  }
  closeModal();if(modal.kind!=='return'){toast('Сохранено');await navigate(S.route);}
  if(newType&&$('#entry-form')){$('#entry-form [name=waste_type_id]').value=newType;updateEntryUnit($('#entry-form'));saveEntryDraft();}
}

document.addEventListener('click',async event=>{
  const nav=event.target.closest('[data-route]');
  if(nav){event.preventDefault();const route=nav.dataset.route;S.reportGuide=false;if(['reports','review'].includes(route))S.reportId=null;if(route==='review'){S.reportPeriod=S.meta.current_month;S.reportStatus='';}await navigate(route);return;}
  const target=event.target.closest('[data-action]');if(!target||target.disabled)return;
  const action=target.dataset.action,id=target.dataset.id,value=target.dataset.value;
  try{
    if(action==='reset-food-plan'){
      const root=target.closest('#food-plan');for(const f of foodPlanFields)root.querySelector(`[name="${f.name}"]`).value=String(f.base);
      refreshFoodPlan(root);return;
    }
    if(action==='menu'){document.body.classList.toggle('sidebar-open');return;}
    if(action==='close-modal'){closeModal();return;}
    if(action==='reload'){await navigate(S.route);return;}
    if(action==='jury-login'){S.jurySelection++;await enterJuryRole(value);return;}
    if(action==='logout'){await api('/auth/logout',{method:'POST',body:{}});clearSessionState();renderLogin();return;}
    if(action==='default-period'){S.filters={from:S.meta.default_from,to:S.meta.default_to,organization_id:isReviewer()?'':S.user.organization_id};S.registryPage=1;await navigate(S.route);return;}
    if(action==='export'){target.disabled=true;try{await downloadExport();}finally{target.disabled=false;}return;}
    if(action==='go-registry'){await navigate('registry');return;}
    if(action==='go-agent'){await navigate('agent');return;}
    if(action==='agent-question'){if(S.route!=='agent')await navigate('agent');await sendAgent(value);return;}
    if(action==='open-report'){S.reportId=Number(id);S.reportGuide=false;await navigate(isReviewer()?'review':'reports');return;}
    if(action==='back-reports'){S.reportId=null;S.reportGuide=false;await navigate(S.route);return;}
    if(action==='open-entry-help'){
      if(isReviewer()){await navigate('reports');return;}
      saveEntryDraft();
      const [drafts,returned]=await Promise.all([api('/reports?status=draft&page_size=200'),api('/reports?status=returned&page_size=200')]);
      const editable=[...items(drafts),...items(returned)].filter(r=>String(r.organization_id)===String(S.user.organization_id)).sort((a,b)=>b.period.localeCompare(a.period))[0];
      if(editable){S.reportId=editable.id;S.reportGuide=true;await navigate('reports');}
      else{S.reportId=null;await navigate('reports');toast('Создайте отчёт за свободный месяц: новые данные вводят в черновике или после возврата.');}
      return;
    }
    if(action==='show-entry-guide'||action==='hide-entry-guide'){
      if(!S.report)return;
      S.reportGuide=action==='show-entry-guide';
      const guide=$('.workflow-guide')||$('.guide-strip');if(guide)guide.outerHTML=reportEntryGuide(S.report);
      history.replaceState(null,'',FoodSaveRoutes.format(S.route,S.reportId,S.reportGuide));
      (S.reportGuide?$('.workflow-guide .guide-header button'):$('.guide-strip button'))?.focus({preventScroll:true});
      if(S.reportGuide)$('.workflow-guide')?.scrollIntoView({block:'start'});
      else document.querySelectorAll('.guide-target-active').forEach(node=>node.classList.remove('guide-target-active'));
      return;
    }
    if(action==='guide-weighing'){focusGuideTarget('#entry-form','waste_type_id');return;}
    if(action==='guide-reason'){focusGuideTarget('#entry-form .reason-field','reason_code');return;}
    if(action==='guide-portions'){
      focusGuideTarget('#service-day-form','portions');return;
    }
    if(action==='reports-page'){S.reportsPage=Number(value);await navigate(S.route);return;}
    if(action==='registry-page'){S.registryPage=Number(value);await navigate('registry');return;}
    if(action==='clear-report-filters'){S.reportStatus='';S.reportOrg='';}
    if(action==='all-report-periods'||action==='clear-report-filters'){S.reportPeriod='';S.reportsPage=1;await navigate(S.route);return;}
    if(action==='new-entry'){
      S.reportPeriod=S.meta.current_month;S.reportStatus='';const current=await api('/reports?'+qs({period:S.meta.current_month}));const existing=items(current).find(r=>String(r.organization_id)===String(S.user.organization_id));
      if(existing){S.reportId=existing.id;S.reportGuide=!isEditable(existing);await navigate('reports');}
      else{S.reportId=null;await navigate('reports');openModal('new-report','Создать месячный отчёт',`<label>Период<input type="month" name="period" value="${e(S.meta.current_month)}" max="${e(S.meta.current_month)}" required></label><p class="form-help">Организация: ${e(S.user.organization_name)}</p>`,{submitLabel:'Создать отчёт'});}return;
    }
    if(action==='new-report'){openModal('new-report','Новый месячный отчёт',`<label>Месяц<input type="month" name="period" value="${e(S.reportPeriod||S.meta.current_month)}" max="${e(S.meta.current_month)}" required></label><p class="form-help section-gap">Организация: ${e(S.user.organization_name)}. Для организации может быть один отчёт за месяц.</p>`,{submitLabel:'Создать отчёт'});return;}
    if(action==='report-return'){openModal('return','Вернуть на доработку',`<label>Что нужно исправить?<textarea name="comment" required maxlength="2000" placeholder="Опишите замечания к измерениям или способам утилизации"></textarea></label>`,{submitLabel:'Вернуть отчёт'});return;}
    if(action.startsWith('report-')){target.disabled=true;try{await mutateReport(action.slice(7));}finally{target.disabled=false;}return;}
    if(action==='repeat-entry'){
      if(!isEditable(S.report))return;const entry=S.report.entries?.at(-1),form=$('#entry-form');if(!entry||!form)return;
      if(![...form.elements.namedItem('waste_type_id').options].some(x=>String(x.value)===String(entry.waste_type_id)))throw new Error('Последний вид отходов неактивен. Выберите действующий вид вручную.');
      for(const key of ['waste_type_id','quantity','reason_code','note']){const field=form.elements.namedItem(key);if(field)field.value=entry[key]??(key==='reason_code'?'unspecified':'');}
      form.elements.namedItem('method_id').value=S.methods.some(x=>String(x.id)===String(entry.method_id)&&x.active!==false&&x.active!==0)?entry.method_id:activeMethodId((S.reportTypes||S.wasteTypes).find(x=>String(x.id)===String(entry.waste_type_id)));
      updateEntryUnit(form,false);const extra=$('.entry-extra',form);if(extra)extra.open=!!entry.note;saveEntryDraft();form.scrollIntoView({block:'center'});form.elements.namedItem('quantity').focus();toast('Форма подготовлена. Проверьте дату и значения, затем добавьте взвешивание.');return;
    }
    if(action==='edit-service-day'){if(!isEditable(S.report))return;const day=S.report.service_days.find(x=>x.date===value),form=$('#service-day-form');if(day&&form){form.dataset.edited='1';form.elements.namedItem('date').value=day.date;form.elements.namedItem('portions').value=day.portions;form.scrollIntoView({block:'center'});form.elements.namedItem('portions').focus();}return;}
    if(action==='delete-service-day'){if(!isEditable(S.report))return;openModal('delete-service-day','Удалить число порций?',`<p class="methodology">${e(isoDate(value))}. После удаления число порций за этот день будет неизвестным.</p>`,{date:value,submitLabel:'Удалить'});return;}
    if(action==='edit-entry'){const entry=S.report.entries.find(x=>String(x.id)===id);if(entry)openModal('edit-entry','Изменить взвешивание',entryFields(entry,true),{id:Number(id)});return;}
    if(action==='delete-entry'){const entry=S.report.entries.find(x=>String(x.id)===id);openModal('delete-entry','Удалить взвешивание?',`<p class="methodology">${e(entry?.waste_name||'Запись')} · ${qty(entry?.quantity)} ${unit(entry?.unit)} · ${e(isoDate(entry?.date))}</p><p class="form-help">Действие будет отражено в истории отчёта.</p>`,{id:Number(id),submitLabel:'Удалить запись'});return;}
    if(action==='settings-tab'){S.settingsTab=value;await navigate('settings');return;}
    if(action==='new-type'){saveEntryDraft();typeModal();return;}
    if(action==='edit-type'){typeModal(S.wasteTypes.find(x=>String(x.id)===id));return;}
    if(action==='new-organization'){organizationModal();return;}
    if(action==='edit-organization'){organizationModal(S.organizations.find(x=>String(x.id)===id));return;}
    if(action==='new-user'){userModal();return;}
    if(action==='edit-user'){userModal(S.users.find(x=>String(x.id)===id));return;}
    if(action==='new-method'){methodModal();return;}
    if(action==='edit-method'){methodModal(S.methods.find(x=>String(x.id)===id));return;}
  }catch(err){toast(err.message,true);}
});
document.addEventListener('input',event=>{
  if (event.target.id === 'example-mass') {
    const panel = event.target.closest('#ecology-example');
    S.ecologyExampleMass = event.target.value;
    panel.querySelector('.eco-working').innerHTML = ecologyExampleResult(
      S.ecologyExampleMass, Number(panel.dataset.landfill), Number(panel.dataset.compost)
    );
    return;
  }
  const plan=event.target.closest('#food-plan');if(plan&&event.target.matches('input')){refreshFoodPlan(plan);return;}
  if(event.target.closest('#entry-form'))saveEntryDraft();
  const service=event.target.closest('#service-day-form');if(service)service.dataset.edited='1';
});
document.addEventListener('change',event=>{
  if(event.target.matches('#service-day-form [name=date]')){
    const service=event.target.form;service.dataset.edited='1';fillServiceDate(service,event.target.value,S.report);
  }
  if(event.target.matches('#entry-form [name=date]')){
    const service=$('#service-day-form');if(service&&!service.dataset.edited)fillServiceDate(service,event.target.value,S.report);
  }
  if(event.target.matches('[data-entry-type]')){updateEntryUnit(event.target.closest('form'));saveEntryDraft();}
  if(event.target.matches('[data-user-role]')){const select=$('[data-user-org]',event.target.closest('form'));if(event.target.value==='reviewer')select.value='';}
});
document.addEventListener('keydown',event=>{if(event.target.id==='agent-message'&&event.key==='Enter'&&!event.shiftKey){event.preventDefault();if(event.target.value.trim()&&!S.agentBusy)$('#agent-form').requestSubmit();}});
$('#modal').addEventListener('close',()=>{S.modal=null;});
window.addEventListener('hashchange',()=>{if(S.user){saveEntryDraft();navigateLocation();}});

async function start(){
  if(juryMode()){
    document.body.dataset.juryState='preparing';
    const requestedRole=new URLSearchParams(location.search).get('role');
    S.meta.demo=true;S.juryStatus='Подготавливаем демонстрационную базу в браузере. Можно выбрать роль уже сейчас.';
    renderLogin();
    try{
      await prepareJury();
      if(!S.juryBusy&&!S.user){
        if(requestedRole==='iskander'&&new URLSearchParams(location.search).get('example')==='portions'){
          const selection=S.jurySelection;
          let exampleId=null;
          try{if(typeof window.FoodSaveJury?.exampleReport==='function')exampleId=await window.FoodSaveJury.exampleReport();}
          catch{/* The optional prepared example must not prevent entering the journal. */}
          if(selection!==S.jurySelection||S.juryBusy||S.user)return;
          if(Number.isSafeInteger(exampleId)&&exampleId>0)history.replaceState(null,'',FoodSaveRoutes.format('reports',exampleId,true));
          else if(!location.hash)history.replaceState(null,'',FoodSaveRoutes.format('reports'));
        }
        if(['iskander','reviewer'].includes(requestedRole))await enterJuryRole(requestedRole,Boolean(location.hash));
        else renderLogin();
      }
    }
    catch(error){if(!S.juryBusy&&!S.user)renderLogin(error.message);}
    return;
  }
  try{
    S.meta=await api('/meta');S.reportPeriod=S.meta.current_month;S.filters={from:S.meta.default_from,to:S.meta.default_to};
    try{const me=await api('/auth/me');S.user=me.user;S.csrf=me.csrf_token||'';}
    catch(err){if(err.status!==401)throw err;}
    if(!S.user){const t=await api('/auth/csrf');S.csrf=t.csrf_token;renderLogin();return;}
    if(!S.csrf)S.csrf=(await api('/auth/csrf')).csrf_token;
    await loadCatalogs();S.filters.organization_id=isReviewer()?'':S.user.organization_id;S.reportPeriod=isReviewer()?S.meta.current_month:'';await navigateLocation();
  }catch(err){renderLogin(err.message);}
}
start();
