import { useState, useEffect, useCallback } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Real-time system metrics (queue depth, pod count, throughput …) */
export function useMetricsStream() {
  const [metrics, setMetrics] = useState<any>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const es = new EventSource(`${API_BASE}/api/v1/stream/metrics`);
    es.onmessage = (e) => {
      try { setMetrics(JSON.parse(e.data)); } catch {}
    };
    es.onerror = () => es.close();
    return () => es.close();
  }, []);

  return metrics;
}

/** Real-time job status updates for the /jobs page.
 *  Polls GET /api/v1/jobs every `intervalMs` ms (default 3 s).
 *  Falls back to simple polling because SSE requires a dedicated server endpoint;
 *  the backend already has the job list cached in memory.
 */
export function useJobStream(intervalMs = 3000) {
  const [jobs, setJobs]     = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState<string | null>(null);

  const fetchJobs = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/jobs`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setJobs(data.jobs ?? []);
      setError(null);
    } catch (e: any) {
      setError(e.message ?? "Failed to fetch jobs");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchJobs();
    const id = setInterval(fetchJobs, intervalMs);
    return () => clearInterval(id);
  }, [fetchJobs, intervalMs]);

  return { jobs, loading, error, refetch: fetchJobs };
}
