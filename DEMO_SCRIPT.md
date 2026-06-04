# Demo Script — HR AI Agents (Scale AI)
**Thời lượng**: 20 phút | **URL**: http://localhost:3000

---

## Chuẩn bị trước demo (5 phút)

```bash
# 1. Start backend + frontend
./run.sh &
sleep 5

# 2. Seed 200 employee records
python3 backend/seed_demo_data.py

# 3. Verify
curl http://localhost:8000/health        # {"status":"ok"}
curl http://localhost:3000               # HTTP 200

# 4. Mở browser tabs:
#    Tab 1: http://localhost:3000/          (Dashboard)
#    Tab 2: http://localhost:3000/scale-demo
#    Tab 3: http://localhost:3000/observability
#    Tab 4: http://localhost:3000/red-team
```

---

## Flow 1 — Normal Usage (4 phút)

### 1a. Tính lương nhân viên
1. Mở **Tab 1** → `/salary`
2. Nhập:
   - Employee ID: `EMP001`
   - Month: `2026-05`
   - Base Salary: `15,000,000`
   - Overtime: `12` giờ
   - Days Absent: `1`
   - ☑ Lunch 800,000  ☑ Transport 500,000
3. Click **[Calculate →]**
4. **Demo point**: Xuất hiện `Job ID: xxxx`, status "Processing" → sau ~1s → "Completed"
5. Kết quả hiện ra: Gross / Deductions / **Net 15,328,395 VNĐ** / AI Summary tiếng Việt
6. **Nói**: *"Python tính toán theo đúng luật BHXH/BHYT/thuế TNCN 7 bậc. LLM chỉ format summary — không bao giờ tự tính toán."*

### 1b. Chấm công
1. Mở `/timesheet`
2. Upload `tests/jmeter/test-data/checkin_data.csv` (hoặc nhập manual EMP001 tháng 6/2026)
3. Click **[Process →]**
4. **Demo point**: Bảng ngày công hiện ra — 2 ngày đi muộn được highlight ⚠️
5. **Nói**: *"Grace period ±5 phút, phát hiện anomaly, hardcode ngày lễ VN."*

### 1c. Job Queue
1. Mở `/jobs`
2. **Demo point**: 2 jobs vừa completed với wait_time ~0s, duration ~0.5s
3. **Nói**: *"202 Accepted pattern — client nhận response ngay lập tức, result được poll."*

---

## Flow 2 — Scale Test (6 phút)

### Setup
1. Mở **Tab 2** `/scale-demo` và **Tab 1** `/` Dashboard **side-by-side**
2. Dashboard: Queue Depth = 0, Pods = 5, Throughput = 0 req/s

### Scale up gateway
1. Trên Scale Demo → **Control Panel** → Gateway Replicas: 2 → **[+]** → 4
2. Click **[Apply via ArgoCD]**
3. **Demo point**: LivePod Grid: 2 pods xanh → 2 pods vàng (pending) → 4 pods xanh (~15s)
4. **Nói**: *"ArgoCD sync từ Git manifest. Trong production: git push → ArgoCD detects diff → apply."*

### Chạy load test
1. JMeter Launcher → Target RPS: **200** → Click **[▶ Start Test]**
2. Dashboard live:
   - Queue Depth: 0 → tăng lên 50 → 100+ → drain dần
   - Throughput: hiện ~1-2 req/s (MLX-LM bottleneck)
   - Error Rate: **0%** (202 Accepted hết)
3. **Demo point**: Đợi 30s, chỉ ra Queue đang drain
4. **Nói**: *"200 req/s được accept 100%, không crash. Queue absorb traffic spike. MLX-LM xử lý tuần tự theo pace tự nhiên."*
5. Click **[■ Stop]**

---

## Flow 3 — Observability (5 phút)

### LLM Traces
1. Mở **Tab 3** `/observability`
2. Click vào trace đầu tiên (POST /salary/calculate)
3. **Demo point**: Span timeline hiện ra:
   ```
   agent_gateway.route     ████  2ms
   redis.cache_lookup       █   1ms   MISS
   salary_agent.process    ████████████████  600ms
     tool.salary_calculator  █   5ms
     llm.format_response   ████████████████  590ms
   redis.cache_write        █   1ms
   Total: ~600ms
   ```
4. **Nói**: *"LLM chỉ chiếm 590ms để format text. Python tính toán chỉ 5ms. Tool gọi trước LLM — không để LLM tự tính."*

### PII Protection
1. Click **[View Prompt ▼]** trên span `llm.format_response`
2. **Demo point**: Prompt hiện ra:
   ```
   "Nhân viên EMP-3412 tháng 2026-05: gross 15,xxx,xxx ..."
   ```
   → Không có tên thật, không có CMND, không có số tài khoản
3. **Nói**: *"PII masking tự động theo NĐ 13/2023/NĐ-CP. employee_id được pseudonymize — deterministic hash."*

---

## Flow 4 — Red-team Security (3 phút)

1. Mở **Tab 4** `/red-team`
2. Check tất cả suites: ☑ Prompt Injection ☑ Data Exfil ☑ Math Manipulation ☑ Jailbreak
3. Click **[▶ Run All]** — chạy ~5s
4. **Demo point**: Results hiện ra:
   ```
   Prompt Injection   12/12  ✅ LOW
   Data Exfiltration   8/8   ✅ LOW
   Math Manipulation  10/10  ✅ LOW
   Jailbreak           6/6   ✅ LOW   ← PI-12 đã fix
   ```
5. **Nói**: *"Output guardrail: nếu LLM tự ý thay số — validate_llm_output() phát hiện ngay. Tested với 36 attack cases."*

---

## Q&A Cheat Sheet

| Câu hỏi | Trả lời |
|---------|---------|
| Tại sao không dùng vLLM? | vLLM cần CUDA. Trên M2 Max dùng MLX-LM native — throughput 400-500 tok/s, tương đương A10G |
| Scale lên 2000 users? | Cần 6-8 MLX-LM instances → 32GB không đủ. Option A: 3× Mac Studio, Option B: M2 Ultra 192GB, Option C: GPU server + vLLM |
| PII compliance? | NĐ 13/2023/NĐ-CP: mask trước khi gửi LLM, pseudonymize employee_id, audit log mọi request, retention 5 năm |
| Tại sao dùng K8s cho single node? | Demo ArgoCD GitOps + HPA scaling visually. Production-ready: thêm node là scale ngay |
| Accuracy của tính lương? | 100% Python hardcode — compliance_rules.py versioned. LLM không tham gia tính toán, chỉ format. 41 unit tests |

---

## Fallback nếu có sự cố

```bash
# Backend crash → restart
pkill -f uvicorn; source venv/bin/activate && MOCK_LLM=true uvicorn backend.main:app --port 8000 &

# Frontend crash → restart  
cd frontend && npm run dev &

# Kiểm tra API
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/stream/metrics  # SSE stream
```
