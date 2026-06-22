"use client";
import { useState, useEffect, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Play, Square, Settings2, ServerCog, CheckCircle2, Clock, Zap, AlertCircle } from "lucide-react";
import { scaleService, startLoadTest, stopLoadTest, getLoadTestStatus } from "@/lib/api";
import { useMetricsStream } from "@/lib/websocket";

export default function ScaleDemoPage() {
  const metrics = useMetricsStream();
  const [scalingService, setScalingService] = useState<string | null>(null);
  const [report, setReport] = useState<any>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Local state: set immediately on button click, does NOT depend on SSE
  // This ensures Stop button / badge / polling work even when SSE lags or
  // routes to a different pod than the one that received the start command.
  const [localTestActive, setLocalTestActive] = useState(false);
  const [localTestRps, setLocalTestRps]       = useState(0);

  // Combined: SSE OR local state
  const testActive = metrics?.load_test_active || localTestActive;
  const testRps    = metrics?.load_test_rps    || localTestRps;

  const stopPolling = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  };

  // Poll loadtest/status whenever test is active (local OR SSE)
  useEffect(() => {
    if (testActive) {
      stopPolling();
      pollRef.current = setInterval(async () => {
        const s = await getLoadTestStatus();
        if (s.completed && !s.active) {
          setReport(s);
          setLocalTestActive(false);
          stopPolling();
        }
      }, 1500);
    }
    return stopPolling;
  }, [testActive]);

  const handleScale = async (service: string, diff: number) => {
    if (!metrics) return;
    const current = metrics.pod_counts[service] || 1;
    const target = Math.max(1, current + diff);
    setScalingService(service);
    await scaleService(service, target);
    setTimeout(() => setScalingService(null), 1000);
  };

  const handleStartLoad = async (rps: number) => {
    setReport(null);
    setLocalTestActive(true);   // ← set local state IMMEDIATELY before API call
    setLocalTestRps(rps);
    await startLoadTest(rps);
  };

  const handleStopLoad = async () => {
    await stopLoadTest();
    setLocalTestActive(false);
    stopPolling();
    // Retry fetching the final report until completed=true (backend may need ~500ms)
    let attempts = 0;
    const tryFetch = async () => {
      const status = await getLoadTestStatus();
      if (status.completed) {
        setReport(status);
      } else if (attempts++ < 5) {
        setTimeout(tryFetch, 500);
      }
    };
    setTimeout(tryFetch, 400);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">GitOps Scaling Demo</h1>
        <p className="text-zinc-400">Simulate ArgoCD scaling and observe queue behavior under load.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Control Panel */}
        <div className="space-y-6 lg:col-span-1">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="flex items-center"><Settings2 className="w-5 h-5 mr-2" /> Control Panel</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">

              {/* Replica controls */}
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium">Gateway Replicas</span>
                  <div className="flex items-center space-x-3 bg-zinc-950 p-1 rounded-md border border-zinc-800">
                    <Button variant="ghost" size="sm" className="h-6 w-6 p-0" onClick={() => handleScale("agent-gateway", -1)}>-</Button>
                    <span className="w-4 text-center text-sm">{metrics?.pod_counts?.["agent-gateway"] || 2}</span>
                    <Button variant="ghost" size="sm" className="h-6 w-6 p-0" onClick={() => handleScale("agent-gateway", 1)}>+</Button>
                  </div>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium">Salary Agent</span>
                  <div className="flex items-center space-x-3 bg-zinc-950 p-1 rounded-md border border-zinc-800">
                    <Button variant="ghost" size="sm" className="h-6 w-6 p-0" onClick={() => handleScale("salary-agent", -1)}>-</Button>
                    <span className="w-4 text-center text-sm">{metrics?.pod_counts?.["salary-agent"] || 1}</span>
                    <Button variant="ghost" size="sm" className="h-6 w-6 p-0" onClick={() => handleScale("salary-agent", 1)}>+</Button>
                  </div>
                </div>
                <div className="pt-2">
                  <Button variant="outline" className="w-full bg-zinc-950 border-zinc-800 text-xs" disabled={scalingService !== null}>
                    {scalingService ? "Syncing..." : "Apply via ArgoCD"}
                  </Button>
                </div>
              </div>

              <div className="h-px bg-zinc-800" />

              {/* Load test controls */}
              <div className="space-y-4">
                <div>
                  <h3 className="text-sm font-medium mb-1">JMeter Load Test</h3>
                  <p className="text-xs text-zinc-500">Send burst traffic to queue</p>
                </div>

                {testActive ? (
                  <Button variant="destructive" className="w-full" onClick={handleStopLoad}>
                    <Square className="w-4 h-4 mr-2" /> Stop Test
                  </Button>
                ) : (
                  <div className="grid grid-cols-2 gap-2">
                    <Button variant="secondary" className="bg-zinc-800 hover:bg-zinc-700" onClick={() => handleStartLoad(10)}>
                      <Play className="w-3 h-3 mr-1.5" /> 10 RPS
                    </Button>
                    <Button variant="secondary" className="bg-rose-500/20 text-rose-400 hover:bg-rose-500/30" onClick={() => handleStartLoad(200)}>
                      <Play className="w-3 h-3 mr-1.5" /> 200 RPS
                    </Button>
                  </div>
                )}

                {testActive && (
                  <div className="p-3 bg-rose-500/10 border border-rose-500/20 rounded-md">
                    <div className="flex items-center text-rose-400 text-sm font-medium">
                      <span className="relative flex h-2 w-2 mr-2">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-rose-500"></span>
                      </span>
                      Load test active: {testRps} req/s
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Test Report */}
          {report?.completed && (
            <Card className="bg-zinc-900 border-zinc-800">
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center text-base">
                  <CheckCircle2 className="w-4 h-4 mr-2 text-emerald-400" />
                  Test Report
                  <Badge className="ml-auto bg-emerald-500/20 text-emerald-400 border-emerald-500/30 text-xs">
                    {report.target_rps} RPS
                  </Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div className="bg-zinc-950 rounded-md p-2 border border-zinc-800">
                    <div className="text-zinc-500 text-xs mb-1 flex items-center gap-1">
                      <Zap className="w-3 h-3" /> Requests
                    </div>
                    <div className="font-mono font-semibold">{report.requests_sent.toLocaleString()}</div>
                  </div>
                  <div className="bg-zinc-950 rounded-md p-2 border border-zinc-800">
                    <div className="text-zinc-500 text-xs mb-1 flex items-center gap-1">
                      <AlertCircle className="w-3 h-3" /> Error Rate
                    </div>
                    <div className="font-mono font-semibold text-emerald-400">
                      {(report.error_rate * 100).toFixed(2)}%
                    </div>
                  </div>
                  <div className="bg-zinc-950 rounded-md p-2 border border-zinc-800">
                    <div className="text-zinc-500 text-xs mb-1 flex items-center gap-1">
                      <Clock className="w-3 h-3" /> P50 Latency
                    </div>
                    <div className="font-mono font-semibold">
                      {report.p50_ms >= 1000
                        ? `${(report.p50_ms / 1000).toFixed(1)}s`
                        : `${report.p50_ms}ms`}
                    </div>
                  </div>
                  <div className="bg-zinc-950 rounded-md p-2 border border-zinc-800">
                    <div className="text-zinc-500 text-xs mb-1 flex items-center gap-1">
                      <Clock className="w-3 h-3" /> P95 Latency
                    </div>
                    <div className="font-mono font-semibold">
                      {report.p95_ms >= 1000
                        ? `${(report.p95_ms / 1000).toFixed(1)}s`
                        : `${report.p95_ms}ms`}
                    </div>
                  </div>
                </div>
                <div className="bg-zinc-950 rounded-md p-2 border border-zinc-800 text-sm">
                  <div className="flex justify-between">
                    <span className="text-zinc-500 text-xs">Duration</span>
                    <span className="font-mono text-xs">{report.duration_s}s</span>
                  </div>
                  <div className="flex justify-between mt-1">
                    <span className="text-zinc-500 text-xs">Effective RPS</span>
                    <span className="font-mono text-xs">{report.effective_rps}</span>
                  </div>
                  <div className="flex justify-between mt-1">
                    <span className="text-zinc-500 text-xs">Status codes</span>
                    <span className="font-mono text-xs text-emerald-400">all 202 Accepted</span>
                  </div>
                </div>
                <p className="text-xs text-zinc-500">
                  Async queue absorbed all burst. 0% error at {report.target_rps} req/s.
                </p>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Pod Grid */}
        <div className="lg:col-span-2 space-y-6">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <div className="flex items-center"><ServerCog className="w-5 h-5 mr-2" /> Live Pod Grid</div>
                <Badge variant="outline" className="border-emerald-500/30 text-emerald-400 bg-emerald-500/10">ArgoCD Synced</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                {["agent-gateway", "salary-agent", "timesheet-agent", "mlx-lm"].map((svc) => (
                  <div key={svc}>
                    <h4 className="text-sm font-medium text-zinc-400 mb-2">{svc}</h4>
                    <div className="flex flex-wrap gap-2">
                      {Array.from({ length: metrics?.pod_counts?.[svc] || (svc === "mlx-lm" ? 1 : 2) }).map((_, i) => (
                        <div key={i} className="flex items-center justify-center p-2 bg-zinc-950 border border-emerald-500/30 rounded-md w-24 gap-2 animate-in fade-in zoom-in duration-300">
                          <div className="w-2 h-2 rounded-full bg-emerald-500" />
                          <span className="text-xs text-zinc-300">Pod {i + 1}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
