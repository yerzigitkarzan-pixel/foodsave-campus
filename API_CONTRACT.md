# FoodSave Campus — общий контракт реализации

Локальный FastAPI + SQLite, один origin, русский интерфейс. Prefix `/api/v1`.
Исходные справочники: `inputs/reference.xlsx` и извлечение `inputs/reference_cells.json`. Подробное исходное ТЗ: `inputs/Track_1_Requirements.docx`; задание на доработку: `CODEX_TASK.md`.

## Авторизация

GET `/auth/csrf` => `{csrf_token}` устанавливает HttpOnly cookie `foodsave_session`.
POST `/auth/login` JSON `{username,password}`, header `X-CSRF-Token`; => `{user,csrf_token}`.
GET `/auth/me` => `{user,csrf_token}` или 401.
POST `/auth/logout` с CSRF.
Все mutations требуют `X-CSRF-Token`, cookies same origin. Ошибки `{error:{code,message,fields?}}`.
User `{id,username,full_name,role:'operator'|'reviewer',organization_id,organization_name}`.
Reviewer также администратор. Operator ограничен своей организацией на сервере.

GET `/meta` => `{app_name,version,demo,today,current_month,default_from,default_to,timezone,waste_reasons:[{code,label}]}`.

## Каталоги

GET `/organizations` => `{items:[{id,name,short_name,type,address,active}],total}`; operator only own.
POST `/organizations` reviewer `{name,type,address}`.
PATCH `/organizations/{id}` reviewer `{name?,type?,address?,active?}`.
GET `/users` reviewer => `{items:[user...]}`.
POST `/users` reviewer `{username,full_name,password,role,organization_id}`.
PATCH `/users/{id}` reviewer similar optional fields including active; no self-disable/self-demote.
GET `/waste-types?organization_id=N` => `{items:[{id,name,unit:'kg'|'l',category,recyclability:'yes'|'partial'|'no',default_method_id,organization_id,active,factor_tbo,density_kg_per_l,source_note}],total}`.
При первоначальном импорте исходного справочника `default_method_id` указывает на TBO, как в образцах Excel. Рекомендованный способ из исходного листа не считается фактическим: альтернативы отдельно используются при генерации явно синтетических демозаписей. Пользователь выбирает фактический способ во время ввода.
POST `/waste-types` => created type, fields `{name,unit,category?,recyclability?,default_method_id,organization_id?}`. Operator org server-resolved. New factors/density unknown.
PATCH `/waste-types/{id}` => deactivation/rename by permitted owner; no unit change if used.
GET `/disposal-methods` => `{items:[{id,code,name,factor,priority,note,active}],total}`.
POST/PATCH `/disposal-methods[/{id}]` reviewer; new code coefficient unknown unless explicitly set.

## Отчёты

Statuses draft,submitted,in_review,returned,accepted. Operator edit draft/returned only. Reviewer transitions submitted->in_review->returned|accepted. Return comment required.
GET `/reports?period=YYYY-MM&status=...&organization_id=N&page=1&page_size=50` => `{items:[Report],total,page,page_size}`.
POST `/reports` `{period,organization_id?}` => Report (unique org/month).
GET `/reports/{id}` => Report with `entries`, `totals`, `history`.
Report `{id,organization_id,organization_name,period,status,revision,entry_count,total_kg,total_l,created_at,submitted_at,decided_at,last_comment}`.
Entry `{id,report_id,date,waste_type_id,waste_name,quantity,unit,method_id,method_name,method_code,responsible_name,organization_id,organization_name,category,recyclability,density_kg_per_l,factor_tbo,factor_selected,source_note,coefficient_source}`.
POST `/reports/{id}/entries` `{date,waste_type_id,quantity,method_id,revision,client_request_id,confirm_duplicate?}` => full updated Report.
PATCH `/reports/{id}/entries/{entry_id}` `{date,waste_type_id,quantity,method_id,revision}` => Report.
DELETE `/reports/{id}/entries/{entry_id}?revision=N` => Report.
POST `/reports/{id}/submit|start-review|return|accept` `{revision,comment?}` => Report.
GET `/reports/{id}/history` => `{items:[{id,action,from_status,to_status,comment,actor_name,timestamp,details}]}`.
Totals in report `{known_mass_kg,raw_kg,volume_l,unconverted_l,records,by_type:[TypeTotal],daily:[{date,kg,l,by_type:[TypeTotal]}]}`.
TypeTotal `{id,name,kg,l,known_mass_kg,records}`. `kg` и `l` — исходные количества за месяц или день; `known_mass_kg` включает только массу с известной плотностью. Типы отсортированы по названию, дни — по дате. Литры без плотности остаются в `l` и общем `unconverted_l`, не превращаясь в известную массу.
All quantities finite >0 <=10000, <=3 decimal places. Date not future and belongs to report month. Conflict 409.

