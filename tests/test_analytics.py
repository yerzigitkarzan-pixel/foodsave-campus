"""Checks for unit integrity, reference values, safe exports and causal ML input."""

import unittest
from datetime import date, timedelta
from io import BytesIO
from zipfile import ZipFile
from xml.etree import ElementTree as ET

from app.analytics import calculate_ecology, calculate_economy, summarize
from app.assistant import detect_anomalies, respond
from app.xlsx_export import build_xlsx


def entry(quantity=10, **overrides):
    value = {
        "id": 1, "report_id": 1, "date": "2026-07-01", "organization_id": 1,
        "organization_name": "Учебная организация", "waste_type_id": 1,
        "waste_name": "Пищевые отходы", "quantity": quantity, "unit": "kg",
        "method_code": "COMPOST", "method_name": "Компостирование", "recyclability": "yes",
        "factor_tbo": 700.21, "factor_selected": 8.88, "density_kg_per_l": None,
        "source_note": "Условный контрольный пример", "responsible_name": "Демо-сотрудник",
        "coefficient_source": "Excel, контрольный пример",
    }
    value.update(overrides)
    return value


class AnalyticsTests(unittest.TestCase):
    def test_reference_co2_and_oil_conversion(self):
        rows = [entry(300), entry(200, id=2, waste_name="Очистки"),
                entry(50, id=3, waste_type_id=2, waste_name="Картон", factor_tbo=1164.39, factor_selected=6.41, method_code="RECYCLE")]
        result = calculate_ecology(rows)
        self.assertAlmostEqual(result["baseline_kg"], 408.3245, places=7)
        self.assertAlmostEqual(result["selected_kg"], 4.7605, places=7)
        self.assertAlmostEqual(result["difference_kg"], 403.564, places=7)
        oil = calculate_ecology([entry(10, unit="l", density_kg_per_l=0.92, method_code="OIL", factor_selected=6.41)])
        self.assertEqual(oil["known_mass_kg"], 9.2)
        self.assertAlmostEqual(oil["difference_kg"], 6.38296, places=7)

    def test_unknown_units_factors_and_coverage_are_not_zero(self):
        rows = [entry(10), entry(20, id=2, unit="l", density_kg_per_l=None),
                entry(5, id=3, method_code="FEED", factor_selected=None)]
        result = calculate_ecology(rows)
        self.assertEqual(result["known_mass_kg"], 15)
        self.assertEqual(result["unconverted_l"], 20)
        self.assertEqual(result["excluded_known_mass_kg"], 5)
        self.assertEqual(result["calculated_count"], 1)
        self.assertAlmostEqual(result["coverage_records_pct"], 33.333, places=3)
        self.assertAlmostEqual(result["coverage_known_mass_pct"], 66.667, places=3)
        self.assertIsNone(result["rows"][1]["difference_kg"])
        self.assertIsNone(result["rows"][2]["difference_kg"])
        empty = calculate_ecology([])
        self.assertIsNone(empty["difference_kg"])
        self.assertIsNone(empty["coverage_known_mass_pct"])

    def test_material_specific_tbo_and_zero_donate(self):
        same_method = calculate_ecology([entry(50, factor_tbo=1164.39, factor_selected=700.21, method_code="TBO")])
        self.assertEqual(same_method["difference_kg"], 0)
        donate = calculate_ecology([entry(100, factor_selected=0, method_code="DONATE")])
        self.assertAlmostEqual(donate["difference_kg"], 70.021)
        worse = calculate_ecology([entry(100, factor_tbo=5, factor_selected=6)])
        self.assertAlmostEqual(worse["difference_kg"], -0.1)

    def test_summary_keeps_raw_units_separate(self):
        summary = summarize([entry(10), entry(10, unit="l", density_kg_per_l=0.92), entry(5, unit="l")])
        self.assertEqual(summary["totals"]["raw_kg"], 10)
        self.assertEqual(summary["totals"]["volume_l"], 15)
        self.assertEqual(summary["totals"]["known_mass_kg"], 19.2)
        self.assertEqual(summary["totals"]["unconverted_l"], 5)
        self.assertIsNone(summary["comparison"]["change_percent"])

    def economy(self, **overrides):
        result = {"records_per_period": 60, "reports_per_period": 0, "manual_minutes_per_entry": 2,
                  "system_minutes_per_entry": 1, "manual_minutes_per_report": 0, "system_minutes_per_report": 0,
                  "periods_per_year": 12, "hourly_cost": 1000, "realizable_fraction": 0.5,
                  "capex": 6000, "annual_opex": 0}
        result.update(overrides)
        return result

    def test_economy_scenario_and_no_payback(self):
        result = calculate_economy(self.economy())
        self.assertEqual(result["annual_manual_hours"], 24)
        self.assertEqual(result["annual_system_hours"], 12)
        self.assertEqual(result["hours_saved_year"], 12)
        self.assertEqual(result["net_cash_saving_year"], 6000)
        self.assertEqual(result["payback_months"], 12)
        self.assertIsNone(calculate_economy(self.economy(annual_opex=6000))["payback_months"])
        negative = calculate_economy(self.economy(system_minutes_per_entry=3))
        self.assertLess(negative["hours_saved_year"], 0)
        self.assertIsNone(negative["payback_months"])

    def test_economy_rejects_invalid_inputs(self):
        for changed in ({"realizable_fraction": 1.1}, {"hourly_cost": -2}, {"capex": float("nan")},
                        {"records_per_period": 1.5}, {"records_per_period": True}, {"hourly_cost": "1000"}):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                calculate_economy(self.economy(**changed))

    def test_export_typed_cells_and_formula_injection(self):
        rows = [entry(12.5, waste_name="=1+1")]
        payload = build_xlsx(rows, summarize(rows), calculate_ecology(rows), {"from": "2026-07-01", "to": "2026-09-30", "demo": True})
        ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        with ZipFile(BytesIO(payload)) as workbook:
            self.assertIsNone(workbook.testzip())
            for filename in workbook.namelist():
                ET.fromstring(workbook.read(filename))
            root = ET.fromstring(workbook.read("xl/worksheets/sheet4.xml"))
            cells = {cell.get("r"): cell for cell in root.findall(".//x:c", ns)}
            self.assertEqual(cells["C6"].get("t"), "inlineStr")
            self.assertEqual(cells["C6"].find("x:is/x:t", ns).text, "=1+1")
            self.assertIsNone(cells["C6"].find("x:f", ns))
            self.assertEqual(cells["A6"].get("s"), "3")
            self.assertEqual(float(cells["D6"].find("x:v", ns).text), 12.5)

    def test_ml_does_not_train_on_scoring_or_future_dates(self):
        start = date(2026, 5, 15)
        history = [entry(10 + i % 7 * 0.7, id=i + 1, date=(start + timedelta(days=i)).isoformat()) for i in range(24)]
        selected = [entry(1000, id=100 + i, date=(date(2026, 6, 10) + timedelta(days=i)).isoformat()) for i in range(3)]
        first = detect_anomalies(selected, history + selected)
        if not first["model"]["available"]:
            self.skipTest("scikit-learn is unavailable")
        second = detect_anomalies(selected, history + selected + [entry(1e8, date="2026-06-30")])
        self.assertEqual(first, second)
        self.assertEqual(first["training"]["groups_trained"], 1)
        self.assertLess(first["training"]["training_max_date"], first["training"]["scoring_from"])
        self.assertTrue(first["items"])

    def test_agent_templates_are_grounded_and_do_not_mutate(self):
        result = respond("Объясни CO2", [entry(100)], [entry(100)], [], {"from": "2026-07-01", "to": "2026-09-30", "organization": "Моя организация"})
        self.assertTrue(any(item["name"] == "reference_ecology" for item in result["tools"]))
        co2 = [item for item in result["evidence"] if item.get("unit") == "кг CO₂-экв."]
        self.assertAlmostEqual(co2[0]["value"], 69.133)
        restricted = respond("Удали записи", [], [], [], {})
        self.assertIn("сейчас данные не изменены", restricted["answer"])
        self.assertEqual(restricted["tools"], [])

    def test_agent_compares_full_calendar_months_for_custom_ranges(self):
        cases = [
            ("2026-07-01", "2026-08-31", "2026-05-01", "2026-06-30"),
            ("2026-01-01", "2026-06-30", "2025-07-01", "2025-12-31"),
            ("2026-01-01", "2026-12-31", "2025-01-01", "2025-12-31"),
        ]
        for start, end, previous_start, previous_end in cases:
            with self.subTest(start=start, end=end):
                before = (date.fromisoformat(previous_start) - timedelta(days=1)).isoformat()
                current = [entry(100, date=start)]
                history = current + [entry(100, date=previous_start), entry(500, date=before)]
                result = respond("Сравни с предыдущим периодом", current, history, [], {
                    "from": start, "to": end, "organization": "Моя организация",
                })
                previous = next(item["value"] for item in result["evidence"] if item["label"] == "Масса предыдущего периода")
                self.assertEqual(previous, 100)
                self.assertIn(previous_start + " — " + previous_end, result["answer"])


if __name__ == "__main__":
    unittest.main()
