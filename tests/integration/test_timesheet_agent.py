"""
Integration tests for POST /api/v1/timesheet/process — HR-003
Tests full HTTP request → job queued → poll result flow.
"""
import time
import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

BASE_PAYLOAD = {
    "employee_id": "EMP001",
    "month": "2026-06",
    "records": [
        {"date": "2026-06-01", "check_in": "08:00", "check_out": "17:30"},
        {"date": "2026-06-02", "check_in": "08:10", "check_out": "17:30"},
        {"date": "2026-06-03", "check_in": None,    "check_out": None},
    ],
    "work_schedule": {"start": "08:00", "end": "17:30", "break_minutes": 60},
}


def post_ts(payload=None):
    return client.post("/api/v1/timesheet/process", json=payload or BASE_PAYLOAD)


def poll_job(job_id: str, timeout: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = client.get(f"/api/v1/jobs/{job_id}")
        assert r.status_code == 200
        data = r.json()
        if data["status"] == "completed":
            return data
        if data["status"] == "failed":
            pytest.fail(f"Job {job_id} failed: {data.get('error')}")
        time.sleep(0.1)
    pytest.fail(f"Job {job_id} did not complete within {timeout}s")


class TestTimesheetProcessEndpoint:
    def test_returns_202_accepted(self):
        assert post_ts().status_code == 202

    def test_response_has_job_id(self):
        body = post_ts().json()
        assert "job_id" in body and len(body["job_id"]) > 0

    def test_job_completes(self):
        job_id = post_ts().json()["job_id"]
        job = poll_job(job_id)
        assert job["status"] == "completed"

    def test_result_has_summary(self):
        job_id = post_ts().json()["job_id"]
        result = poll_job(job_id)["result"]
        assert result.get("summary") and len(result["summary"]) > 5

    def test_days_present_counted(self):
        # 2026-06-01=Mon, 2026-06-02=Tue (both workdays with records), 2026-06-03=Wed (absent)
        job_id = post_ts().json()["job_id"]
        result = poll_job(job_id)["result"]
        assert result["days_present"] == 2

    def test_absent_day_in_anomalies(self):
        job_id = post_ts().json()["job_id"]
        result = poll_job(job_id)["result"]
        anomalies = result["anomalies"]
        assert any("2026-06-03" in a for a in anomalies)

    def test_late_arrival_detected(self):
        payload = {**BASE_PAYLOAD, "records": [
            {"date": "2026-06-02", "check_in": "09:00", "check_out": "17:30"},
        ]}
        job_id = post_ts(payload).json()["job_id"]
        result = poll_job(job_id)["result"]
        assert result["late_arrivals"] == 1

    def test_approved_defaults_false(self):
        job_id = post_ts().json()["job_id"]
        result = poll_job(job_id)["result"]
        assert result["approved"] is False

    def test_employee_id_preserved_in_result(self):
        job_id = post_ts().json()["job_id"]
        result = poll_job(job_id)["result"]
        assert result["employee_id"] == "EMP001"

    def test_period_preserved_in_result(self):
        job_id = post_ts().json()["job_id"]
        result = poll_job(job_id)["result"]
        assert result["period"] == "2026-06"

    def test_missing_required_field_returns_422(self):
        r = client.post("/api/v1/timesheet/process", json={"employee_id": "EMP001"})
        assert r.status_code == 422

    def test_overtime_on_weekend_detected(self):
        payload = {**BASE_PAYLOAD, "month": "2026-06", "records": [
            {"date": "2026-06-07", "check_in": "08:00", "check_out": "20:00"},  # Sunday
        ]}
        job_id = post_ts(payload).json()["job_id"]
        result = poll_job(job_id)["result"]
        assert result["overtime_hours"] > 0
