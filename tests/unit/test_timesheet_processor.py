"""
Unit tests for backend/tools/timesheet_processor.py — HR-003
Covers: grace period, late/early, OT types, holiday/weekend, anomaly detection.
"""
import pytest
from backend.tools.timesheet_processor import process_timesheet

# June 2026 has no VN public holidays → clean month for testing
MONTH = "2026-06"
SCHEDULE = {"start": "08:00", "end": "17:30", "break_minutes": 60}

# Working days in June 2026 (Mon–Fri, no holidays) = 22 days
# Jun 1=Mon, Jun 6-7=Sat-Sun, Jun 13-14, 20-21, 27-28 = weekends → 4 weekends = 8 weekend days → 22 workdays


def ts(records, schedule=None, month=None):
    return process_timesheet(records, schedule or SCHEDULE, month or MONTH)


# ---------------------------------------------------------------------------
# Presence & absent detection
# ---------------------------------------------------------------------------

class TestPresenceDetection:
    def test_single_normal_day_present(self):
        result = ts([{"date": "2026-06-01", "check_in": "08:00", "check_out": "17:30"}])
        assert result["days_present"] == 1
        assert result["days_absent"] == 21   # 22 work days minus 1 present

    def test_absent_null_both(self):
        result = ts([{"date": "2026-06-01", "check_in": None, "check_out": None}])
        assert result["days_present"] == 0
        assert result["days_absent"] == 22

    def test_absent_record_missing(self):
        # Provide only 1 of 22 work days — other 21 have no records at all
        result = ts([{"date": "2026-06-02", "check_in": "08:00", "check_out": "17:30"}])
        assert result["days_present"] == 1
        assert result["days_absent"] == 21

    def test_full_month_no_anomalies(self):
        # Generate all 22 work days in June 2026
        from datetime import date, timedelta
        import calendar
        from backend.governance.compliance_rules import VN_HOLIDAYS_2026
        records = []
        for day in range(1, 31):
            d = date(2026, 6, day)
            if d.weekday() < 5 and d not in VN_HOLIDAYS_2026:
                records.append({"date": d.strftime("%Y-%m-%d"), "check_in": "08:00", "check_out": "17:30"})
        result = ts(records)
        assert result["days_present"] == 22
        assert result["days_absent"] == 0
        # No late/early anomalies — only "Không có dữ liệu" absent anomalies should be absent
        late_anomalies = [a for a in result["anomalies"] if "muộn" in a]
        assert late_anomalies == []


# ---------------------------------------------------------------------------
# Late arrival (grace period = 5 minutes → threshold 08:05)
# ---------------------------------------------------------------------------

class TestLateArrival:
    def test_on_time_exact(self):
        result = ts([{"date": "2026-06-01", "check_in": "08:00", "check_out": "17:30"}])
        assert result["late_arrivals"] == 0

    def test_within_grace_period(self):
        result = ts([{"date": "2026-06-01", "check_in": "08:04", "check_out": "17:30"}])
        assert result["late_arrivals"] == 0

    def test_exactly_at_grace_limit(self):
        # 08:05 is exactly at the threshold — still ok (threshold is >grace, not >=)
        result = ts([{"date": "2026-06-01", "check_in": "08:05", "check_out": "17:30"}])
        assert result["late_arrivals"] == 0

    def test_one_minute_late(self):
        result = ts([{"date": "2026-06-01", "check_in": "08:06", "check_out": "17:30"}])
        assert result["late_arrivals"] == 1
        assert any("muộn" in a for a in result["anomalies"])

    def test_very_late(self):
        result = ts([{"date": "2026-06-01", "check_in": "10:00", "check_out": "17:30"}])
        assert result["late_arrivals"] == 1
        anomaly = next(a for a in result["anomalies"] if "muộn" in a)
        assert "10:00" in anomaly

    def test_multiple_late_days(self):
        result = ts([
            {"date": "2026-06-01", "check_in": "08:10", "check_out": "17:30"},
            {"date": "2026-06-02", "check_in": "08:15", "check_out": "17:30"},
            {"date": "2026-06-03", "check_in": "08:00", "check_out": "17:30"},
        ])
        assert result["late_arrivals"] == 2


# ---------------------------------------------------------------------------
# Early leave (grace period = 5 minutes → threshold 17:25)
# ---------------------------------------------------------------------------

class TestEarlyLeave:
    def test_normal_checkout(self):
        result = ts([{"date": "2026-06-01", "check_in": "08:00", "check_out": "17:30"}])
        assert result["early_leaves"] == 0

    def test_within_early_leave_grace(self):
        result = ts([{"date": "2026-06-01", "check_in": "08:00", "check_out": "17:26"}])
        assert result["early_leaves"] == 0

    def test_early_leave_detected(self):
        result = ts([{"date": "2026-06-01", "check_in": "08:00", "check_out": "17:00"}])
        assert result["early_leaves"] == 1
        assert any("sớm" in a for a in result["anomalies"])

    def test_late_and_early_same_day(self):
        result = ts([{"date": "2026-06-01", "check_in": "08:30", "check_out": "17:00"}])
        assert result["late_arrivals"] == 1
        assert result["early_leaves"] == 1
        assert len([a for a in result["anomalies"] if "muộn" in a or "sớm" in a]) == 2


