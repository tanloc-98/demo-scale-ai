"""
Integration tests for POST /api/v1/salary/calculate — HR-004
Tests full HTTP request → job queued → poll result flow.
"""
import time
import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

SALARY_PAYLOAD = {
    "employee_id": "EMP001",
    "month": "2026-05",
    "base_salary": 15_000_000,
    "total_work_days": 22,
    "days_worked": 22,
    "days_absent": 0,
    "overtime_hours": 0,
    "overtime_hours_weekend": 0,
    "overtime_hours_holiday": 0,
    "allowances": {"lunch": 800_000, "transport": 500_000},
    "deductions": {"social_insurance": True, "health_insurance": True, "union_fee": True},
    "dependents": 0,
}


def post_salary(payload=None):
    return client.post("/api/v1/salary/calculate", json=payload or SALARY_PAYLOAD)


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


class TestSalaryCalculateEndpoint:
    def test_returns_202_accepted(self):
        r = post_salary()
        assert r.status_code == 202

    def test_response_has_job_id(self):
        r = post_salary()
        body = r.json()
        assert "job_id" in body
        assert len(body["job_id"]) > 0

    def test_initial_status_is_queued(self):
        r = post_salary()
        assert r.json()["status"] == "queued"

    def test_job_completes_with_result(self):
        job_id = post_salary().json()["job_id"]
        job = poll_job(job_id)
        assert job["result"] is not None

    def test_result_has_correct_gross(self):
        job_id = post_salary().json()["job_id"]
        result = poll_job(job_id)["result"]
        assert result["gross_salary"] > 0

    def test_net_less_than_gross(self):
        job_id = post_salary().json()["job_id"]
        result = poll_job(job_id)["result"]
        assert result["net_salary"] < result["gross_salary"]

    def test_result_has_summary(self):
        job_id = post_salary().json()["job_id"]
        result = poll_job(job_id)["result"]
        assert result.get("summary")
        assert len(result["summary"]) > 10

    def test_allowances_increase_gross(self):
        # AllowancesInput has defaults — pass null to disable all allowances
        no_allow   = {**SALARY_PAYLOAD, "allowances": None}
        with_allow = {**SALARY_PAYLOAD, "allowances": {"lunch": 800_000, "transport": 0}}
        r_no  = poll_job(post_salary(no_allow).json()["job_id"])["result"]
        r_yes = poll_job(post_salary(with_allow).json()["job_id"])["result"]
        assert r_yes["gross_salary"] == r_no["gross_salary"] + 800_000

    def test_absent_day_reduces_net(self):
        full   = {**SALARY_PAYLOAD, "days_worked": 22, "days_absent": 0}
        absent = {**SALARY_PAYLOAD, "days_worked": 21, "days_absent": 1}
        r_full   = poll_job(post_salary(full).json()["job_id"])["result"]
        r_absent = poll_job(post_salary(absent).json()["job_id"])["result"]
        assert r_absent["net_salary"] < r_full["net_salary"]

    def test_invalid_employee_id_still_processed(self):
        payload = {**SALARY_PAYLOAD, "employee_id": "UNKNOWN"}
        job_id = post_salary(payload).json()["job_id"]
        job = poll_job(job_id)
        assert job["status"] == "completed"

    def test_missing_required_field_returns_422(self):
        r = client.post("/api/v1/salary/calculate", json={"employee_id": "EMP001"})
        assert r.status_code == 422

    def test_poll_nonexistent_job_returns_404(self):
        r = client.get("/api/v1/jobs/NONEXISTENT")
        assert r.status_code == 404


class TestSalaryJobsEndpoint:
    def test_jobs_list_returns_200(self):
        r = client.get("/api/v1/jobs")
        assert r.status_code == 200

    def test_jobs_list_has_jobs_key(self):
        r = client.get("/api/v1/jobs")
        assert "jobs" in r.json()

    def test_completed_job_appears_in_list(self):
        job_id = post_salary().json()["job_id"]
        poll_job(job_id)
        jobs = client.get("/api/v1/jobs").json()["jobs"]
        ids = [j["job_id"] for j in jobs]
        assert job_id in ids