### Причины и порции

Entry дополнительно содержит `reason_code` и `note`. POST/PATCH entries принимают необязательные `reason_code` и `note` (строка до 1000 символов). Коды причин: `unspecified`, `preparation`, `overproduction`, `spoilage`, `plate_leftovers`, `other`; русские названия приходят в `/meta.waste_reasons`. Для старых записей причина «Не указана», примечание пустое. PATCH сохраняет отсутствующие поля; явная пустая строка очищает примечание. Идемпотентность сравнивает и эти поля.

Report detail дополнительно содержит `service_days:[{date,portions}]` и `totals.intensity`.

- POST `/reports/{id}/service-days` `{date,portions,revision}` — добавить/заменить число порций за день. `portions` — целое 0…100000; 0 означает отсутствие обслуживания, отсутствие строки — неизвестное число. Дата входит в месяц отчёта и не находится в будущем.
- DELETE `/reports/{id}/service-days/{date}?revision=N` — удалить число порций, вернув его к неизвестному.

Оба действия доступны только оператору своей организации в `draft`/`returned`, требуют CSRF и текущую ревизию, возвращают обновлённый Report и фиксируются в истории. Принятые значения не редактируются.

Dashboard дополнительно содержит `by_reason:[{code,label,raw_kg,volume_l,known_mass_kg,records}]`, `service_days` и `intensity`. Агент получает тот же разрешённый расчёт в `scope.intensity`; причины являются записями пользователя, а не установленной моделью причинностью.

Intensity: `{kg_per_100_portions,covered_kg_per_100_portions,covered_mass_kg,portions,total_days,covered_days,missing_days,zero_portion_days,unknown_mass_days,coverage_days_pct,complete,message,daily,by_organization,service_only_days,definition}`. Единица дня — пара организация/дата с выбранными взвешиваниями. Она покрыта только при положительном числе порций и известной массе всех выбранных строк. Порции дня учитываются один раз. Основной показатель — масса / порции × 100 — заполнен только при полном покрытии. Частичный показатель относится только к явно указанным покрытым дням; неизвестное не заменяется нулём. Дни обслуживания без взвешиваний не считаются днями с нулевыми отходами. Фильтры вида/способа меняют выбранную массу и набор дней с этими взвешиваниями.

XLSX сохраняет причины/примечания в подробном журнале и добавляет шестой лист «Порции» с датами, числами, покрытием и определением. Отсутствующие показатели остаются пустыми.

## Реестр и аналитика

