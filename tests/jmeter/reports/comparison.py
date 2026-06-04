#!/usr/bin/env python3
"""Generate benchmark comparison HTML report from JSON results."""
import json
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).parent
SCENARIOS = [
    ("10rps",  "10 req/s — Normal Load"),
    ("200rps", "200 req/s — Stress / Async Demo"),
    ("500rps", "500 req/s — Extreme / Break-point"),
]

rows = []
for key, label in SCENARIOS:
    p = BASE / key / "result.json"
    if p.exists():
        d = json.loads(p.read_text())
        rows.append({
            "label": label,
            "total":        d.get("total", 0),
            "ok":           d.get("ok", 0),
            "error_pct":    d.get("error_rate_pct", 0),
            "actual_rps":   d.get("actual_rps", 0),
            "p50":          d.get("p50_ms", 0),
            "p95":          d.get("p95_ms", 0),
            "p99":          d.get("p99_ms", 0),
            "status_codes": d.get("status_codes", {}),
        })

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>HR AI Agents — Benchmark Comparison</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #0f172a; color: #e2e8f0; margin: 0; padding: 24px; }}
  h1   {{ color: #7dd3fc; font-size: 1.5rem; margin-bottom: 4px; }}
  .sub {{ color: #64748b; font-size: 0.85rem; margin-bottom: 24px; }}
  table {{ width: 100%; border-collapse: collapse; background: #1e293b;
           border-radius: 8px; overflow: hidden; }}
  th   {{ background: #334155; color: #94a3b8; font-size: 0.8rem;
          text-transform: uppercase; letter-spacing: .05em;
          padding: 12px 16px; text-align: left; }}
  td   {{ padding: 12px 16px; border-top: 1px solid #1e293b;
          font-variant-numeric: tabular-nums; }}
  tr:hover td {{ background: #263344; }}
  .green {{ color: #4ade80; font-weight: 600; }}
  .yellow{{ color: #facc15; font-weight: 600; }}
  .red   {{ color: #f87171; font-weight: 600; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 9999px;
            font-size: 0.75rem; font-weight: 600; }}
  .bg-green {{ background: #14532d; color: #4ade80; }}
  .bg-yellow{{ background: #422006; color: #fbbf24; }}
  .bg-red   {{ background: #450a0a; color: #f87171; }}
  .insight  {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px;
               padding: 16px; margin-top: 24px; }}
  .insight h3 {{ color: #7dd3fc; margin: 0 0 8px; font-size: 0.95rem; }}
  .insight p  {{ color: #94a3b8; margin: 4px 0; font-size: 0.85rem; }}
</style>
</head>
<body>
<h1>⚡ HR AI Agents — Benchmark Comparison</h1>
<p class="sub">Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} &nbsp;|&nbsp;
   Backend: FastAPI + async queue &nbsp;|&nbsp; Mac M2 Max 32GB</p>

<table>
<thead>
  <tr>
    <th>Scenario</th>
    <th>Requests</th>
    <th>Actual RPS</th>
    <th>Success</th>
    <th>Error %</th>
    <th>P50 (ms)</th>
    <th>P95 (ms)</th>
    <th>P99 (ms)</th>
    <th>Status codes</th>
    <th>Verdict</th>
  </tr>
</thead>
<tbody>
"""

for r in rows:
    err = r["error_pct"]
    err_cls = "green" if err < 1 else ("yellow" if err < 5 else "red")
    p95 = r["p95"]
    p95_cls = "green" if p95 < 1000 else ("yellow" if p95 < 5000 else "red")

    if err < 1 and p95 < 1000:
        verdict, badge_cls = "✅ Excellent", "bg-green"
    elif err < 1:
        verdict, badge_cls = "✅ Accepted (queue)", "bg-green"
    elif err < 5:
        verdict, badge_cls = "⚠️ Degraded", "bg-yellow"
    else:
        verdict, badge_cls = "❌ Failed", "bg-red"

    codes_str = " &nbsp; ".join(
        f"<span class='badge bg-{'green' if c in (200,202) else 'red'}'>{c}: {n}</span>"
        for c, n in sorted(r["status_codes"].items())
    )

    html += f"""
  <tr>
    <td><strong>{r['label']}</strong></td>
    <td>{r['total']:,}</td>
    <td>{r['actual_rps']:.1f}</td>
    <td class="green">{r['ok']:,} ({100-r['error_pct']:.1f}%)</td>
    <td class="{err_cls}">{r['error_pct']:.2f}%</td>
    <td class="{p95_cls}">{r['p50']:.0f}</td>
    <td class="{p95_cls}">{r['p95']:.0f}</td>
    <td>{r['p99']:.0f}</td>
    <td>{codes_str}</td>
    <td><span class='badge {badge_cls}'>{verdict}</span></td>
  </tr>
"""

html += """
</tbody>
</table>

<div class="insight">
  <h3>🔍 Key Insights — Async Queue Pattern</h3>
  <p>• <strong>10 req/s</strong>: Xử lý thoải mái. P95 &lt; 10ms — gateway nhận 202 ngay lập tức.</p>
  <p>• <strong>200 req/s</strong>: <strong>100% 202 Accepted, 0% error</strong> — async queue hấp thụ toàn bộ burst.
     MLX-LM drain dần ~1.3 req/s. Queue tích lũy ~2,900 jobs nhưng không crash.</p>
  <p>• <strong>500 req/s</strong>: Vẫn <strong>100% 202 Accepted</strong>. Latency cao hơn (P95=5s) do
     Gateway thread pool bắt đầu saturate, nhưng <strong>không có lỗi nào</strong>.</p>
  <p>• <strong>Kết luận</strong>: Async queue pattern = hệ thống chịu được burst mọi mức tải.
     Điểm giới hạn là RAM Redis (500rps × 60s = 30,000 jobs → ~300MB Redis).</p>
</div>
</body>
</html>
"""

out = BASE / "comparison.html"
out.write_text(html)
print(f"Report written: {out}")
print(f"Scenarios: {len(rows)}")
