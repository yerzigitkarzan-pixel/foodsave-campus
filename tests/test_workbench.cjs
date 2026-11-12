'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {JSDOM} = require('jsdom');
const asset = name => fs.readFileSync(path.join(__dirname, '../static', name), 'utf8');
const settle = () => new Promise(resolve => setImmediate(resolve));

// Only fixtures are used here. This exercises actual DOM, form and event logic
// without a browser, a server, network traffic or a write to the demo database.
async function mount(t, {hash='#reports/7', role='operator', status='draft', duplicate=false, teachingExample={waste_name:'Пищевые отходы',method_name:'Компостирование',factor_tbo:700.21,factor_selected:8.88,source:'Контрольный учебный справочник'}}={}) {
  const dom = new JSDOM(asset('index.html'), {url:'https://foodsave.test/'+hash, runScripts:'outside-only'});
  const win=dom.window, doc=win.document, calls=[];
  // jsdom does not implement the native dialog's top layer.
  const dialog=doc.getElementById('modal');
  dialog.showModal=function(){this.setAttribute('open','');};
  dialog.close=function(){this.removeAttribute('open');this.dispatchEvent(new win.Event('close'));};
  t.after(()=>win.close());
  const entry={id:1,date:'2026-06-12',waste_type_id:4,quantity:3,unit:'kg',waste_name:'Овощи',method_name:'ТБО',reason_code:'other'};
  let report={id:7,organization_id:1,organization_name:'Столовая',period:'2026-06',status,revision:2,entries:[entry],service_days:[{date:entry.date,portions:200}],history:[],totals:{known_mass_kg:3}};
  const meta={today:'2026-11-12',current_month:'2026-11',default_from:'2026-07-01',default_to:'2026-09-30',waste_reasons:[{code:'unspecified',label:'Не указана'},{code:'other',label:'Другая'}]};
  const user={id:8,role,organization_id:role==='operator'?1:null,organization_name:'Столовая',username:'test',full_name:'Тест'};
  win.fetch=async (url,{method='GET',body}={})=>{
    const address=new URL(url,win.location.href),p=address.pathname.replace('/api/v1','');
    calls.push([method,p]);
    let data;
    if(p==='/meta')data=meta;
    else if(p==='/auth/me')data={user,csrf_token:'fixture'};
    else if(p==='/organizations')data=[{id:1,name:'Столовая'}];
    else if(p==='/disposal-methods')data=[{id:1,code:'TBO',name:'ТБО',active:true}];
    else if(p==='/waste-types')data=[{id:4,name:'Овощи',unit:'kg',default_method_id:1,active:true}];
    else if(p==='/reports/7' && method==='GET')data=report;
    else if(p==='/reports/7/entries' && method==='POST') {
      const b=JSON.parse(body); assert.equal(b.revision,report.revision);
      if(duplicate&&!b.confirm_duplicate)return {ok:false,status:409,json:async()=>({error:{code:'duplicate',message:'Похожая запись'}})};
      report={...report,revision:report.revision+1,entries:[...report.entries,{...entry,...b,id:2}]}; data=report;
    }else if(p==='/reports/7/service-days' && method==='POST') {
      const b=JSON.parse(body); assert.equal(b.revision,report.revision);
      report={...report,revision:report.revision+1,service_days:[...report.service_days.filter(x=>x.date!==b.date),{date:b.date,portions:b.portions}]}; data=report;
    }else if(p==='/dashboard')data={totals:{known_mass_kg:3,records:1}};
    else if(p==='/ecology')data={baseline_kg:2.1,selected_kg:0.03,difference_kg:2.07,known_mass_kg:3,calculated_mass_kg:3,excluded_known_mass_kg:0,unconverted_l:0,calculated_count:1,total_count:1,coverage_records_pct:100,coverage_known_mass_pct:100,rows:[],assumptions:[],teaching_example:teachingExample};
    else if(p==='/missing-reports')data=status==='accepted'?[]:[{organization_id:1,report_id:7,status}];
    else if(p==='/reports')data={items:[{...report,entry_count:1,total_kg:3},{...report,id:5,entry_count:2,total_kg:2,status:'accepted'}],total:2,page:1,page_size:25};
    else throw Error('Unexpected API path: '+p);
    return {ok:true,json:async()=>structuredClone(data)};
  };
  for(const name of ['routes.js','app.js'])vm.runInContext(asset(name),dom.getInternalVMContext(),{filename:name});
  await settle();
  const $=s=>doc.querySelector(s);
  const enter=(field,value)=>{field.value=value;field.dispatchEvent(new win.Event('input',{bubbles:true}));};
  const submit=async form=>{form.dispatchEvent(new win.Event('submit',{bubbles:true,cancelable:true}));await settle();};
  return {$,doc,win,calls,enter,submit};
}

