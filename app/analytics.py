"""Pure, auditable analytics over rows already scoped by the API.

Amounts are calculated with Decimal. JSON-facing values are finite numbers;
unknown mass or emission factors remain None rather than becoming zero.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import math
from typing import Any, Iterable, Mapping

from .entry_context import REASON_LABELS

D = Decimal
ZERO = D("0")
RECYCLED_METHODS = frozenset({"RECYCLE", "OIL", "AD", "COMPOST"})


def _decimal(value: Any, *, name: str = "Значение", nullable: bool = False) -> Decimal | None:
    if value is None or value == "":
        if nullable:
            return None
        raise ValueError(f"{name}: значение обязательно")
    if isinstance(value, bool):
        raise ValueError(f"{name}: требуется число")
    try:
        number = D(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{name}: требуется корректное число") from exc
    if not number.is_finite():
        raise ValueError(f"{name}: число должно быть конечным")
    return number


def _number(value: Decimal | int | None, places: int | None = None) -> float | None:
    if value is None:
        return None
    number = D(value)
    if places is not None:
        try:
            number = number.quantize(D(1).scaleb(-places), rounding=ROUND_HALF_UP)
        except InvalidOperation as exc:
            raise ValueError("Результат слишком велик для расчёта") from exc
    converted = float(number)
    if not math.isfinite(converted):
        raise ValueError("Результат слишком велик для расчёта")
    return converted


def row_mass(row: Mapping[str, Any]) -> Decimal | None:
    """Known kilograms, preserving unknown density for original litres."""
    quantity = _decimal(row.get("quantity"), name="Количество")
    if quantity < 0:
        raise ValueError("Количество не может быть отрицательным")
    unit = row.get("unit", row.get("unit_snapshot"))
    if unit in ("kg", "кг"):
        return quantity
    if unit in ("l", "л"):
        density = _decimal(row.get("density_kg_per_l"), name="Плотность", nullable=True)
        if density is None:
            return None
        if density <= 0:
            raise ValueError("Плотность должна быть положительной")
        return quantity * density
    return None


def summarize(rows: Iterable[Mapping[str, Any]], previous_rows=None) -> dict:
    rows = list(rows)
    previous_rows = list(previous_rows or [])
    raw_kg = volume_l = unconverted_l = mass = recyclable = partial = recycled = ZERO
    monthly = defaultdict(lambda: ZERO)
    daily = defaultdict(lambda: {"kg": ZERO, "l": ZERO})
    types: dict[Any, dict] = {}
    organizations: dict[Any, dict] = {}
    reasons: dict[str, dict] = {}

    for row in rows:
        quantity = _decimal(row.get("quantity"), name="Количество")
        unit = row.get("unit", row.get("unit_snapshot"))
        known_mass = row_mass(row)
        reason_code = row.get("reason_code") or "unspecified"
        reason = reasons.setdefault(reason_code, {
            "code": reason_code, "label": REASON_LABELS.get(reason_code, str(reason_code)),
            "raw_kg": ZERO, "volume_l": ZERO, "known_mass_kg": ZERO, "records": 0,
        })
        reason["records"] += 1
        if unit in ("kg", "кг"):
            reason["raw_kg"] += quantity
        elif unit in ("l", "л"):
            reason["volume_l"] += quantity
        if known_mass is not None:
            reason["known_mass_kg"] += known_mass
        day = str(row.get("date", ""))[:10]
        month = day[:7]
        if unit in ("kg", "кг"):
            raw_kg += quantity
            daily[day]["kg"] += quantity
        elif unit in ("l", "л"):
            volume_l += quantity
            daily[day]["l"] += quantity
            if known_mass is None:
                unconverted_l += quantity
        oid = row.get("organization_id")
        wid = row.get("waste_type_id")
        # An absent identifier must not merge distinct labelled categories.
        ok = oid if oid is not None else str(row.get("organization_name", "—"))
        wk = wid if wid is not None else str(row.get("waste_name", "—"))
        org = organizations.setdefault(ok, {"id": oid, "name": row.get("organization_name", "—"), "mass_kg": ZERO, "records": 0})
        waste = types.setdefault(wk, {"id": wid, "name": row.get("waste_name", "—"), "mass_kg": ZERO, "records": 0})
        org["records"] += 1
        waste["records"] += 1
        monthly[month] += known_mass or ZERO
        if known_mass is None:
            continue
        mass += known_mass
        org["mass_kg"] += known_mass
        waste["mass_kg"] += known_mass
        if row.get("recyclability") in ("yes", "Да"):
            recyclable += known_mass
        elif row.get("recyclability") in ("partial", "Частично"):
            partial += known_mass
        if row.get("method_code") in RECYCLED_METHODS:
            recycled += known_mass

    def groups(mapping):
        return [{**item, "mass_kg": _number(item["mass_kg"])} for item in sorted(mapping.values(), key=lambda item: (-item["mass_kg"], str(item["name"])))]

    previous_mass = sum((row_mass(row) or ZERO for row in previous_rows), ZERO)
    previous_dates = sorted(str(row.get("date", ""))[:10] for row in previous_rows if row.get("date"))
    change = (mass - previous_mass) / previous_mass * 100 if previous_mass > 0 else None
    return {
        "totals": {
            "known_mass_kg": _number(mass), "raw_kg": _number(raw_kg),
            "volume_l": _number(volume_l), "unconverted_l": _number(unconverted_l),
            "records": len(rows), "organizations": len(organizations),
            "recyclable_mass_kg": _number(recyclable), "partial_mass_kg": _number(partial),
            "recycled_mass_kg": _number(recycled),
        },
        "monthly": [{"label": key, "mass_kg": _number(value)} for key, value in sorted(monthly.items())],
        "daily": [{"date": key, "kg": _number(value["kg"]), "l": _number(value["l"])} for key, value in sorted(daily.items())],
        "by_type": groups(types), "by_organization": groups(organizations),
        "by_reason": [
            {**item, **{key: _number(item[key]) for key in ("raw_kg", "volume_l", "known_mass_kg")}}
            for item in sorted(reasons.values(), key=lambda item: (-item["known_mass_kg"], str(item["label"])))
        ],
        "comparison": {
            "current_mass_kg": _number(mass), "previous_mass_kg": _number(previous_mass),
            "change_percent": _number(change, 3),
            "previous_from": previous_dates[0] if previous_dates else None,
            "previous_to": previous_dates[-1] if previous_dates else None,
        },
    }


def calculate_ecology(rows: Iterable[Mapping[str, Any]]) -> dict:
    rows = list(rows)
    baseline = selected = known_mass = calculated_mass = unknown_l = ZERO
    calculated_count = 0
    details = []
    notes = [
        "Оценка изменения способа обращения с отходами, не полный жизненный цикл продуктов.",
        "Коэффициенты предоставленного справочника: кг CO₂-экв. на тонну. Масса в кг делится на 1000.",
        "UK DEFRA/BEIS 2024 и Climatiq указаны в исходном Excel. Применимость к Казахстану ориентировочная; коэффициенты не верифицированы на площадке АТУ.",
        "Передача пригодной еды с коэффициентом 0 — допущение границ справочника, а не нулевой полный углеродный след.",
    ]
    for row in rows:
        mass = row_mass(row)
        unit = row.get("unit", row.get("unit_snapshot"))
        if mass is not None:
            known_mass += mass
        elif unit in ("l", "л"):
            unknown_l += _decimal(row.get("quantity"), name="Количество")
        fb = _decimal(row.get("factor_tbo"), name="Коэффициент ТБО", nullable=True)
        fs = _decimal(row.get("factor_selected"), name="Коэффициент способа", nullable=True)
        if fb is not None and fb < 0 or fs is not None and fs < 0:
            raise ValueError("Экологический коэффициент не может быть отрицательным")
        # TBO is material-specific; the generic methods row must never override it.
        if row.get("method_code") == "TBO":
            fs = fb
        can_calculate = mass is not None and fb is not None and fs is not None
        b = mass / 1000 * fb if can_calculate else None
        s = mass / 1000 * fs if can_calculate else None
        if can_calculate:
            baseline += b
            selected += s
            calculated_mass += mass
            calculated_count += 1
        reason = None if can_calculate else ("Не рассчитано: нет плотности для перевода литров в кг" if mass is None else "Не рассчитано: нет коэффициента для выбранного материала и способа")
        details.append({
            "id": row.get("id"), "date": row.get("date"),
            "organization_name": row.get("organization_name", "—"),
            "waste_name": row.get("waste_name", "—"), "method_code": row.get("method_code"),
            "method_name": row.get("method_name", row.get("method_code", "—")),
            "quantity": _number(_decimal(row.get("quantity"))), "unit": unit,
            "mass_kg": _number(mass), "density_kg_per_l": row.get("density_kg_per_l"),
            "factor_tbo": _number(fb), "factor_selected": _number(fs),
            "baseline_kg": _number(b), "selected_kg": _number(s),
            "difference_kg": _number(b - s) if can_calculate else None,
            "calculated": can_calculate, "reason": reason,
            "source": row.get("coefficient_source") or "Предоставленный Excel: «Виды отходов» и «Способы утилизации»",
            "source_note": row.get("source_note", ""),
        })
        note = str(row.get("source_note") or "").strip()
        if note and ("допущ" in note.lower() or "0,92" in note or "0.92" in note) and note not in notes:
            notes.append(note)
    if unknown_l:
        notes.append("Есть литры без плотности: покрытие известной массы не отражает полноту всей выборки.")
    return {
        "baseline_kg": _number(baseline) if calculated_count else None,
        "selected_kg": _number(selected) if calculated_count else None,
        "difference_kg": _number(baseline - selected) if calculated_count else None,
        "known_mass_kg": _number(known_mass), "calculated_mass_kg": _number(calculated_mass),
        "excluded_known_mass_kg": _number(known_mass - calculated_mass), "unconverted_l": _number(unknown_l),
        "calculated_count": calculated_count, "total_count": len(rows),
        "coverage_records_pct": _number(D(calculated_count) / len(rows) * 100, 3) if rows else None,
        "coverage_known_mass_pct": _number(calculated_mass / known_mass * 100, 3) if known_mass else None,
        "rows": details, "assumptions": notes,
    }


_ECONOMY_LABELS = {
    "records_per_period": "Записей за период", "reports_per_period": "Отчётов за период",
    "manual_minutes_per_entry": "Минут ручного ввода записи", "system_minutes_per_entry": "Минут ввода в системе",
    "manual_minutes_per_report": "Минут ручной обработки отчёта", "system_minutes_per_report": "Минут обработки отчёта в системе",
    "periods_per_year": "Периодов в году", "hourly_cost": "Стоимость часа",
    "realizable_fraction": "Доля денежной реализации", "capex": "CAPEX", "annual_opex": "Годовой OPEX",
}


def calculate_economy(payload: Mapping[str, Any]) -> dict:
    values = {}
    for key, label in _ECONOMY_LABELS.items():
        value = payload.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
            raise ValueError(f"{label}: требуется число")
        number = _decimal(value, name=label)
        if number < 0:
            raise ValueError(f"{label}: значение не может быть отрицательным")
        if key in {"records_per_period", "reports_per_period", "periods_per_year"} and number != number.to_integral_value():
            raise ValueError(f"{label}: требуется целое число")
        values[key] = number
    if values["realizable_fraction"] > 1:
        raise ValueError("Доля денежной реализации должна быть от 0 до 1 (0–100%)")
    v = values
    manual = v["periods_per_year"] * (v["records_per_period"] * v["manual_minutes_per_entry"] + v["reports_per_period"] * v["manual_minutes_per_report"]) / 60
    system = v["periods_per_year"] * (v["records_per_period"] * v["system_minutes_per_entry"] + v["reports_per_period"] * v["system_minutes_per_report"]) / 60
    hours = manual - system
    capacity = hours * v["hourly_cost"]
    cash = capacity * v["realizable_fraction"]
    net = cash - v["annual_opex"]
    payback = v["capex"] / (net / 12) if net > 0 else None
    message = "Сценарная оценка: высвобождённое время не автоматически превращается в денежную экономию."
    if net <= 0:
        message = "При этих допущениях окупаемость не достигается."
    if hours < 0:
        message += " В сценарии обработка в системе занимает больше времени, чем вручную."
    return {
        "annual_manual_hours": _number(manual, 4), "annual_system_hours": _number(system, 4),
        "hours_saved_year": _number(hours, 4), "capacity_value_kzt": _number(capacity, 2),
        "cash_saving_before_opex": _number(cash, 2), "net_cash_saving_year": _number(net, 2),
        "payback_months": _number(payback, 2), "message": message,
        "is_scenario": True, "assumptions": {key: _number(value) for key, value in values.items()},
    }
