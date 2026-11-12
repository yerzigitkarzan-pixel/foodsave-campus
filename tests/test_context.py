"""Regression checks for waste context, daily portions and existing SQLite data."""
import io
import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
import uuid
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from fastapi.testclient import TestClient

from app.db import init_db
from app.main import create_app
from app.metrics import calculate_intensity
from app.seed import seed_demo


class IntensityTests(unittest.TestCase):
    def row(self, quantity=10, **extra):
        return {"quantity": quantity, "unit": "kg", "organization_id": 1,
                "organization_name": "A", "date": "2001-01-12", **extra}

    def day(self, portions=100, **extra):
        return {"organization_id": 1, "organization_name": "A", "date": "2001-01-12",
                "portions": portions, **extra}

    def test_denominator_is_counted_once_per_organization_day(self):
        result = calculate_intensity([
            self.row(4), self.row(6), self.row(30, organization_id=2, organization_name="B")
        ], [self.day(), self.day(), self.day(200, organization_id=2, organization_name="B")])
        self.assertEqual(result["portions"], 300)
        self.assertEqual(result["covered_days"], 2)
        self.assertAlmostEqual(result["kg_per_100_portions"], 40 / 3)
        self.assertTrue(result["complete"])

    def test_missing_zero_unknown_density_and_unweighed_days_are_not_zero_waste(self):
        rows = [self.row(), self.row(20, date="2001-01-13")]
        partial = calculate_intensity(rows, [self.day(), self.day(500, date="2001-01-14")])
        self.assertIsNone(partial["kg_per_100_portions"])
        self.assertEqual(partial["covered_kg_per_100_portions"], 10)
        self.assertEqual((partial["portions"], partial["missing_days"], partial["total_days"]), (100, 1, 2))
        self.assertEqual(partial["service_only_days"], 1)
        zero = calculate_intensity([self.row()], [self.day(0)])
        self.assertIsNone(zero["kg_per_100_portions"])
        self.assertIsNone(zero["covered_kg_per_100_portions"])
        self.assertEqual(zero["zero_portion_days"], 1)
        unknown = calculate_intensity([self.row(), self.row(5, unit="l", density_kg_per_l=None)], [self.day()])
        self.assertIsNone(unknown["kg_per_100_portions"])
        self.assertEqual(unknown["unknown_mass_days"], 1)
        self.assertEqual(unknown["covered_days"], 0)
        no_rows = calculate_intensity([], [self.day()])
        self.assertIsNone(no_rows["kg_per_100_portions"])

    def test_additive_migration_preserves_legacy_entry_and_is_repeatable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.sqlite3"
            with closing(sqlite3.connect(path)) as connection, connection:
                connection.execute("""CREATE TABLE entries(
                    id INTEGER PRIMARY KEY,report_id INTEGER NOT NULL,date TEXT NOT NULL,
                    waste_type_id INTEGER NOT NULL,quantity TEXT NOT NULL,method_id INTEGER NOT NULL,
                    responsible_user_id INTEGER NOT NULL,snapshot TEXT NOT NULL,
                    client_request_id TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
                    UNIQUE(report_id,client_request_id))""")
                original = (77, 3, "2001-01-12", 8, "2.500", 7, 9, '{"unit":"kg"}', "old-request", "old-created", "old-updated")
                connection.execute("INSERT INTO entries VALUES(?,?,?,?,?,?,?,?,?,?,?)", original)
            init_db(path)
            init_db(path)
            with closing(sqlite3.connect(path)) as connection, connection:
                connection.row_factory = sqlite3.Row
                migrated = dict(connection.execute("SELECT * FROM entries WHERE id=77").fetchone())
                self.assertEqual(tuple(migrated.values())[:11], original)
                self.assertEqual(migrated["reason_code"], "unspecified")
                self.assertEqual(migrated["note"], "")
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM service_days").fetchone()[0], 0)


class ContextApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="foodsave-context-")
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "test.sqlite3"
        self.passwords = {name: "Context-Only-" + name + "-823!" for name in ("reviewer", "tpp", "thipp", "atuinn", "canella", "iskander")}
        seed_demo(self.path, passwords=self.passwords)
        self.app = create_app(self.path)
        self.operator = self.login("iskander")
        self.reviewer = self.login("reviewer")
        self.foreign = self.login("tpp")
        self.waste = next(x for x in self.ok(self.operator.get("/api/v1/waste-types"))["items"] if x["unit"] == "kg")
        self.method = next(x for x in self.ok(self.operator.get("/api/v1/disposal-methods"))["items"] if x["code"] == "TBO")
        self.report = self.ok(self.operator.post("/api/v1/reports", json={"period": "2001-01"}))
        self.filters = {"from": "2001-01-01", "to": "2001-01-31", "organization_id": self.report["organization_id"]}

    def ok(self, response):
        self.assertIn(response.status_code, (200, 201), response.text[:1500])
        return response.json()

    def login(self, name):
        client = TestClient(self.app)
        self.addCleanup(client.close)
        csrf = self.ok(client.get("/api/v1/auth/csrf"))["csrf_token"]
        data = self.ok(client.post("/api/v1/auth/login", json={"username": name, "password": self.passwords[name]}, headers={"X-CSRF-Token": csrf}))
        client.headers["X-CSRF-Token"] = data["csrf_token"]
        return client

    @property
    def endpoint(self):
        return f'/api/v1/reports/{self.report["id"]}'

    def add(self, **extra):
        body = {"date": "2001-01-12", "waste_type_id": self.waste["id"], "method_id": self.method["id"], "quantity": 10,
                "revision": self.report["revision"], "client_request_id": str(uuid.uuid4()), **extra}
        self.report = self.ok(self.operator.post(self.endpoint + "/entries", json=body))
        return body

    def portions(self, portions=100, **extra):
        self.report = self.ok(self.operator.post(self.endpoint + "/service-days", json={"date": "2001-01-12", "portions": portions, "revision": self.report["revision"], **extra}))

    def transition(self, client, action):
        self.report = self.ok(client.post(self.endpoint + "/" + action, json={"revision": self.report["revision"]}))

    def test_reason_and_note_roundtrip_partial_edit_validation_and_retry(self):
        reasons = self.ok(self.operator.get("/api/v1/meta"))["waste_reasons"]
        self.assertIn("spoilage", [item["code"] for item in reasons])
        body = self.add(reason_code="spoilage", note="=SUM(A1:A2)")
        saved = self.report["entries"][0]
        self.assertEqual((saved["reason_code"], saved["note"]), ("spoilage", "=SUM(A1:A2)"))
        retried = self.ok(self.operator.post(self.endpoint + "/entries", json=body))
        self.assertEqual(len(retried["entries"]), 1)
        changed_retry = self.operator.post(self.endpoint + "/entries", json={**body, "note": "different"})
        self.assertEqual(changed_retry.status_code, 409)
        patch = {key: value for key, value in body.items() if key not in ("client_request_id", "reason_code", "note")}
        self.report = self.ok(self.operator.patch(self.endpoint + f'/entries/{saved["id"]}', json={**patch, "revision": self.report["revision"], "quantity": 12}))
        self.assertEqual(self.report["entries"][0]["note"], "=SUM(A1:A2)")
        self.assertEqual(self.report["entries"][0]["reason_code"], "spoilage")
        for extra in ({"reason_code": "invented"}, {"note": "x" * 1001}, {"note": 123}, {"reason_code": None}):
            response = self.operator.patch(self.endpoint + f'/entries/{saved["id"]}', json={**patch, "revision": self.report["revision"], **extra})
            self.assertEqual(response.status_code, 422, response.text)

    def test_portions_upsert_partial_coverage_zero_and_delete(self):
        self.add(quantity=4)
        self.add(quantity=6)
        self.portions(100)
        self.assertEqual(self.report["totals"]["intensity"]["kg_per_100_portions"], 10)
        self.portions(200)
        self.assertEqual(len(self.report["service_days"]), 1)
        self.assertEqual(self.report["totals"]["intensity"]["kg_per_100_portions"], 5)
        self.add(quantity=5, date="2001-01-13")
        intensity = self.report["totals"]["intensity"]
        self.assertIsNone(intensity["kg_per_100_portions"])
        self.assertEqual(intensity["covered_kg_per_100_portions"], 5)
        self.portions(100, date="2001-01-13")
        self.assertEqual(self.report["totals"]["intensity"]["kg_per_100_portions"], 5)
        self.portions(0)
        self.assertEqual(self.report["totals"]["intensity"]["zero_portion_days"], 1)
        self.report = self.ok(self.operator.delete(self.endpoint + "/service-days/2001-01-12", params={"revision": self.report["revision"]}))
        self.assertEqual(self.report["totals"]["intensity"]["missing_days"], 1)

    def test_service_validation_revision_csrf_roles_and_accepted_lock(self):
        self.add()
        body = {"date": "2001-01-12", "portions": 100, "revision": self.report["revision"]}
        for extra in ({"portions": -1}, {"portions": 1.5}, {"portions": True}, {"portions": 100001}, {"portions": None}, {"date": "2001-02-01"}, {"date": "2099-01-12"}):
            response = self.operator.post(self.endpoint + "/service-days", json={**body, **extra})
            self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.reviewer.post(self.endpoint + "/service-days", json=body).status_code, 403)
        self.assertEqual(self.foreign.post(self.endpoint + "/service-days", json=body).status_code, 404)
        self.assertEqual(self.operator.post(self.endpoint + "/service-days", json=body, headers={"X-CSRF-Token": "wrong"}).status_code, 403)
        self.portions()
        self.assertEqual(self.operator.post(self.endpoint + "/service-days", json=body).status_code, 409)
        self.transition(self.operator, "submit")
        self.transition(self.reviewer, "start-review")
        self.transition(self.reviewer, "accept")
        body["revision"] = self.report["revision"]
        self.assertEqual(self.operator.post(self.endpoint + "/service-days", json=body).status_code, 409)
        self.assertEqual(self.operator.delete(self.endpoint + "/service-days/2001-01-12", params={"revision": self.report["revision"]}).status_code, 409)

    def test_accepted_context_reaches_dashboard_agent_and_typed_export(self):
        self.add(reason_code="overproduction", note="=1+1")
        self.portions(100)
        before = self.ok(self.reviewer.get("/api/v1/dashboard", params=self.filters))
        self.assertIsNone(before["intensity"]["kg_per_100_portions"])
        self.transition(self.operator, "submit")
        self.transition(self.reviewer, "start-review")
        self.transition(self.reviewer, "accept")
        dashboard = self.ok(self.reviewer.get("/api/v1/dashboard", params=self.filters))
        self.assertEqual(dashboard["intensity"]["kg_per_100_portions"], 10)
        reason = next(x for x in dashboard["by_reason"] if x["code"] == "overproduction")
        self.assertEqual(reason["raw_kg"], 10)
        agent = self.ok(self.operator.post("/api/v1/agent/chat", json={"message": "Причины и отходы на 100 порций", **self.filters}))
        self.assertEqual(agent["scope"]["intensity"]["kg_per_100_portions"], 10)
        self.assertIn("порц", agent["answer"].lower())
        payload = self.reviewer.get("/api/v1/exports/summary.xlsx", params=self.filters)
        self.assertEqual(payload.status_code, 200)
        ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        with ZipFile(io.BytesIO(payload.content)) as workbook:
            sheets = ET.fromstring(workbook.read("xl/workbook.xml"))
            self.assertIn("Порции", [item.get("name") for item in sheets.findall(".//x:sheet", ns)])
            detail = ET.fromstring(workbook.read("xl/worksheets/sheet4.xml"))
            text_cells = [item for item in detail.findall(".//x:c", ns) if item.find("x:is/x:t", ns) is not None and item.find("x:is/x:t", ns).text == "=1+1"]
            self.assertEqual(len(text_cells), 1)
            self.assertEqual(text_cells[0].get("t"), "inlineStr")
            self.assertIsNone(text_cells[0].find("x:f", ns))
            portions = ET.fromstring(workbook.read("xl/worksheets/sheet6.xml"))
            self.assertTrue(any(cell.get("t") is None and cell.find("x:v", ns) is not None and cell.find("x:v", ns).text == "100" for cell in portions.findall(".//x:c", ns)))
        foreign = self.ok(self.foreign.get("/api/v1/dashboard", params={"from": "2001-01-01", "to": "2001-01-31"}))
        self.assertIsNone(foreign["intensity"]["kg_per_100_portions"])


if __name__ == "__main__":
    unittest.main()