test('saving either form preserves the unfinished neighbouring task and confirms the actual values',async t=>{
  const {$,calls,enter,submit}=await mount(t);
  const reason=$('#entry-form [name=reason_code]');assert.ok(reason);assert.equal(reason.closest('details'),null);
  assert.equal($('#entry-form [name=date]').value,'2026-06-12');assert.equal($('#service-day-portions').value,'200');
  enter($('#service-day-portions'),'275');
  enter($('#entry-form [name=quantity]'),'2.5');enter(reason,'other');
  await submit($('#entry-form'));
  assert.equal($('#service-day-portions').value,'275');
  assert.match($('#toast-region').textContent,/2,5 кг/);
  const qty=$('#entry-form [name=quantity]');enter(qty,'7');
  await submit($('#service-day-form'));
  assert.equal($('#entry-form [name=quantity]').value,'7');
  assert.match($('#toast-region').textContent,/275 · 12\.06\.2026/);
  assert.deepEqual(calls.filter(c=>c[0]==='POST'),[['POST','/reports/7/entries'],['POST','/reports/7/service-days']]);
  assert.equal(calls.filter(c=>c[0]==='GET'&&c[1]==='/reports/7').length,1);
});

test('date selection loads saved portions, preserves zero, and leaves unknown days blank',async t=>{
  const {$,win,enter,submit}=await mount(t),day=$('#service-day-date');
  day.value='2026-06-15';day.dispatchEvent(new win.Event('change',{bubbles:true}));
  assert.equal($('#service-day-portions').value,'');
  enter($('#service-day-portions'),'0');await submit($('#service-day-form'));
  assert.equal($('#service-day-portions').value,'0');
  const next=$('#service-day-date');next.value='2026-06-12';next.dispatchEvent(new win.Event('change',{bubbles:true}));
  assert.equal($('#service-day-portions').value,'200');
});

test('confirming a separate similar weighing also keeps the other form and does not save it',async t=>{
  const {$,enter,submit,calls}=await mount(t,{duplicate:true});
  enter($('#service-day-portions'),'375');enter($('#entry-form [name=quantity]'),'3');
  await submit($('#entry-form'));assert.ok($('#modal[open]'));
  assert.equal($('#service-day-portions').value,'375');
  await submit($('#modal-form'));
  assert.equal($('#modal[open]'),null);assert.match($('#toast-region').textContent,/3 кг/);
  assert.equal($('#service-day-portions').value,'375');
  assert.equal(calls.some(([m,p])=>m==='POST'&&p.endsWith('/service-days')),false);
});

test('the overview offers one usable next step for each role and current report state',async t=>{
  for(const [role,status,expected] of [['operator','submitted','[href="#reports"]'],['operator','accepted','[href="#reports"]'],['operator','draft','[data-action="new-entry"]'],['operator','missing','[data-action="new-entry"]'],['operator','returned','[data-action="new-entry"]'],['reviewer','submitted','[href="#review"]']]){
    const {$}=await mount(t,{hash:'#overview',role,status});
    assert.equal($('.hero-actions').children.length,1);assert.ok($('.hero-actions > '+expected));
  }
});

