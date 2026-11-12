"""Import the supplied workbook's extracted cells with source provenance."""
from pathlib import Path
from functools import lru_cache
import json
import math

ROOT=Path(__file__).resolve().parents[1]
ORGANIZATIONS=[
 ('Кафедра ТПП','ТПП','Кафедра','Учебный корпус'),
 ('Кафедра ТХиПП','ТХиПП','Кафедра','Учебный корпус'),
 ('Учебно-гостиничный комплекс ATU INN','ATU INN','Гостиница','АТУ'),
 ('Кофейня АТУ (ИП «Canella»)','Canella','Кофейня','АТУ'),
 ('Столовый комплекс корп. 1, 2 (ИП «Искандер»)','Искандер','Столовая','Корпуса 1, 2'),
]

def cells(row):
    return {''.join(c for c in item['cell'] if c.isalpha()):item['value'] for item in row}

@lru_cache(maxsize=1)
def ecology_teaching_example():
    """Read the two workbook factors used in the worked vegetable-peel example."""
    def find_row(sheets, sheet_id, row_name):
        sheet = next(item for item in sheets if item['sheet'] == sheet_id)
        for row in sheet['rows']:
            columns = {item['cell'].rstrip('0123456789'): item for item in row}
            if columns.get('A', {}).get('value') == row_name:
                return columns
        raise KeyError(row_name)

    try:
        sheets = json.loads((ROOT / 'inputs/reference_cells.json').read_text(encoding='utf-8'))
        waste = find_row(sheets, 'sheet1', 'Очистки овощей')
        method = find_row(sheets, 'sheet2', 'COMPOST')
        landfill, compost = waste['G'], method['D']
        raw_factors = [landfill['value'], compost['value']]
        if any(isinstance(value, bool) for value in raw_factors):
            return None
        baseline, selected = map(float, raw_factors)
        if not all(math.isfinite(value) and value >= 0 for value in (baseline, selected)):
            return None
        method_name = method['B']['value']
        if not isinstance(method_name, str) or not method_name.strip():
            return None
        return {
            'waste_name': waste['A']['value'],
            'method_name': method_name.strip(),
            'factor_tbo': baseline,
            'factor_selected': selected,
            'source': (f'Справочник трека reference.xlsx. Для полигона взята ячейка {landfill["cell"]} '
                       f'листа «Виды отходов», для компостирования — {compost["cell"]} '
                       'листа «Способы утилизации».'),
        }
    except (OSError, ValueError, TypeError, AttributeError, LookupError, StopIteration, OverflowError):
        return None

def reference_recommendations(data=None):
    """Recommended alternatives are distinct from the recorded default TBO."""
    data=data or json.loads((ROOT/'inputs/reference_cells.json').read_text(encoding='utf-8'))
    result={}
    for row in data[0]['rows'][1:]:
        c=cells(row)
        if not c.get('A'):continue
        name=c['A'];recommendation=c.get('F') or ''
        if 'масло' in name.lower() and c.get('D')=='л':method='OIL'
        elif 'Биогаз' in recommendation or 'анаэроб' in recommendation:method='AD'
        elif 'переработ' in recommendation:method='RECYCLE'
        else:method='COMPOST'
        result[name]=method
    return result

def load_catalog(conn):
    data=json.loads((ROOT/'inputs/reference_cells.json').read_text(encoding='utf-8'))
    for index,(name,short,typ,address) in enumerate(ORGANIZATIONS,1):
        conn.execute('INSERT OR IGNORE INTO organizations(id,name,short_name,type,address) VALUES(?,?,?,?,?)',(index,name,short,typ,address))
    methods={}
    for row in data[1]['rows'][1:]:
        c=cells(row)
        if not c.get('A'): continue
        conn.execute('INSERT OR IGNORE INTO methods(code,name,factor,priority,note) VALUES(?,?,?,?,?)',(c['A'],c['B'],c.get('D'),int(c.get('E') or 5),c.get('F') or ''))
        methods[c['A']]=conn.execute('SELECT id FROM methods WHERE code=?',(c['A'],)).fetchone()['id']
    if conn.execute('SELECT COUNT(*) FROM waste_types').fetchone()[0]: return
    for row in data[0]['rows'][1:]:
        c=cells(row)
        if not c.get('A'): continue
        name=c['A']
        rowref=row[0]['cell'][1:]
        source='UK DEFRA/BEIS 2024; предоставленный справочник, Виды отходов!A'+rowref+':J'+rowref+'; версия Track1'
        wid=conn.execute('''INSERT INTO waste_types(name,unit,category,recyclability,default_method_id,
          density_kg_per_l,factor_tbo,source_note,coefficient_source) VALUES(?,?,?,?,?,?,?,?,?)''',
          (name,'l' if c.get('D')=='л' else 'kg',c.get('C') or 'Не указано',
          {'Да':'yes','Частично':'partial','Нет':'no'}.get(c.get('E'),'no'),methods['TBO'],
          '0.92' if c.get('D')=='л' and 'масло' in name.lower() else None,c.get('G'),c.get('J') or '',source)).lastrowid
        orgtext=(c.get('B') or '').lower()
        ids=[]
        if 'тпп' in orgtext: ids.append(1)
        if 'тхипп' in orgtext: ids.append(2)
        if 'atu inn' in orgtext: ids.append(3)
        if 'кофейн' in orgtext: ids.append(4)
        if 'столов' in orgtext: ids.append(5)
        for oid in ids: conn.execute('INSERT OR IGNORE INTO org_waste_types VALUES(?,?)',(oid,wid))

def snapshot(waste,method):
    waste=dict(waste);method=dict(method)
    code=method['code']; unit=waste['unit']; category=waste['category']
    factor=None
    if code=='TBO': factor=waste.get('factor_tbo')
    elif code=='FEED': factor=None
    elif code=='DONATE' and 'нереализован' in waste['name'].lower(): factor='0'
    elif code in ('COMPOST','AD') and category=='Органические': factor=method.get('factor')
    elif code=='OIL' and 'масло' in waste['name'].lower() and unit=='l': factor=method.get('factor')
    elif code=='RECYCLE' and category in ('Вторсырьё','Смешанные'): factor=method.get('factor')
    return {
      'waste_name':waste['name'],'unit':unit,'category':category,'recyclability':waste['recyclability'],
      'density_kg_per_l':float(waste['density_kg_per_l']) if waste.get('density_kg_per_l') is not None else None,
      'factor_tbo':float(waste['factor_tbo']) if waste.get('factor_tbo') is not None else None,
      'factor_selected':float(factor) if factor is not None else None,
      'method_name':method['name'],'method_code':code,'source_note':waste.get('source_note',''),
      'coefficient_source':waste.get('coefficient_source','')+'; '+method.get('note',''),
      'coefficient_version':'Track1-snapshot-v1'}