# ---------------------------------------------------------------------------
# Missing check-in / check-out
# ---------------------------------------------------------------------------

class TestMissingRecord:
    def test_missing_checkin_only(self):
        result = ts([{"date": "2026-06-01", "check_in": None, "check_out": "17:30"}])
        assert any("check-in" in a for a in result["anomalies"])

    def test_missing_checkout_only(self):
        result = ts([{"date": "2026-06-01", "check_in": "08:00", "check_out": None}])
        assert any("check-out" in a for a in result["anomalies"])


# ---------------------------------------------------------------------------
# Weekend & Holiday handling
# ---------------------------------------------------------------------------

class TestWeekendAndHoliday:
    def test_saturday_not_counted_as_workday(self):
        # Jun 6, 2026 = Saturday
        result = ts([{"date": "2026-06-06", "check_in": "09:00", "check_out": "15:00"}])
        assert result["days_present"] == 0
        assert result["days_weekend"] >= 1

    def test_holiday_not_counted_as_workday(self):
        # Sep 2, 2026 = Quốc khánh (holiday)
        result = process_timesheet(
            [{"date": "2026-09-02", "check_in": "08:00", "check_out": "17:30"}],
            SCHEDULE,
            "2026-09",
        )
        assert result["days_holiday"] >= 1
        # day worked on holiday → not counted as absent or present work day
        assert result["days_present"] == 0

    def test_weekend_ot_type_label(self):
        # Jun 7, 2026 = Sunday
        result = ts([{"date": "2026-06-07", "check_in": "08:00", "check_out": "20:00"}])
        rec = next(r for r in result["records"] if r["date"] == "2026-06-07")
        assert rec["ot_type"] == "weekend"
        assert rec["overtime_hours"] > 0

    def test_holiday_ot_type_label(self):
        # May 1, 2026 = Lao động (holiday)
        result = process_timesheet(
            [{"date": "2026-05-01", "check_in": "08:00", "check_out": "20:00"}],
            SCHEDULE,
            "2026-05",
        )
        rec = next(r for r in result["records"] if r["date"] == "2026-05-01")
        assert rec["ot_type"] == "holiday"


# ---------------------------------------------------------------------------
# Overtime calculation
# ---------------------------------------------------------------------------

class TestOvertimeCalculation:
    def test_no_ot_exact_checkout(self):
        result = ts([{"date": "2026-06-01", "check_in": "08:00", "check_out": "17:30"}])
        rec = result["records"][0]
        assert rec["overtime_hours"] == 0.0

    def test_ot_2_hours(self):
        result = ts([{"date": "2026-06-01", "check_in": "08:00", "check_out": "19:30"}])
        rec = next(r for r in result["records"] if r["date"] == "2026-06-01")
        assert rec["overtime_hours"] == pytest.approx(2.0, abs=0.1)

    def test_total_hours_excludes_lunch(self):
        # 08:00–17:30 = 9.5 raw hours, minus 60 min lunch = 8.5h if raw > break+60m
        result = ts([{"date": "2026-06-01", "check_in": "08:00", "check_out": "17:30"}])
        rec = next(r for r in result["records"] if r["date"] == "2026-06-01")
        assert rec["hours_worked"] == pytest.approx(8.5, abs=0.1)


# ---------------------------------------------------------------------------
# Anomaly messages
# ---------------------------------------------------------------------------

class TestAnomalyMessages:
    def test_absent_anomaly_contains_date(self):
        result = ts([{"date": "2026-06-01", "check_in": None, "check_out": None}])
        assert any("2026-06-01" in a for a in result["anomalies"])

    def test_late_anomaly_contains_time(self):
        result = ts([{"date": "2026-06-02", "check_in": "09:15", "check_out": "17:30"}])
        anomaly = next(a for a in result["anomalies"] if "muộn" in a)
        assert "09:15" in anomaly

    def test_no_anomalies_clean_day(self):
        result = ts([{"date": "2026-06-01", "check_in": "08:00", "check_out": "17:30"}])
        late = [a for a in result["anomalies"] if "muộn" in a or "sớm" in a]
        assert late == []


# ---------------------------------------------------------------------------
# Summary fields
# ---------------------------------------------------------------------------

class TestSummaryFields:
    def test_approved_defaults_false(self):
        result = ts([{"date": "2026-06-01", "check_in": "08:00", "check_out": "17:30"}])
        assert result["approved"] is False

    def test_summary_field_is_none(self):
        result = ts([{"date": "2026-06-01", "check_in": "08:00", "check_out": "17:30"}])
        assert result["summary"] is None

    def test_total_working_days_june(self):
        # June 2026 has 22 working days (no holidays in June)
        result = ts([], month=MONTH)
        assert result["total_working_days"] == 22

    def test_records_list_populated(self):
        result = ts([{"date": "2026-06-01", "check_in": "08:00", "check_out": "17:30"}])
        assert len(result["records"]) == 30   # all 30 days of June expanded
