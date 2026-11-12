"""Portable, dependency-free XLSX exporter for accepted registry data.

This writes standard OOXML parts with inline strings, typed dates and numbers.
User-provided strings are never emitted as formulas. Exported values come from
the same analytics functions used by the API, without a parallel calculation.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
import math
import re
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

from .analytics import calculate_ecology, row_mass, summarize
from .entry_context import REASON_LABELS
from .metrics import calculate_intensity

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT = "http://schemas.openxmlformats.org/package/2006/content-types"
ET.register_namespace("", MAIN)
ET.register_namespace("r", REL)
_INVALID_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]")


def _clean(value):
    return _INVALID_XML.sub("", str(value))[:32767]


def _tag(name):
    return f"{{{MAIN}}}{name}"


def _col(index):
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _xml(element):
    return ET.tostring(element, encoding="utf-8", xml_declaration=True)


def _cell(parent, row, column, value, style=None):
    attrs = {"r": f"{_col(column)}{row}"}
    if style is not None:
        attrs["s"] = str(style)
    node = ET.SubElement(parent, _tag("c"), attrs)
    if value is None:
        return
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        node.set("s", "3")
        ET.SubElement(node, _tag("v")).text = str((value - date(1899, 12, 30)).days)
    elif isinstance(value, bool):
        node.set("t", "b")
        ET.SubElement(node, _tag("v")).text = "1" if value else "0"
    elif isinstance(value, (int, float, Decimal)):
        if not math.isfinite(float(value)):
            raise ValueError("Экспорт не может содержать бесконечные или нечисловые значения")
        if style is None and not isinstance(value, int):
            node.set("s", "2")
        ET.SubElement(node, _tag("v")).text = str(value)
    else:
        node.set("t", "inlineStr")
        inline = ET.SubElement(node, _tag("is"))
        text = ET.SubElement(inline, _tag("t"))
        text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        text.text = _clean(value)


def _sheet(title, headers, records, note, period, widths=None, footer_rows=None):
    columns = max(len(headers), 2)
    data_last = max(5 + len(records), 5)
    last = data_last + len(footer_rows) + 2 if footer_rows else data_last
    root = ET.Element(_tag("worksheet"))
    ET.SubElement(root, _tag("dimension"), {"ref": f"A1:{_col(columns)}{last}"})
    views = ET.SubElement(root, _tag("sheetViews"))
    view = ET.SubElement(views, _tag("sheetView"), {"workbookViewId": "0", "showGridLines": "1"})
    ET.SubElement(view, _tag("pane"), {"ySplit": "5", "topLeftCell": "A6", "activePane": "bottomLeft", "state": "frozen"})
    ET.SubElement(root, _tag("sheetFormatPr"), {"defaultRowHeight": "17"})
    cols = ET.SubElement(root, _tag("cols"))
    for column in range(1, columns + 1):
        width = (widths or {}).get(column, 19)
        ET.SubElement(cols, _tag("col"), {"min": str(column), "max": str(column), "width": str(width), "customWidth": "1"})
    data = ET.SubElement(root, _tag("sheetData"))
    for index, text in ((1, title), (2, note), (3, period)):
        row = ET.SubElement(data, _tag("row"), {"r": str(index), "ht": "24" if index == 1 else "20", "customHeight": "1"})
        _cell(row, index, 1, text, 4 if index == 1 else 5)
    header = ET.SubElement(data, _tag("row"), {"r": "5", "ht": "36", "customHeight": "1"})
    for column, text in enumerate(headers, 1):
        _cell(header, 5, column, text, 1)
    for row_number, values in enumerate(records, 6):
        row = ET.SubElement(data, _tag("row"), {"r": str(row_number)})
        for column, value in enumerate(values, 1):
            _cell(row, row_number, column, value)
    if records:
        ET.SubElement(root, _tag("autoFilter"), {"ref": f"A5:{_col(len(headers))}{data_last}"})
    merges = ET.SubElement(root, _tag("mergeCells"), {"count": str(3 + 2 * len(footer_rows or []))})
    for row_number in (1, 2, 3):
        ET.SubElement(merges, _tag("mergeCell"), {"ref": f"A{row_number}:{_col(columns)}{row_number}"})
    for row_number, (label, value, unit) in enumerate(footer_rows or [], data_last + 3):
        height = max(36, math.ceil(len(str(value or "")) / 80) * 17) if isinstance(value, str) else 36
        row = ET.SubElement(data, _tag("row"), {"r": str(row_number), "ht": str(height), "customHeight": "1"})
        _cell(row, row_number, 1, label, 5)
        _cell(row, row_number, 5, value, 5 if isinstance(value, str) else None)
        _cell(row, row_number, 9, unit, 5)
        ET.SubElement(merges, _tag("mergeCell"), {"ref": f"A{row_number}:D{row_number}"})
        ET.SubElement(merges, _tag("mergeCell"), {"ref": f"E{row_number}:H{row_number}"})
    ET.SubElement(root, _tag("pageMargins"), {"left": "0.3", "right": "0.3", "top": "0.5", "bottom": "0.5", "header": "0.2", "footer": "0.2"})
    ET.SubElement(root, _tag("pageSetup"), {"paperSize": "9", "orientation": "landscape", "fitToWidth": "1", "fitToHeight": "0"})
    return _xml(root)


def _styles():
    root = ET.Element(_tag("styleSheet"))
    formats = ET.SubElement(root, _tag("numFmts"), {"count": "2"})
    ET.SubElement(formats, _tag("numFmt"), {"numFmtId": "164", "formatCode": "yyyy-mm-dd"})
    ET.SubElement(formats, _tag("numFmt"), {"numFmtId": "165", "formatCode": "#,##0.000###"})
    fonts = ET.SubElement(root, _tag("fonts"), {"count": "3"})
    for bold, size in ((False, 11), (True, 11), (True, 15)):
        font = ET.SubElement(fonts, _tag("font"))
        if bold:
            ET.SubElement(font, _tag("b"))
        ET.SubElement(font, _tag("sz"), {"val": str(size)})
        ET.SubElement(font, _tag("name"), {"val": "Calibri"})
        ET.SubElement(font, _tag("family"), {"val": "2"})
    fills = ET.SubElement(root, _tag("fills"), {"count": "3"})
    ET.SubElement(ET.SubElement(fills, _tag("fill")), _tag("patternFill"), {"patternType": "none"})
    ET.SubElement(ET.SubElement(fills, _tag("fill")), _tag("patternFill"), {"patternType": "gray125"})
    solid = ET.SubElement(ET.SubElement(fills, _tag("fill")), _tag("patternFill"), {"patternType": "solid"})
    ET.SubElement(solid, _tag("fgColor"), {"rgb": "FFE2F1E8"})
    ET.SubElement(solid, _tag("bgColor"), {"indexed": "64"})
    borders = ET.SubElement(root, _tag("borders"), {"count": "1"})
    border = ET.SubElement(borders, _tag("border"))
    for side in ("left", "right", "top", "bottom", "diagonal"):
        ET.SubElement(border, _tag(side))
    base = ET.SubElement(root, _tag("cellStyleXfs"), {"count": "1"})
    ET.SubElement(base, _tag("xf"), {"numFmtId": "0", "fontId": "0", "fillId": "0", "borderId": "0"})
    styles = ET.SubElement(root, _tag("cellXfs"), {"count": "6"})
    for num_format, font, fill, wrap in ((0, 0, 0, False), (0, 1, 2, True), (165, 0, 0, False), (164, 0, 0, False), (0, 2, 0, False), (0, 0, 0, True)):
        item = ET.SubElement(styles, _tag("xf"), {"numFmtId": str(num_format), "fontId": str(font), "fillId": str(fill), "borderId": "0", "xfId": "0", "applyNumberFormat": "1", "applyAlignment": "1"})
        ET.SubElement(item, _tag("alignment"), {"vertical": "top", **({"wrapText": "1"} if wrap else {})})
    cell_styles = ET.SubElement(root, _tag("cellStyles"), {"count": "1"})
    ET.SubElement(cell_styles, _tag("cellStyle"), {"name": "Normal", "xfId": "0", "builtinId": "0"})
    return _xml(root)


def build_xlsx(rows, dashboard, ecology, filters):
    rows = list(rows)
    dashboard = dashboard or summarize(rows)
    ecology = ecology or calculate_ecology(rows)
    filters = dict(filters or {})
    totals = dashboard["totals"]
    intensity = dashboard.get("intensity") or calculate_intensity(rows, dashboard.get("service_days", []))
    if filters.get("demo") is True:
        note = "ДЕМОНСТРАЦИОННЫЕ ДАННЫЕ · Только принятые отчёты · Не фактические результаты АТУ"
    elif filters.get("demo") is False:
        note = "Данные пользователя · Только принятые отчёты · Экология — справочная оценка"
    else:
        note = "Только принятые отчёты · Статус набора данных проверьте в системе"
    period = f"Период: {filters.get('from', '—')} — {filters.get('to', '—')}"
    if filters.get("organization_id"):
        period += f"; организация ID {filters['organization_id']}"
    if filters.get("waste_type_id"):
        period += f"; вид отходов ID {filters['waste_type_id']}"
    if filters.get("method_id"):
        period += f"; способ ID {filters['method_id']}"

    summary_rows = [
        ["Принятых записей", totals["records"], "шт."],
        ["Организаций с данными", totals["organizations"], "шт."],
        ["Исходная масса в килограммах", totals["raw_kg"], "кг"],
        ["Исходный объём отдельно", totals["volume_l"], "л"],
        ["Известная масса с переводом по плотности", totals["known_mass_kg"], "кг"],
        ["Литры без плотности", totals["unconverted_l"], "л"],
        ["Потенциально перерабатываемая известная масса", totals["recyclable_mass_kg"], "кг"],
        ["Частично перерабатываемая известная масса", totals["partial_mass_kg"], "кг"],
        ["Направлено на переработку/компост/биогаз/сбор масла", totals["recycled_mass_kg"], "кг"],
        ["Базовые выбросы рассчитанных строк", ecology["baseline_kg"], "кг CO₂-экв."],
        ["Выбранные способы, рассчитанные строки", ecology["selected_kg"], "кг CO₂-экв."],
        ["Оценка разницы выбросов по справочнику", ecology["difference_kg"], "кг CO₂-экв."],
        ["Покрытие записей экологическим расчётом", ecology["coverage_records_pct"], "%"],
        ["Покрытие известной массы", ecology["coverage_known_mass_pct"], "%"],
        ["Исключённая известная масса без коэффициентов", ecology["excluded_known_mass_kg"], "кг"],
        ["Отходы на 100 порций по всем дням с взвешиваниями", intensity["kg_per_100_portions"], "кг/100 порций"],
        ["Отходы на 100 порций только покрытых дней", intensity["covered_kg_per_100_portions"], "кг/100 порций"],
        ["Дней организаций с взвешиваниями", intensity["total_days"], "дней организаций"],
        ["Покрытых дней организаций с взвешиваниями", intensity["covered_days"], "дней организаций"],
    ]
    org_rows = [[item["name"], item["mass_kg"], item["records"]] for item in dashboard["by_organization"]]
    type_rows = [[item["name"], item["mass_kg"], item["records"]] for item in dashboard["by_type"]]
    # Preserve original units in organization/type summaries as well as detail.
    for group_rows, key, name_key in ((org_rows, "organization_id", "organization_name"), (type_rows, "waste_type_id", "waste_name")):
        groups = dashboard["by_organization"] if key == "organization_id" else dashboard["by_type"]
        for index, group in enumerate(groups):
            subset = [row for row in rows if (row.get(key) == group["id"] if group["id"] is not None else row.get(name_key) == group["name"])]
            local = summarize(subset)["totals"]
            group_rows[index].extend([local["raw_kg"], local["volume_l"], local["unconverted_l"]])

    details = []
    for row, eco in zip(rows, ecology["rows"]):
        try:
            when = date.fromisoformat(str(row["date"])[:10])
        except (ValueError, TypeError, KeyError):
            when = row.get("date", "")
        details.append([
            when, row.get("organization_name", ""), row.get("waste_name", ""), row.get("quantity"),
            "кг" if row.get("unit") == "kg" else "л" if row.get("unit") == "l" else row.get("unit", ""),
            float(row_mass(row)) if row_mass(row) is not None else None,
            row.get("method_name", row.get("method_code", "")), row.get("responsible_name", ""), row.get("report_id"),
            eco["factor_tbo"], eco["factor_selected"], eco["difference_kg"],
            eco["reason"] or "Рассчитано", eco["source"], eco["source_note"],
            REASON_LABELS.get(row.get("reason_code") or "unspecified", row.get("reason_code") or "Не указана"),
            row.get("note") or "",
        ])
    methodology = [["Формула", "масса, кг / 1000 × (коэффициент ТБО − коэффициент выбранного способа)", "кг CO₂-экв."]]
    methodology += [["Коэффициенты", "Кг CO₂-экв. на тонну отходов", "кг CO₂-экв./т"],
                    ["Масло", "1 л ≈ 0,92 кг — допущение исходного справочника", "кг/л"],
                    ["Пропуски", "Неизвестная плотность или коэффициент сохраняются неизвестными; пустые ячейки не означают нулевой след", ""],
                    ["Покрытие", "Покрытие известной массы исключает литры без плотности и не доказывает полноту всей выборки", ""],
                    ["Входной справочник", "Справочники для Трека 1: отходы, утилизация, CO₂; листы «Виды отходов», «Способы утилизации», «Расчёт CO₂ и источники»", ""]]
    methodology.extend([["Ограничение", text, ""] for text in ecology["assumptions"]])
    methodology.extend([
        ["Причины", "Причину указывает сотрудник. Сводка описывает отмеченные категории и не доказывает причинную связь; старые строки без причины обозначены «Не указана».", ""],
        ["Порции", intensity["definition"], "кг/100 порций"],
        ["Покрытие порций", "Полный показатель пуст при хотя бы одном непокрытом дне с взвешиваниями. Частичный показатель использует только покрытые дни; их масса и порции исключают непокрытые дни целиком.", ""],
    ])

    portion_rows = []
    matched_days = set()
    for day in intensity["daily"]:
        matched_days.add((day["organization_id"], day["date"]))
        issues = []
        if day["portions"] is None:
            issues.append("Число порций не указано")
        elif day["portions"] == 0:
            issues.append("Указано 0 порций: деление невозможно")
        if day["mass_kg"] is None:
            issues.append("Масса части выбранных строк неизвестна")
        portion_rows.append([
            date.fromisoformat(day["date"]), day["organization_name"], day["portions"],
            day["known_mass_kg"], day["mass_kg"], day["records"],
            "Да" if day["covered"] else "Нет", day["kg_per_100_portions"], "; ".join(issues),
        ])
    for service in dashboard.get("service_days", []):
        key = (service.get("organization_id"), str(service.get("date", ""))[:10])
        if key in matched_days:
            continue
        matched_days.add(key)
        portion_rows.append([
            date.fromisoformat(key[1]), service.get("organization_name", "—"), service.get("portions"),
            None, None, 0, "Нет", None, "Нет взвешиваний: не считается днём с нулевыми отходами",
        ])
    portion_rows.sort(key=lambda item: (item[0], str(item[1])))
    portion_footer = [
        ["Полный показатель", intensity["kg_per_100_portions"], "кг/100 порций"],
        ["Частичный показатель только покрытых дней", intensity["covered_kg_per_100_portions"], "кг/100 порций"],
        ["Известная масса покрытых дней", intensity["covered_mass_kg"], "кг"],
        ["Порции покрытых дней (знаменатель)", intensity["portions"], "порций"],
        ["Дней организаций с взвешиваниями", intensity["total_days"], "дней"],
        ["Покрытых дней организаций", intensity["covered_days"], "дней"],
        ["Дней с неуказанными порциями", intensity["missing_days"], "дней"],
        ["Дней с нулевыми порциями", intensity["zero_portion_days"], "дней"],
        ["Дней с неизвестной массой", intensity["unknown_mass_days"], "дней"],
        ["Дней обслуживания без взвешиваний (исключены)", intensity["service_only_days"], "дней"],
        ["Статус полноты", intensity["message"], ""],
        ["Определение и границы", intensity["definition"], ""],
        ["Пояснение счётчиков", "День может одновременно не иметь порций и содержать неизвестную массу; диагностические счётчики не складываются. Пустой показатель не означает нулевые отходы.", ""],
    ]
    sheets = [
        ("Сводка", "FoodSave · Сводный отчёт", ["Показатель", "Значение", "Единица"], summary_rows, {1: 64, 2: 24, 3: 21}),
        ("По организациям", "Сводка по организациям", ["Организация", "Известная масса, кг", "Записей", "Исходно, кг", "Исходно, л", "Без плотности, л"], org_rows, {1: 58}),
        ("По видам", "Сводка по видам отходов", ["Вид отходов", "Известная масса, кг", "Записей", "Исходно, кг", "Исходно, л", "Без плотности, л"], type_rows, {1: 58}),
        ("Принятые записи", "Реестр принятых взвешиваний", ["Дата", "Организация", "Вид отходов", "Количество", "Единица", "Известная масса, кг", "Способ", "Ответственный", "Отчёт ID", "ТБО, кг CO₂-экв./т", "Способ, кг CO₂-экв./т", "Разница, кг CO₂-экв.", "Статус расчёта", "Источник/версия", "Примечание справочника", "Причина, указанная сотрудником", "Комментарий к взвешиванию"], details, {1: 14, 2: 42, 3: 46, 7: 42, 8: 28, 13: 48, 14: 50, 15: 65, 16: 32, 17: 65}),
        ("Методика", "Источники и границы расчёта", ["Раздел", "Пояснение", "Единица"], methodology, {1: 28, 2: 110, 3: 24}),
        ("Порции", "Порции и масса по дням организаций", ["Дата", "Организация", "Порций за день", "Известная часть массы, кг", "Полная масса выбранных строк, кг", "Взвешиваний", "Покрытый день", "Кг/100 порций", "Причина исключения"], portion_rows, {1: 14, 2: 42, 4: 23, 5: 25, 8: 22, 9: 65}),
    ]

    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        types = ET.Element(f"{{{CONTENT}}}Types")
        ET.SubElement(types, f"{{{CONTENT}}}Default", {"Extension": "rels", "ContentType": "application/vnd.openxmlformats-package.relationships+xml"})
        ET.SubElement(types, f"{{{CONTENT}}}Default", {"Extension": "xml", "ContentType": "application/xml"})
        for part, content_type in (("/xl/workbook.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"), ("/xl/styles.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml")):
            ET.SubElement(types, f"{{{CONTENT}}}Override", {"PartName": part, "ContentType": content_type})
        workbook = ET.Element(_tag("workbook"))
        sheets_element = ET.SubElement(workbook, _tag("sheets"))
        relationships = ET.Element(f"{{{PKG}}}Relationships")
        for index, (name, title, headers, records, widths) in enumerate(sheets, 1):
            ET.SubElement(types, f"{{{CONTENT}}}Override", {"PartName": f"/xl/worksheets/sheet{index}.xml", "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"})
            ET.SubElement(sheets_element, _tag("sheet"), {"name": name, "sheetId": str(index), f"{{{REL}}}id": f"rId{index}"})
            ET.SubElement(relationships, f"{{{PKG}}}Relationship", {"Id": f"rId{index}", "Type": REL + "/worksheet", "Target": f"worksheets/sheet{index}.xml"})
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _sheet(title, headers, records, note, period, widths, portion_footer if name == "Порции" else None))
        ET.SubElement(relationships, f"{{{PKG}}}Relationship", {"Id": "rIdStyles", "Type": REL + "/styles", "Target": "styles.xml"})
        root_relationship = ET.Element(f"{{{PKG}}}Relationships")
        ET.SubElement(root_relationship, f"{{{PKG}}}Relationship", {"Id": "rId1", "Type": REL + "/officeDocument", "Target": "xl/workbook.xml"})
        archive.writestr("[Content_Types].xml", _xml(types))
        archive.writestr("_rels/.rels", _xml(root_relationship))
        archive.writestr("xl/workbook.xml", _xml(workbook))
        archive.writestr("xl/_rels/workbook.xml.rels", _xml(relationships))
        archive.writestr("xl/styles.xml", _styles())
    return buffer.getvalue()
