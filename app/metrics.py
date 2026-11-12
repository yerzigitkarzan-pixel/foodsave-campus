"""Comparable waste intensity from explicitly matched organization-days.

The caller supplies authorized measurements and daily portion counts. A missing
measurement day is not interpreted as zero waste, and portion counts are never
repeated for each measurement, waste type or disposal method.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal


INTENSITY_DEFINITION = (
    "Кг на 100 порций = масса выбранных взвешиваний / число порций соответствующих "
    "дней организаций × 100. Порции каждого дня организации учитываются один раз. "
    "Покрытый день содержит взвешивания, положительное число порций и известную "
    "массу всех выбранных строк. Дни без взвешиваний не считаются днями с нулевыми отходами."
)


def _key(row):
    when = date.fromisoformat(str(row.get("date", ""))[:10]).isoformat()
    oid = row.get("organization_id")
    organization = ("id", oid) if oid is not None else ("name", str(row.get("organization_name", "—")))
    return organization, when


def calculate_intensity(rows, service_days) -> dict:
    """Return a full rate only when every measured organization-day is covered.

    Unknown mass disqualifies the whole matched day, including its denominator.
    Missing and zero portion counts are distinct; diagnostic counts may overlap
    with unknown-mass days. Service-only days never enter the rate or coverage.
    """
    # Imported here so analytics can stay independently usable and can later
    # expose this helper without a circular module import.
    from .analytics import _decimal, _number, row_mass

    measured = {}
    for row in rows:
        key = _key(row)
        day = measured.setdefault(key, {
            "organization_id": row.get("organization_id"),
            "organization_name": row.get("organization_name", "—"),
            "date": key[1], "known_mass_kg": Decimal(0),
            "unknown_mass_records": 0, "records": 0,
        })
        mass = row_mass(row)
        day["records"] += 1
        if mass is None:
            day["unknown_mass_records"] += 1
        else:
            day["known_mass_kg"] += mass

    portions_by_day = {}
    for service in service_days or []:
        key = _key(service)
        amount = _decimal(service.get("portions"), name="Порций за день", nullable=True)
        if amount is not None and (amount < 0 or amount != amount.to_integral_value()):
            raise ValueError("Порций за день: требуется неотрицательное целое число")
        amount = int(amount) if amount is not None else None
        if key in portions_by_day and portions_by_day[key] != amount:
            raise ValueError("У дня организации есть противоречащие друг другу значения порций")
        portions_by_day[key] = amount

    daily = []
    by_organization = defaultdict(list)
    for key, source in sorted(measured.items(), key=lambda item: (item[0][1], str(item[0][0]))):
        portions = portions_by_day.get(key)
        mass = source["known_mass_kg"] if not source["unknown_mass_records"] else None
        covered = portions is not None and portions > 0 and mass is not None
        day = {
            **source, "known_mass_kg": _number(source["known_mass_kg"]),
            "mass_kg": _number(mass), "portions": portions, "covered": covered,
            "kg_per_100_portions": _number(mass / portions * 100) if covered else None,
        }
        daily.append(day)
        by_organization[key[0]].append(day)

    def aggregate(days):
        covered = [day for day in days if day["covered"]]
        covered_mass = sum((_decimal(day["mass_kg"]) for day in covered), Decimal(0))
        portions = sum(day["portions"] for day in covered)
        rate = _number(covered_mass / portions * 100) if portions > 0 else None
        complete = bool(days) and len(covered) == len(days)
        if not days:
            message = "Нет дней организаций с взвешиваниями: интенсивность не рассчитана."
        elif complete:
            message = "Показатель рассчитан по всем дням организаций с выбранными взвешиваниями."
        else:
            message = (
                f"Полный показатель не рассчитан: покрыто {len(covered)} из {len(days)} дней организаций "
                "с взвешиваниями. Частичный показатель относится только к покрытым дням."
            )
        return {
            "kg_per_100_portions": rate if complete else None,
            "covered_kg_per_100_portions": rate,
            "covered_mass_kg": _number(covered_mass), "portions": portions,
            "total_days": len(days), "covered_days": len(covered),
            "missing_days": sum(day["portions"] is None for day in days),
            "zero_portion_days": sum(day["portions"] == 0 for day in days),
            "unknown_mass_days": sum(day["mass_kg"] is None for day in days),
            "coverage_days_pct": _number(Decimal(len(covered)) / len(days) * 100, 3) if days else None,
            "complete": complete, "message": message,
        }

    organizations = []
    for days in by_organization.values():
        organizations.append({
            "organization_id": days[0]["organization_id"],
            "organization_name": days[0]["organization_name"], **aggregate(days),
        })
    organizations.sort(key=lambda item: (str(item["organization_name"]), str(item["organization_id"])))
    return {
        **aggregate(daily), "daily": daily, "by_organization": organizations,
        "service_only_days": len(set(portions_by_day) - set(measured)),
        "definition": INTENSITY_DEFINITION,
    }
