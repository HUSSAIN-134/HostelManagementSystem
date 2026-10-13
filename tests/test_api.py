"""Safe integration tests against the configured hostel_management database.

Run with: python -m unittest discover -s tests -v
The mutation tests create uniquely named records and remove them in cleanup.
"""

from datetime import date, timedelta
import unittest
import uuid

import mysql.connector

from app import app
from database import get_connection


GET_ENDPOINTS = (
    "/api/students", "/api/blocks", "/api/rooms", "/api/beds",
    "/api/beds/available", "/api/allocations", "/api/transfers",
    "/api/fees", "/api/payments", "/api/visitors", "/api/complaints",
    "/api/maintenance", "/api/vacating", "/api/reports/occupancy",
    "/api/reports/vacancies", "/api/reports/fee-dues",
    "/api/reports/allocation-history", "/api/reports/visitors",
    "/api/reports/complaints", "/api/reports/maintenance",
)


class HostelApiIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        response = app.test_client().get("/api/health")
        if response.status_code != 200:
            raise unittest.SkipTest("Configured MySQL database is unavailable")
        cls.client = app.test_client()

    def test_health_stats_and_read_modules(self):
        health = self.client.get("/api/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.get_json(), {"status": "ok", "database": "connected"})
        stats = self.client.get("/api/stats")
        self.assertEqual(stats.status_code, 200)
        self.assertEqual(stats.get_json()["students"], 20)
        self.assertEqual(stats.get_json()["hostel_blocks"], 3)
        self.assertEqual(stats.get_json()["rooms"], 10)
        self.assertEqual(stats.get_json()["beds"], 30)
        self.assertEqual(stats.get_json()["active_allocations"], 19)
        for endpoint in GET_ENDPOINTS:
            with self.subTest(endpoint=endpoint):
                response = self.client.get(endpoint)
                self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
                self.assertIsInstance(response.get_json(), list)
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_validation_rejects_invalid_records_without_writes(self):
        sample = self.client.get("/api/students").get_json()[0]
        base = {
            "registration_no": "AUDIT-DUP-REG", "first_name": "Audit", "last_name": "Candidate",
            "email": "audit-unique@example.invalid", "phone": "9000000100", "gender": "OTHER",
            "department": "Audit", "course": "Audit", "year_of_study": 1,
            "emergency_contact_name": "Contact", "emergency_contact_phone": "9000000101",
        }
        by_reg = dict(base, registration_no=sample["registration_no"])
        by_email = dict(base, registration_no="AUDIT-DUP-EMAIL", email=sample["email"])
        self.assertEqual(self.client.post("/api/students", json=by_reg).status_code, 409)
        self.assertEqual(self.client.post("/api/students", json=by_email).status_code, 409)

        beds = self.client.get("/api/beds").get_json()
        occupied_bed = next(row["bed_id"] for row in beds if row["is_occupied"])
        available = self.client.get("/api/beds/available").get_json()
        candidate = next(row for row in available if row["block_code"] == "EAST")
        today = date.today()
        payload = {"student_id": 99999999, "bed_id": candidate["bed_id"],
                   "allocation_date": today.isoformat(), "expected_vacate_date": (today + timedelta(days=30)).isoformat()}
        self.assertEqual(self.client.post("/api/allocations", json=payload).status_code, 404)
        payload["student_id"] = sample["student_id"]
        payload["bed_id"] = 99999999
        self.assertEqual(self.client.post("/api/allocations", json=payload).status_code, 400)
        payload["bed_id"] = occupied_bed
        self.assertEqual(self.client.post("/api/allocations", json=payload).status_code, 409)
        payload["student_id"] = sample["student_id"]
        payload["bed_id"] = candidate["bed_id"]
        self.assertEqual(self.client.post("/api/allocations", json=payload).status_code, 409)
        payload["student_id"] = 99999999
        payload["allocation_date"] = "not-a-date"
        self.assertEqual(self.client.post("/api/allocations", json=payload).status_code, 400)
        payload["allocation_date"] = today.isoformat()
        payload["expected_vacate_date"] = (today - timedelta(days=1)).isoformat()
        self.assertEqual(self.client.post("/api/allocations", json=payload).status_code, 400)

        invalid_room = self.client.post("/api/rooms", json={"block_id": 99999999, "room_number": "AUDIT-X", "capacity": 1})
        self.assertEqual(invalid_room.status_code, 400)
        fee = self.client.get("/api/fees").get_json()[0]
        payment = self.client.post("/api/payments", json={"student_id": sample["student_id"], "fee_schedule_id": fee["fee_schedule_id"], "amount": 0, "payment_method": "CASH"})
        self.assertEqual(payment.status_code, 400)
        overpayment = self.client.post("/api/payments", json={"student_id": sample["student_id"], "fee_schedule_id": fee["fee_schedule_id"], "amount": fee["amount"] + 1, "payment_method": "CASH"})
        self.assertEqual(overpayment.status_code, 400)

    def test_student_block_room_bed_crud_with_temporary_records(self):
        suffix = uuid.uuid4().hex[:10].upper()
        created_student = created_block = created_room = created_bed = None
        try:
            student_data = {
                "registration_no": f"AUDIT-{suffix}", "first_name": "Temporary", "last_name": "Audit",
                "email": f"{suffix.lower()}@example.invalid", "phone": "9000000200", "gender": "OTHER",
                "department": "Audit", "course": "Test", "year_of_study": 1,
                "emergency_contact_name": "Contact", "emergency_contact_phone": "9000000201",
            }
            response = self.client.post("/api/students", json=student_data)
            self.assertEqual(response.status_code, 201, response.get_json())
            created_student = response.get_json()["student_id"]
            self.assertEqual(self.client.get(f"/api/students/{created_student}").status_code, 200)
            self.assertEqual(self.client.put(f"/api/students/{created_student}", json={"phone": "9000000202"}).status_code, 200)

            response = self.client.post("/api/blocks", json={"block_code": f"T{suffix}", "block_name": "Temporary Audit Block", "gender_policy": "MIXED"})
            self.assertEqual(response.status_code, 201, response.get_json())
            created_block = response.get_json()["block_id"]
            self.assertEqual(self.client.put(f"/api/blocks/{created_block}", json={"address": "Audit location"}).status_code, 200)

            response = self.client.post("/api/rooms", json={"block_id": created_block, "room_number": "T-1", "capacity": 1})
            self.assertEqual(response.status_code, 201, response.get_json())
            created_room = response.get_json()["room_id"]
            self.assertEqual(self.client.put(f"/api/rooms/{created_room}", json={"floor_number": 1}).status_code, 200)

            response = self.client.post("/api/beds", json={"room_id": created_room, "bed_label": "A"})
            self.assertEqual(response.status_code, 201, response.get_json())
            created_bed = response.get_json()["bed_id"]
            self.assertEqual(self.client.post("/api/beds", json={"room_id": created_room, "bed_label": "B"}).status_code, 409)
            self.assertEqual(self.client.put(f"/api/beds/{created_bed}", json={"is_active": False}).status_code, 200)
            self.assertEqual(self.client.put(f"/api/beds/{created_bed}", json={"is_active": True}).status_code, 200)
            self.assertEqual(self.client.delete(f"/api/blocks/{created_block}").status_code, 409)
            self._delete_temporary_records(bed_id=created_bed)
            created_bed = None
            self.assertEqual(self.client.delete(f"/api/rooms/{created_room}").status_code, 200)
            created_room = None
            self.assertEqual(self.client.delete(f"/api/blocks/{created_block}").status_code, 200)
            created_block = None
            self.assertEqual(self.client.delete(f"/api/students/{created_student}").status_code, 200)
            created_student = None
        finally:
            self._delete_temporary_records(created_student, created_block, created_room, created_bed)

    def test_fees_payments_visitors_complaints_and_maintenance_writes(self):
        suffix = uuid.uuid4().hex[:10].upper()
        student_id = fee_id = visitor_id = complaint_id = maintenance_id = None
        payment_id = None
        try:
            student_data = {
                "registration_no": f"AUDIT-{suffix}", "first_name": "Service", "last_name": "Audit",
                "email": f"{suffix.lower()}@example.invalid", "phone": "9000000400", "gender": "OTHER",
                "department": "Audit", "course": "Test", "year_of_study": 1,
                "emergency_contact_name": "Contact", "emergency_contact_phone": "9000000401",
            }
            response = self.client.post("/api/students", json=student_data)
            self.assertEqual(response.status_code, 201, response.get_json())
            student_id = response.get_json()["student_id"]
            due = (date.today() + timedelta(days=30)).isoformat()
            response = self.client.post("/api/fees", json={"academic_year": "2099-2100", "term": f"Audit-{suffix}", "fee_type": "OTHER", "amount": 100, "due_date": due})
            self.assertEqual(response.status_code, 201, response.get_json())
            fee_id = response.get_json()["fee_schedule_id"]
            response = self.client.post("/api/payments", json={"student_id": student_id, "fee_schedule_id": fee_id, "amount": 25, "payment_method": "UPI", "transaction_reference": f"AUDIT-{suffix}"})
            self.assertEqual(response.status_code, 201, response.get_json())
            payment_id = response.get_json()["payment_id"]

            approver = self._existing_user_id()
            response = self.client.post("/api/visitors", json={"student_id": student_id, "visitor_name": "Audit Visitor", "relationship_to_student": "Friend", "phone": "9000000402", "purpose": "Integration test", "approved_by": approver})
            self.assertEqual(response.status_code, 201, response.get_json())
            visitor_id = response.get_json()["visitor_id"]
            response = self.client.put(f"/api/visitors/{visitor_id}/checkout", json={})
            self.assertEqual(response.status_code, 200, response.get_json())
            self.assertIsNotNone(response.get_json()["check_out"])

            response = self.client.post("/api/complaints", json={"student_id": student_id, "category": "OTHER", "subject": "Audit complaint", "description": "Temporary API integration check"})
            self.assertEqual(response.status_code, 201, response.get_json())
            complaint_id = response.get_json()["complaint_id"]
            response = self.client.put(f"/api/complaints/{complaint_id}", json={"status": "IN_PROGRESS", "assigned_to": approver})
            self.assertEqual(response.status_code, 200, response.get_json())
            self.assertEqual(response.get_json()["status"], "IN_PROGRESS")

            room_id = self.client.get("/api/rooms").get_json()[0]["room_id"]
            response = self.client.post("/api/maintenance", json={"room_id": room_id, "requested_by_student_id": student_id, "category": "OTHER", "description": "Temporary API integration check"})
            self.assertEqual(response.status_code, 201, response.get_json())
            maintenance_id = response.get_json()["maintenance_id"]
            response = self.client.put(f"/api/maintenance/{maintenance_id}", json={"status": "ASSIGNED", "assigned_to": approver})
            self.assertEqual(response.status_code, 200, response.get_json())
            self.assertEqual(response.get_json()["status"], "ASSIGNED")
        finally:
            self._delete_service_records(student_id, fee_id, payment_id, visitor_id, complaint_id, maintenance_id)

    def test_allocation_transfer_vacating_and_transaction_rollbacks(self):
        suffix = uuid.uuid4().hex[:10].upper()
        student_id = allocation_id = transferred_allocation_id = None
        bed_one = bed_two = None
        try:
            available = [row for row in self.client.get("/api/beds/available").get_json() if row["block_code"] == "EAST"]
            self.assertGreaterEqual(len(available), 2, "Need two available mixed-block beds for transaction tests")
            first = available[0]
            second = next(row for row in available[1:] if row["room_number"] != first["room_number"])
            bed_one, bed_two = first["bed_id"], second["bed_id"]
            student_data = {
                "registration_no": f"AUDIT-{suffix}", "first_name": "Transaction", "last_name": "Audit",
                "email": f"{suffix.lower()}@example.invalid", "phone": "9000000300", "gender": "OTHER",
                "department": "Audit", "course": "Test", "year_of_study": 1,
                "emergency_contact_name": "Contact", "emergency_contact_phone": "9000000301",
            }
            response = self.client.post("/api/students", json=student_data)
            self.assertEqual(response.status_code, 201, response.get_json())
            student_id = response.get_json()["student_id"]
            today = date.today()
            allocation_data = {"student_id": student_id, "bed_id": bed_one,
                               "allocation_date": today.isoformat(), "expected_vacate_date": (today + timedelta(days=90)).isoformat(),
                               "created_by": self._existing_user_id()}
            response = self.client.post("/api/allocations", json=allocation_data)
            self.assertEqual(response.status_code, 201, response.get_json())
            allocation_id = response.get_json()["allocation_id"]
            self.assertEqual(response.get_json()["created_by"], allocation_data["created_by"])

            invalid_length_transfer = {"student_id": student_id, "from_allocation_id": allocation_id,
                            "to_bed_id": bed_two, "transfer_date": today.isoformat(),
                            "expected_vacate_date": (today + timedelta(days=90)).isoformat(),
                            "reason": "x" * 501, "approved_by": allocation_data["created_by"]}
            self.assertEqual(self.client.post("/api/transfers", json=invalid_length_transfer).status_code, 400)
            old_transfer_date = (today - timedelta(days=1)).isoformat()
            invalid_old_transfer = dict(invalid_length_transfer, reason="Invalid old transfer date", transfer_date=old_transfer_date, expected_vacate_date=old_transfer_date)
            self.assertEqual(self.client.post("/api/transfers", json=invalid_old_transfer).status_code, 400)

            bad_transfer = dict(invalid_length_transfer, reason="Rollback verification", approved_by=99999999)
            before_transfers = len(self.client.get("/api/transfers").get_json())
            response = self.client.post("/api/transfers", json=bad_transfer)
            self.assertEqual(response.status_code, 400, response.get_json())
            self.assertEqual(self.client.get(f"/api/allocations/{allocation_id}").get_json()["status"], "ACTIVE")
            self.assertEqual(len(self.client.get("/api/transfers").get_json()), before_transfers)
            self.assertIn(bed_two, [row["bed_id"] for row in self.client.get("/api/beds/available").get_json()])

            transfer_data = dict(bad_transfer, reason="Move for transaction audit", approved_by=allocation_data["created_by"])
            response = self.client.post("/api/transfers", json=transfer_data)
            self.assertEqual(response.status_code, 201, response.get_json())
            transferred_allocation_id = response.get_json()["new_allocation"]["allocation_id"]
            self.assertEqual(self.client.get(f"/api/allocations/{allocation_id}").get_json()["status"], "TRANSFERRED")
            self.assertEqual(self.client.get(f"/api/allocations/{transferred_allocation_id}").get_json()["status"], "ACTIVE")

            bad_vacating = {"allocation_id": transferred_allocation_id, "vacating_date": today.isoformat(),
                            "reason": "Rollback verification", "processed_by": 99999999}
            invalid_vacate_date = dict(bad_vacating, vacating_date=(today - timedelta(days=1)).isoformat(), processed_by=None)
            self.assertEqual(self.client.post("/api/vacating", json=invalid_vacate_date).status_code, 400)
            response = self.client.post("/api/vacating", json=bad_vacating)
            self.assertEqual(response.status_code, 400, response.get_json())
            self.assertEqual(self.client.get(f"/api/allocations/{transferred_allocation_id}").get_json()["status"], "ACTIVE")
            self.assertNotIn(transferred_allocation_id, [row["allocation_id"] for row in self.client.get("/api/vacating").get_json()])

            response = self.client.post("/api/vacating", json={"allocation_id": transferred_allocation_id,
                "vacating_date": today.isoformat(), "reason": "Temporary transaction test"})
            self.assertEqual(response.status_code, 201, response.get_json())
            self.assertEqual(self.client.get(f"/api/allocations/{transferred_allocation_id}").get_json()["status"], "VACATED")
            self.assertIn(bed_two, [row["bed_id"] for row in self.client.get("/api/beds/available").get_json()])
        finally:
            self._delete_temporary_records(student_id, allocation_ids=(allocation_id, transferred_allocation_id))

    def _existing_user_id(self):
        blocks = self.client.get("/api/blocks").get_json()
        return next(block["warden_user_id"] for block in blocks if block["warden_user_id"] is not None)

    @staticmethod
    def _delete_temporary_records(student_id=None, block_id=None, room_id=None, bed_id=None, allocation_ids=()):
        connection = get_connection()
        try:
            connection.start_transaction()
            cursor = connection.cursor()
            ids = tuple(value for value in allocation_ids if value is not None)
            if ids:
                marks = ",".join(["%s"] * len(ids))
                cursor.execute(f"DELETE FROM transfers WHERE from_allocation_id IN ({marks}) OR to_allocation_id IN ({marks})", ids + ids)
                cursor.execute(f"DELETE FROM vacating_records WHERE allocation_id IN ({marks})", ids)
                cursor.execute(f"DELETE FROM allocations WHERE allocation_id IN ({marks})", ids)
            if student_id is not None:
                cursor.execute("DELETE FROM students WHERE student_id=%s", (student_id,))
            if bed_id is not None:
                cursor.execute("DELETE FROM beds WHERE bed_id=%s", (bed_id,))
            if room_id is not None:
                cursor.execute("DELETE FROM rooms WHERE room_id=%s", (room_id,))
            if block_id is not None:
                cursor.execute("DELETE FROM hostel_blocks WHERE block_id=%s", (block_id,))
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _delete_service_records(student_id, fee_id, payment_id, visitor_id, complaint_id, maintenance_id):
        connection = get_connection()
        try:
            connection.start_transaction()
            cursor = connection.cursor()
            for table, key, value in (
                ("payments", "payment_id", payment_id),
                ("visitors", "visitor_id", visitor_id),
                ("complaints", "complaint_id", complaint_id),
                ("maintenance_requests", "maintenance_id", maintenance_id),
                ("fee_schedules", "fee_schedule_id", fee_id),
                ("students", "student_id", student_id),
            ):
                if value is not None:
                    cursor.execute(f"DELETE FROM {table} WHERE {key}=%s", (value,))
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
