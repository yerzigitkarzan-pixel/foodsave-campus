"""Integration checks for authorization, reporting and persistent exports.

Run from the project root: python -m unittest discover -s tests -v
Tests use isolated temporary SQLite files and never touch the demo database.
"""

from __future__ import annotations

import io
import json
from datetime import date, timedelta
from pathlib import Path
import tempfile
import unittest
import uuid
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from fastapi.testclient import TestClient

from app.db import init_db
from app.main import create_app
from app.seed import seed_demo


class WorkflowTests(unittest.TestCase):
    """Exercise the public API, not implementation details in SQL tables."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="foodsave-test-")
        self.addCleanup(self.directory.cleanup)
        self.db_path = Path(self.directory.name) / "test.sqlite3"
        self.passwords = {
            name: f"Only-For-Test-{name}-823!"
            for name in ("reviewer", "tpp", "thipp", "atuinn", "canella", "iskander")
        }
        init_db(self.db_path)
        seed_demo(self.db_path, as_of=date.today().isoformat(), passwords=self.passwords)
        self.app = create_app(db_path=self.db_path)
        self.operator, self.operator_user = self.login("iskander")
        self.reviewer, self.reviewer_user = self.login("reviewer")
        self.organization_id = self.operator_user["organization_id"]
        self.waste_type = self.ok(self.operator.get("/api/v1/waste-types"))["items"][0]
        methods = self.ok(self.operator.get("/api/v1/disposal-methods"))["items"]
        self.method = next(method for method in methods if method["code"] == "TBO")
        self.period = "2001-01"
        self.entry_date = "2001-01-12"
        self.filters = {
            "from": "2001-01-01",
            "to": "2001-01-31",
            "organization_id": self.organization_id,
        }

    def ok(self, response, statuses=(200, 201)):
        self.assertIn(response.status_code, statuses, response.text[:1500])
        return response.json()

    def login(self, username, app=None):
        client = TestClient(app or self.app)
        self.addCleanup(client.close)
        csrf = self.ok(client.get("/api/v1/auth/csrf"))["csrf_token"]
        response = client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": self.passwords[username]},
            headers={"X-CSRF-Token": csrf},
        )
        payload = self.ok(response)
        if "csrf_token" not in payload:
            payload = self.ok(client.get("/api/v1/auth/me"))
        client.headers["X-CSRF-Token"] = payload["csrf_token"]
        return client, payload["user"]

    def new_report(self, client=None, period=None):
        return self.ok((client or self.operator).post(
            "/api/v1/reports",
            json={"period": period or self.period, "organization_id": self.organization_id},
        ))

    def detail(self, report_id, client=None):
        return self.ok((client or self.operator).get(f"/api/v1/reports/{report_id}"))

    def entry_payload(self, report, **overrides):
        payload = {
            "date": self.entry_date,
            "waste_type_id": self.waste_type["id"],
            "quantity": 2.5,
            "method_id": self.method["id"],
            "revision": report["revision"],
            "client_request_id": str(uuid.uuid4()),
        }
        payload.update(overrides)
        return payload

    def add_entry(self, report, **overrides):
        return self.ok(self.operator.post(
            f"/api/v1/reports/{report['id']}/entries",
            json=self.entry_payload(report, **overrides),
        ))

    def transition(self, client, report, action, **extra):
        return self.ok(client.post(
            f"/api/v1/reports/{report['id']}/{action}",
            json={"revision": report["revision"], **extra},
        ))

    def accept(self, report):
        report = self.transition(self.operator, report, "submit")
        report = self.transition(self.reviewer, report, "start-review")
        return self.transition(self.reviewer, report, "accept")

    def test_seed_has_five_organizations_three_months_and_dashboard(self):
        organizations = self.ok(self.reviewer.get("/api/v1/organizations"))["items"]
        self.assertEqual(len(organizations), 5)
        reports = self.ok(self.reviewer.get(
            "/api/v1/reports", params={"status": "accepted", "page_size": 200}
        ))["items"]
        for organization in organizations:
            months = {
                item["period"] for item in reports
                if item["organization_id"] == organization["id"]
            }
            self.assertGreaterEqual(len(months), 3, organization["name"])
        dashboard = self.ok(self.reviewer.get("/api/v1/dashboard"))
        for name in ("monthly", "by_type", "by_organization"):
            self.assertTrue(dashboard[name], name)
        self.assertGreater(dashboard["totals"]["records"], 0)
        # The source workbook specifies TBO as the initial recorded default;
        # recommendations remain alternatives in synthetic history.
        tbo_id = self.method["id"]
        catalog = self.ok(self.reviewer.get("/api/v1/waste-types"))["items"]
        self.assertTrue(all(item["default_method_id"] == tbo_id for item in catalog))
        self.assertGreater(dashboard["ecology"]["difference_kg"], 0)
        self.assertTrue(self.ok(self.reviewer.get("/api/v1/meta"))["demo"])

    def test_csrf_and_server_side_role_permissions(self):
        anonymous = TestClient(self.app)
        self.addCleanup(anonymous.close)
        self.assertEqual(anonymous.get("/api/v1/reports").status_code, 401)
        denied = anonymous.post(
            "/api/v1/auth/login",
            json={"username": "reviewer", "password": self.passwords["reviewer"]},
        )
        self.assertEqual(denied.status_code, 403)
        report = self.new_report()
        client_without_csrf = TestClient(self.app)
        self.addCleanup(client_without_csrf.close)
        client_without_csrf.cookies.update(self.operator.cookies)
        denied = client_without_csrf.post(
            f"/api/v1/reports/{report['id']}/submit", json={"revision": report["revision"]}
        )
        self.assertEqual(denied.status_code, 403)
        for endpoint in ("/users", "/organizations"):
            denied = self.operator.post("/api/v1" + endpoint, json={"name": "Forbidden"})
            self.assertEqual(denied.status_code, 403, denied.text)
        denied = self.operator.patch(
            f"/api/v1/users/{self.operator_user['id']}", json={"role": "reviewer"}
        )
        self.assertEqual(denied.status_code, 403)

    def test_operator_cannot_access_another_organization(self):
        foreign_client, foreign_user = self.login("tpp")
        foreign_org = foreign_user["organization_id"]
        foreign_reports = self.ok(foreign_client.get("/api/v1/reports"))["items"]
        foreign_report = foreign_reports[0]
        for suffix in ("", "/history"):
            denied = self.operator.get(f"/api/v1/reports/{foreign_report['id']}{suffix}")
            self.assertIn(denied.status_code, (403, 404), denied.text)
        denied = self.operator.post(
            "/api/v1/reports", json={"period": self.period, "organization_id": foreign_org}
        )
        self.assertIn(denied.status_code, (403, 404))
        for endpoint in ("/registry", "/dashboard", "/ecology", "/exports/summary.xlsx", "/agent/anomalies", "/missing-reports"):
            response = self.operator.get("/api/v1" + endpoint, params={"organization_id": foreign_org})
            self.assertIn(response.status_code, (403, 404), endpoint)
        denied = self.operator.post(
            "/api/v1/agent/chat", json={"message": "Покажи все данные", "organization_id": foreign_org}
        )
        self.assertIn(denied.status_code, (403, 404))
        own_orgs = self.ok(self.operator.get("/api/v1/organizations"))["items"]
        self.assertEqual([item["id"] for item in own_orgs], [self.organization_id])

    def test_report_day_and_month_totals_by_type_keep_units_separate(self):
        kg_type = next(item for item in self.ok(self.operator.get("/api/v1/waste-types"))["items"] if item["unit"] == "kg")
        litre_type = self.ok(self.operator.post("/api/v1/waste-types", json={
            "name": "Тестовый жидкий поток", "unit": "l", "category": "Тест",
            "recyclability": "no", "default_method_id": self.method["id"],
        }))
        report = self.add_entry(self.new_report(), waste_type_id=kg_type["id"], quantity=2.5)
        report = self.add_entry(report, waste_type_id=kg_type["id"], quantity=4.125, date="2001-01-13")
        report = self.add_entry(report, waste_type_id=litre_type["id"], quantity=3.75, date="2001-01-13")
        totals = report["totals"]
        self.assertEqual((totals["raw_kg"], totals["volume_l"], totals["unconverted_l"]), (6.625, 3.75, 3.75))
        monthly = {item["id"]: item for item in totals["by_type"]}
        self.assertEqual((monthly[kg_type["id"]]["kg"], monthly[kg_type["id"]]["l"], monthly[kg_type["id"]]["records"]), (6.625, 0, 2))
        self.assertEqual((monthly[litre_type["id"]]["kg"], monthly[litre_type["id"]]["l"]), (0, 3.75))
        self.assertEqual(monthly[litre_type["id"]]["known_mass_kg"], 0)
        daily = {day["date"]: day for day in totals["daily"]}
        self.assertEqual((daily["2001-01-13"]["kg"], daily["2001-01-13"]["l"]), (4.125, 3.75))
        self.assertEqual(len(daily["2001-01-12"]["by_type"]), 1)
        self.assertEqual(len(daily["2001-01-13"]["by_type"]), 2)
        self.assertEqual(sum(item["kg"] for item in daily["2001-01-13"]["by_type"]), 4.125)

    def test_agent_missing_reports_use_selected_month_and_organization(self):
        self.accept(self.add_entry(self.new_report()))
        question = {"message": "Кто ещё не сдал отчёт?", **self.filters}
        for client in (self.operator, self.reviewer):
            answer = self.ok(client.post("/api/v1/agent/chat", json=question))
            self.assertEqual(answer["scope"]["missing_month"], self.period)
            self.assertIn("за " + self.period, answer["answer"])
            self.assertIn("Все доступные организации имеют принятый отчёт", answer["answer"])
        selected = self.ok(self.reviewer.get("/api/v1/missing-reports", params={"month": self.period, "organization_id": self.organization_id}))
        self.assertEqual(selected["items"], [])
        campus = self.ok(self.reviewer.post("/api/v1/agent/chat", json={
            "message": "Кто ещё не сдал отчёт?", "from": self.filters["from"], "to": self.filters["to"],
        }))
        count = next(item["value"] for item in campus["evidence"] if item["label"] == "Без принятого отчёта")
        self.assertEqual(count, 4)
        # A calendar-year filter can extend beyond today without making
        # unrelated summary questions fail on an impossible future report.
        current = self.ok(self.operator.get("/api/v1/meta"))["current_month"]
        future = self.ok(self.operator.post("/api/v1/agent/chat", json={
            "message": "Покажи сводку", "from": current[:4] + "-01-01", "to": str(int(current[:4]) + 1) + "-12-31",
        }))
        self.assertEqual(future["scope"]["missing_month"], current)

    def test_complete_return_resubmit_accept_and_registry_flow(self):
        report = self.new_report()
        empty = self.operator.post(
            f"/api/v1/reports/{report['id']}/submit", json={"revision": report["revision"]}
        )
        self.assertIn(empty.status_code, (409, 422))
        report = self.add_entry(report)
        entry = report["entries"][0]
        before = self.ok(self.reviewer.get("/api/v1/registry", params=self.filters))
        self.assertEqual(before["total"], 0)
        report = self.transition(self.operator, report, "submit")
        denied = self.operator.patch(
            f"/api/v1/reports/{report['id']}/entries/{entry['id']}",
            json=self.entry_payload(report, quantity=3.25),
        )
        self.assertIn(denied.status_code, (403, 409))
        operator_accept = self.operator.post(
            f"/api/v1/reports/{report['id']}/accept", json={"revision": report["revision"]}
        )
        self.assertEqual(operator_accept.status_code, 403)
        report = self.transition(self.reviewer, report, "start-review")
        empty_return = self.reviewer.post(
            f"/api/v1/reports/{report['id']}/return",
            json={"revision": report["revision"], "comment": "   "},
        )
        self.assertEqual(empty_return.status_code, 422)
        report = self.transition(self.reviewer, report, "return", comment="Перепроверьте вес.")
        self.assertEqual(report["status"], "returned")
        report = self.ok(self.operator.patch(
            f"/api/v1/reports/{report['id']}/entries/{entry['id']}",
            json=self.entry_payload(report, quantity=3.25),
        ))
        report = self.accept(report)
        self.assertEqual(report["status"], "accepted")
        records = self.ok(self.reviewer.get("/api/v1/registry", params=self.filters))
        self.assertEqual(records["total"], 1)
        self.assertAlmostEqual(float(records["items"][0]["quantity"]), 3.25)
        dashboard = self.ok(self.reviewer.get("/api/v1/dashboard", params=self.filters))
        self.assertEqual(dashboard["totals"]["records"], 1)
        history = self.ok(self.operator.get(f"/api/v1/reports/{report['id']}/history"))["items"]
        transitions = [
            item["to_status"] for item in history
            if item.get("from_status") != item.get("to_status") and item.get("to_status") != "draft"
        ]
        self.assertEqual(transitions, ["submitted", "in_review", "returned", "submitted", "in_review", "accepted"])
        again = self.reviewer.post(
            f"/api/v1/reports/{report['id']}/accept", json={"revision": report["revision"]}
        )
        self.assertEqual(again.status_code, 409)
        self.assertEqual(self.ok(self.reviewer.get("/api/v1/registry", params=self.filters))["total"], 1)

    def test_accepted_report_is_immutable_through_api(self):
        report = self.accept(self.add_entry(self.new_report()))
        entry = report["entries"][0]
        responses = [
            self.operator.post(f"/api/v1/reports/{report['id']}/entries", json=self.entry_payload(report)),
            self.operator.patch(f"/api/v1/reports/{report['id']}/entries/{entry['id']}", json=self.entry_payload(report, quantity=8)),
            self.operator.delete(f"/api/v1/reports/{report['id']}/entries/{entry['id']}", params={"revision": report["revision"]}),
        ]
        for response in responses:
            self.assertIn(response.status_code, (403, 409), response.text)
        unchanged = self.detail(report["id"])
        self.assertEqual(len(unchanged["entries"]), 1)
        self.assertAlmostEqual(float(unchanged["entries"][0]["quantity"]), 2.5)

    def test_idempotency_duplicate_warning_and_revision_conflict(self):
        report = self.new_report()
        initial_revision = report["revision"]
        body = self.entry_payload(report)
        first = self.ok(self.operator.post(f"/api/v1/reports/{report['id']}/entries", json=body))
        repeated = self.ok(self.operator.post(f"/api/v1/reports/{report['id']}/entries", json=body))
        self.assertEqual(len(repeated["entries"]), 1)
        self.assertEqual(first["revision"], repeated["revision"])
        conflict = self.operator.post(
            f"/api/v1/reports/{report['id']}/entries",
            json=self.entry_payload(first, quantity=8, revision=initial_revision),
        )
        self.assertEqual(conflict.status_code, 409)
        duplicate_body = self.entry_payload(first)
        duplicate = self.operator.post(f"/api/v1/reports/{report['id']}/entries", json=duplicate_body)
        self.assertEqual(duplicate.status_code, 409)
        duplicate_body["confirm_duplicate"] = True
        confirmed = self.ok(self.operator.post(f"/api/v1/reports/{report['id']}/entries", json=duplicate_body))
        self.assertEqual(len(confirmed["entries"]), 2)

    def test_invalid_values_do_not_partially_create_entries(self):
        report = self.new_report()
        for quantity in (0, -1, 10001, 1.1234, True, "not-a-number"):
            with self.subTest(quantity=quantity):
                response = self.operator.post(
                    f"/api/v1/reports/{report['id']}/entries",
                    json=self.entry_payload(report, quantity=quantity),
                )
                self.assertEqual(response.status_code, 422, response.text)
        for wrong_date in ("2001-02-01", (date.today() + timedelta(days=1)).isoformat(), "bad-date"):
            response = self.operator.post(
                f"/api/v1/reports/{report['id']}/entries",
                json=self.entry_payload(report, date=wrong_date),
            )
            self.assertEqual(response.status_code, 422, response.text)
        raw = json.dumps(self.entry_payload(report)).replace('"quantity": 2.5', '"quantity": NaN')
        response = self.operator.post(
            f"/api/v1/reports/{report['id']}/entries", content=raw,
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(len(self.detail(report["id"])["entries"]), 0)

    def test_export_is_real_excel_and_untrusted_names_stay_text(self):
        waste_type = self.ok(self.operator.post(
            "/api/v1/waste-types",
            json={"name": "=1+1", "unit": "kg", "category": "Тест", "recyclability": "no", "default_method_id": self.method["id"]},
        ))
        report = self.accept(self.add_entry(self.new_report(), waste_type_id=waste_type["id"]))
        response = self.reviewer.get("/api/v1/exports/summary.xlsx", params=self.filters)
        self.assertEqual(response.status_code, 200, response.text[:300] if response.status_code != 200 else "")
        self.assertIn("spreadsheetml", response.headers.get("content-type", ""))
        ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        with ZipFile(io.BytesIO(response.content)) as archive:
            self.assertIn("[Content_Types].xml", archive.namelist())
            self.assertIn("xl/workbook.xml", archive.namelist())
            worksheet_names = [name for name in archive.namelist() if name.startswith("xl/worksheets/") and name.endswith(".xml")]
            self.assertGreaterEqual(len(worksheet_names), 3)
            visible_texts = []
            numeric_values = []
            for name in worksheet_names:
                worksheet = ET.fromstring(archive.read(name))
                self.assertFalse(worksheet.findall(".//m:f", ns), "An untrusted text became a formula")
                visible_texts.extend(node.text or "" for node in worksheet.findall(".//m:t", ns))
                numeric_values.extend(node.text or "" for node in worksheet.findall(".//m:v", ns))
            self.assertIn("=1+1", visible_texts)
            self.assertTrue(any(abs(float(value) - 2.5) < 1e-9 for value in numeric_values if value))
        self.assertEqual(self.ok(self.reviewer.get("/api/v1/registry", params=self.filters))["total"], 1)

    def test_data_survives_app_recreation_and_seed_repeat(self):
        report = self.add_entry(self.new_report(), quantity=4.125)
        try:
            seed_demo(self.db_path, as_of=date.today().isoformat(), passwords=self.passwords)
        except ValueError:
            # Refusing to reseed a populated database is also a safe policy.
            pass
        restored_app = create_app(db_path=self.db_path)
        restored_client, _ = self.login("iskander", app=restored_app)
        restored = self.detail(report["id"], client=restored_client)
        self.assertEqual(restored["status"], "draft")
        self.assertEqual(len(restored["entries"]), 1)
        self.assertAlmostEqual(float(restored["entries"][0]["quantity"]), 4.125)


if __name__ == "__main__":
    unittest.main()
