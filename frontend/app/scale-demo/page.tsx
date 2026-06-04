"use client";
import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Play, Square, Settings2, Server, ServerCog } from "lucide-react";
import { scaleService, startLoadTest, stopLoadTest } from "@/lib/api";
import { useMetricsStream } from "@/lib/websocket";

export default function ScaleDemoPage() {
  const metrics = useMetricsStream();
  const [scalingService, setScalingService] = useState<string | null>(null);

  const handleScale = async (service: string, diff: number) => {
    if (!metrics) return;
    const current = metrics.pod_counts[service] || 1;
    const target = Math.max(1, current + diff);
    setScalingService(service);
    await scaleService(service, target);
    setTimeout(() => setScalingService(null), 1000);
  };

  const handleStartLoad = async (rps: number) => {
    await startLoadTest(rps);
  };

  const handleStopLoad = async () => {
    await stopLoadTest();
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">GitOps Scaling Demo</h1>
        <p className="text-zinc-400">Simulate ArgoCD scaling and observe queue behavior under load.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="space-y-6 lg:col-span-1">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="flex items-center"><Settings2 className="w-5 h-5 mr-2" /> Control Panel</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              
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

              <div className="h-px bg-zinc-800 my-4" />

              <div className="space-y-4">
                <div>
                  <h3 className="text-sm font-medium mb-1">JMeter Load Test</h3>
                  <p className="text-xs text-zinc-500">Send burst traffic to queue</p>
                </div>
                
                {metrics?.load_test_active ? (
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
                
                {metrics?.load_test_active && (
                  <div className="p-3 bg-rose-500/10 border border-rose-500/20 rounded-md">
                    <div className="flex items-center text-rose-400 text-sm font-medium">
                      <span className="relative flex h-2 w-2 mr-2">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-rose-500"></span>
                      </span>
                      Load test active: {metrics.load_test_rps} req/s
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

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
                      {Array.from({ length: metrics?.pod_counts?.[svc] || (svc === 'mlx-lm' ? 1 : 2) }).map((_, i) => (
                        <div key={i} className="flex items-center justify-center p-2 bg-zinc-950 border border-emerald-500/30 rounded-md w-24 gap-2 animate-in fade-in zoom-in duration-300">
                          <div className="w-2 h-2 rounded-full bg-emerald-500" />
                          <span className="text-xs text-zinc-300">Pod {i+1}</span>
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