test('drafts appear before the archive, and a submitted report opens without entry controls',async t=>{
  const listing=await mount(t,{hash:'#reports'});
  assert.equal(listing.$('.report-slip').hash,'#reports/7');
  assert.match(listing.$('.report-stack-working').textContent,/Черновик/);
  const locked=await mount(t,{status:'submitted'});
  assert.equal(locked.$('#entry-form'),null);assert.equal(locked.$('#service-day-form'),null);
  assert.match(locked.$('#content').textContent,/Отправлено/);
});

test('the food-loss teaching plan starts with a transparent 5 × 200 × 20 example, separate from economy',async t=>{
  const {$,calls}=await mount(t,{hash:'#effect'}),plan=$('#food-plan');
  assert.ok(plan);assert.ok($('#economy-form'));
  assert.equal(plan.contains($('#economy-form')),false);
  assert.equal($('#economy-form').contains(plan),false);
  assert.equal($('#food-plan [name=portions_per_day]').value,'5');
  assert.equal($('#food-plan [name=cost_per_portion]').value,'200');
  assert.equal($('#food-plan [name=work_days]').value,'20');
  const total=$('#food-plan-total').textContent.replace(/\s+/g,' ').trim();
  assert.equal(total,'20 000 ₸');
  assert.match($('#food-plan-formula').textContent,/5\s*×\s*200\s*₸\s*×\s*20\s*=\s*20\s*000\s*₸/);
  assert.match($('#food-plan-speech').textContent,/20\s*000\s*₸/);
  assert.deepEqual(calls.filter(([method,p])=>method==='GET'&&p==='/ecology'),[['GET','/ecology']]);
  assert.equal(calls.some(([method])=>method!=='GET'),false);
});

test('each teaching-plan input recalculates live, accepts zero portions and never writes report data',async t=>{
  const {$,win,calls,enter}=await mount(t,{hash:'#effect'});
  const economyBefore=JSON.stringify(Array.from(new win.FormData($('#economy-form'))));
  const assertTotal=expected=>assert.equal($('#food-plan-total').textContent.replace(/\s+/g,' ').trim(),expected);
  enter($('#food-plan [name=portions_per_day]'),'8');assertTotal('32 000 ₸');
  enter($('#food-plan [name=cost_per_portion]'),'150');assertTotal('24 000 ₸');
  enter($('#food-plan [name=work_days]'),'10');assertTotal('12 000 ₸');
  assert.match($('#food-plan-speech').textContent,/12\s*000\s*₸/);
  enter($('#food-plan [name=portions_per_day]'),'0');assertTotal('0 ₸');
  $('#food-plan [data-action=reset-food-plan]').click();assertTotal('20 000 ₸');
  assert.equal(JSON.stringify(Array.from(new win.FormData($('#economy-form')))),economyBefore);
  assert.equal(calls.some(([method])=>method!=='GET'),false);
  assert.equal(calls.some(([,p])=>p.startsWith('/reports')),false);
});

test('blank or invalid teaching-plan inputs remove both the result and the numeric speech claim',async t=>{
  const {$,calls,enter}=await mount(t,{hash:'#effect'});
  const defaults={portions_per_day:'5',cost_per_portion:'200',work_days:'20'};
  for(const [name,value] of [
    ['portions_per_day',''],['cost_per_portion',''],['work_days',''],
    ['portions_per_day','-1'],['cost_per_portion','-1'],['work_days','-1'],
    ['portions_per_day','1.5'],['work_days','2.5'],['work_days','32'],['cost_per_portion','1e309'],
  ]){
    for(const [key,valid] of Object.entries(defaults))enter($('#food-plan [name='+key+']'),valid);
    enter($('#food-plan [name='+name+']'),value);
    assert.equal($('#food-plan-total').textContent.trim(),'—',name+'='+value);
    assert.doesNotMatch($('#food-plan-speech').textContent,/\d/,name+'='+value);
  }
  for(const [name,value] of Object.entries(defaults))enter($('#food-plan [name='+name+']'),value);
  assert.equal($('#food-plan-total').textContent.replace(/\s+/g,' ').trim(),'20 000 ₸');
  assert.match($('#food-plan-speech').textContent,/20\s*000\s*₸/);
  assert.equal(calls.some(([method])=>method!=='GET'),false);
});

