"""
Compliance Rules — Vietnam Labor Law
Versioned constants. NOT to be modified by LLM.
"""
from datetime import date

# === Insurance Rates (NĐ 58/2020/NĐ-CP) ===
SOCIAL_INSURANCE_RATE = 0.08      # BHXH employee share
HEALTH_INSURANCE_RATE = 0.015     # BHYT employee share
UNION_FEE_RATE = 0.01             # Công đoàn

# === Overtime Rates (Bộ Luật Lao Động 2019, Điều 98) ===
OVERTIME_RATE_WEEKDAY = 1.5       # Ngày thường
OVERTIME_RATE_WEEKEND = 2.0       # Cuối tuần
OVERTIME_RATE_HOLIDAY = 3.0       # Ngày lễ

# === Personal Income Tax Deductions (Luật Thuế TNCN 2023) ===
PERSONAL_DEDUCTION = 11_000_000   # Giảm trừ bản thân: 11 triệu/tháng
DEPENDENT_DEDUCTION = 4_400_000   # Giảm trừ người phụ thuộc: 4.4 triệu/người

# === Progressive Tax Brackets (Biểu thuế lũy tiến từng phần) ===
# (max_taxable_income, rate) — 7 bậc
TAX_BRACKETS = [
    (5_000_000,    0.05),   # Bậc 1: đến 5 triệu, 5%
    (10_000_000,   0.10),   # Bậc 2: 5–10 triệu, 10%
    (18_000_000,   0.15),   # Bậc 3: 10–18 triệu, 15%
    (32_000_000,   0.20),   # Bậc 4: 18–32 triệu, 20%
    (52_000_000,   0.25),   # Bậc 5: 32–52 triệu, 25%
    (80_000_000,   0.30),   # Bậc 6: 52–80 triệu, 30%
    (float("inf"), 0.35),   # Bậc 7: trên 80 triệu, 35%
]

# === Vietnam Public Holidays 2026 ===
VN_HOLIDAYS_2026 = [
    date(2026, 1, 1),    # Tết Dương lịch
    date(2026, 1, 27),   # Tết Nguyên Đán (nghỉ bù)
    date(2026, 1, 28),   # Mùng 1 Tết Bính Ngọ
    date(2026, 1, 29),   # Mùng 2 Tết
    date(2026, 1, 30),   # Mùng 3 Tết
    date(2026, 1, 31),   # Mùng 4 Tết
    date(2026, 2, 1),    # Mùng 5 Tết
    date(2026, 4, 7),    # Giỗ Tổ Hùng Vương (10/3 âm lịch)
    date(2026, 4, 30),   # Ngày Giải phóng miền Nam
    date(2026, 5, 1),    # Ngày Quốc tế Lao động
    date(2026, 9, 2),    # Quốc khánh
    date(2026, 9, 3),    # Nghỉ bù Quốc khánh
]

# === Standard Work Schedule ===
STANDARD_WORK_HOURS_PER_DAY = 8
STANDARD_WORK_DAYS_PER_MONTH = 22
WORK_START_TIME = "08:00"
WORK_END_TIME = "17:30"
LUNCH_BREAK_MINUTES = 60
GRACE_PERIOD_MINUTES = 5

# === Compliance Version ===
COMPLIANCE_VERSION = "2024.1"
EFFECTIVE_DATE = "2024-01-01"