Filters shared `from=YYYY-MM-DD&to=YYYY-MM-DD&organization_id=N&waste_type_id=N&method_id=N` inclusive. Defaults `meta.default_from/to` complete previous quarter. Only accepted.
GET `/registry` => `{items:[Entry...],total,page,page_size}`.
GET `/dashboard` => `{totals,monthly,by_type,by_organization,comparison,ecology,filters}`.
totals `{known_mass_kg,raw_kg,volume_l,unconverted_l,records,organizations,recyclable_mass_kg,partial_mass_kg,recycled_mass_kg}`.
monthly `[{label:'YYYY-MM',mass_kg}]`; by_type `[{id,name,mass_kg,records}]`; by_organization `[{id,name,mass_kg,records}]`.
comparison `{current_mass_kg,previous_mass_kg,change_percent,previous_from,previous_to}`.
GET `/missing-reports?month=YYYY-MM&organization_id=N` => `{items:[{organization_id,organization_name,status,report_id}],month}`. Организация необязательна для проверяющего; оператор всегда ограничен своей организацией, а явный чужой ID отклоняется.
GET `/ecology` => `{baseline_kg,selected_kg,difference_kg,known_mass_kg,calculated_mass_kg,excluded_known_mass_kg,unconverted_l,calculated_count,total_count,coverage_records_pct,coverage_known_mass_pct,rows,assumptions,filters,teaching_example}`.
`teaching_example` содержит `{waste_name,method_name,factor_tbo,factor_selected,source}` для учебного сравнения. Коэффициенты в кг CO₂-экв./т берутся из справочника. Если справочные значения недоступны, поле равно `null`. Фильтры применяются к показателям принятых записей.
GET `/exports/summary.xlsx` same filters => XLSX binary.
POST `/scenarios/economy` JSON `{records_per_period,reports_per_period,manual_minutes_per_entry,system_minutes_per_entry,manual_minutes_per_report,system_minutes_per_report,periods_per_year,hourly_cost,realizable_fraction,capex,annual_opex}` => `{annual_manual_hours,annual_system_hours,hours_saved_year,capacity_value_kzt,cash_saving_before_opex,net_cash_saving_year,payback_months,message}`.

## Локальный аналитический агент

POST `/agent/chat` `{message,from?,to?,organization_id?}` => `{answer,tools:[{name,label,status}],evidence:[{label,value,unit?}],suggestions:[string],anomalies:[object],model:{name,available,description},scope:{from,to,organization,missing_month},disclaimer}`.
`scope.missing_month` — месяц конца выбранного периода, ограниченный текущим месяцем, если конец фильтра ещё не наступил. Проверка сдачи использует этот месяц и выбранную организацию, а ответ явно называет месяц контроля. Для сравнения полных календарных месяцев (в том числе 2, 6 и 12) предыдущий период содержит столько же полных месяцев; для неполных дат — столько же календарных дней. Семантика совпадает с `/dashboard`.
GET `/agent/anomalies` same filters => `{items,model,training,limitations}`.
Агент только читает доступные пользователю данные, выводит результаты инструментов и объяснения. Реальный ML — IsolationForest для необычных ежедневных масс; маршрутизация/текст — детерминированные, не универсальная LLM. API-ключи не нужны.

## Контракт модулей Python для параллельной работы

`app.analytics.summarize(rows, previous_rows=None)` returns dashboard fields totals/monthly/by_type/by_organization/comparison.
`app.analytics.calculate_ecology(rows)` returns ecology object above; rows have all snapshot fields in Entry.
`app.analytics.calculate_economy(payload)` validates strictly and returns scenario; raises ValueError on invalid.
`app.xlsx_export.build_xlsx(rows, dashboard, ecology, filters)` returns bytes, stdlib ZIP/XML only for portable exporter. Nonempty workbook with numeric/date cells, safe text strings.
`app.assistant.detect_anomalies(rows, history)` => anomalies object. Train only accepted dates strictly before scoring range/candidate. `history` is full authorized accepted history, rows is selected.
`app.assistant.respond(message, rows, history, missing, scope)` => agent chat object. Scope contains from/to/organization. Use analytics helpers.

`app.db.init_db(db_path)` initializes schema. `app.seed.seed_demo(db_path, as_of=None, passwords=None)` creates demo once, returns `{username:password}`; usernames reviewer,tpp,thipp,atuinn,canella,iskander. Empty existing user set required, never erase existing. as_of ISO date. `passwords` optional per username for tests, otherwise random.
`app.main.create_app(db_path=None)` initializes DB and returns FastAPI, no auto seed. `run.py` runs seed on first local launch and writes generated credentials only to ignored `.local/DEMO_ACCESS.txt`.
Tests use standard unittest + FastAPI TestClient; pytest not installed. Do not add test dependencies unless needed.