function ecologySummary(doc){
  const labels=['Базовый вариант','Выбранные способы','Разница выбросов','Покрытие известной массы'];
  return labels.map(label=>{
    const card=Array.from(doc.querySelectorAll('.stat-card')).find(node=>node.querySelector('.stat-top > span')?.textContent===label);
    assert.ok(card,'Missing existing ecology summary: '+label);
    return {label,value:card.querySelector('.stat-value').textContent.replace(/\s+/g,' ').trim()};
  });
}

test('the ecology teaching mass recalculates locally without changing accepted summary or either economy',async t=>{
  const {$,doc,win,calls,enter}=await mount(t,{hash:'#effect'}),example=$('#ecology-example');
  assert.ok(example);
  const mass=$('#ecology-example [name=example_mass_kg]');assert.ok(mass);assert.equal(mass.value,'100');
  const difference=()=>$('#eco-example-difference').textContent.replace(/\s+/g,' ').trim();
  assert.equal(difference(),'69,133 кг CO₂-экв.');
  assert.match(example.textContent,/Пищевые отходы/);assert.match(example.textContent,/Компостирование/);
  assert.match(example.textContent,/Контрольный учебный справочник/);
  const summaryBefore=ecologySummary(doc),callsBefore=JSON.stringify(calls);
  const economyBefore=JSON.stringify(Array.from(new win.FormData($('#economy-form'))));
  const foodBefore={total:$('#food-plan-total').textContent,speech:$('#food-plan-speech').textContent};
  for(const [value,expected] of [['10','6,9133 кг CO₂-экв.'],['0','0 кг CO₂-экв.'],['','—'],['10','6,9133 кг CO₂-экв.']]){
    enter(mass,value);assert.equal(difference(),expected);
    assert.deepEqual(ecologySummary(doc),summaryBefore);
    assert.equal(JSON.stringify(Array.from(new win.FormData($('#economy-form')))),economyBefore);
    assert.deepEqual({total:$('#food-plan-total').textContent,speech:$('#food-plan-speech').textContent},foodBefore);
  }
  enter($('#food-plan [name=portions_per_day]'),'8');
  assert.equal($('#food-plan-total').textContent.replace(/\s+/g,' ').trim(),'32 000 ₸');
  assert.equal(difference(),'6,9133 кг CO₂-экв.');assert.deepEqual(ecologySummary(doc),summaryBefore);
  await settle();
  assert.equal(JSON.stringify(calls),callsBefore,'Changing either teaching input must not request or write API data');
  assert.equal(calls.some(([method])=>method!=='GET'),false);
});

test('unavailable ecology teaching factors are explicit while accepted summary and economy remain available',async t=>{
  const {$,doc,calls}=await mount(t,{hash:'#effect',teachingExample:null}),example=$('#ecology-example');
  assert.ok(example);
  assert.match(example.textContent,/недоступ|нет (?:справочн|коэффициент|данных)|не удалось|не задан/iu);
  assert.doesNotMatch(example.textContent,/69,133|700[.,]21|8[.,]88/);
  if($('#eco-example-difference'))assert.equal($('#eco-example-difference').textContent.trim(),'—');
  const summary=ecologySummary(doc);
  for(const [index,expected] of [[0,'2,1'],[1,'0,03'],[2,'2,07'],[3,'100']]){
    assert.ok(summary[index].value.startsWith(expected),summary[index].label+' retains its API value');
  }
  assert.ok($('#economy-form'));assert.equal($('#food-plan-total').textContent.replace(/\s+/g,' ').trim(),'20 000 ₸');
  assert.deepEqual(calls.filter(([,p])=>p==='/ecology'),[['GET','/ecology']]);
  assert.equal(calls.some(([method])=>method!=='GET'),false);
});
