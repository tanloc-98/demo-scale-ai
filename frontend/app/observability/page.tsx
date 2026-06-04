"use client";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Search, Activity, Clock, Box, Database, CornerDownRight } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export default function ObservabilityPage() {
  const [selectedTrace, setSelectedTrace] = useState<any>(null);

  const mockTraces = [
    {
      id: "trace-salary-EMP001-f8a2b3",
      endpoint: "POST /salary/calculate",
      job_id: "abc123",
      latency: 857,
      status: "success",
      time: "2 mins ago",
      spans: [
        { name: "agent_gateway.route", time: 2, bar: 1 },
        { name: "redis.cache_lookup", time: 1, bar: 1, info: "MISS" },
        { name: "salary_agent.process", time: 850, bar: 90 },
        { name: "tool.salary_calculator", time: 5, bar: 2, level: 1 },
        { name: "tool.tax_calculator", time: 3, bar: 2, level: 1 },
        { name: "llm.format_response", time: 840, bar: 85, level: 1, 
          info: "Prompt: 187 tkns, Output: 125 tkns" },
        { name: "redis.cache_write", time: 1, bar: 1 },
      ]
    },
    {
      id: "trace-timesheet-EMP042-9c7d41",
      endpoint: "POST /timesheet/process",
      job_id: "xyz789",
      latency: 412,
      status: "success",
      time: "5 mins ago",
      spans: []
    }
  ];

  return (
    <div className="space-y-6 h-[calc(100vh-8rem)]">
      <div className="flex flex-col space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">LLM Observability</h1>
        <p className="text-zinc-400">Distributed tracing for agents, tools, and LLM calls powered by Langfuse & OTel.</p>
      </div>

      <div className="flex items-center space-x-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-zinc-500" />
          <Input placeholder="Search traces by employee ID, job ID, or error..." className="pl-9 bg-zinc-900 border-zinc-800" />
        </div>
        <Button variant="outline" className="border-zinc-800 bg-zinc-900">Last 1h</Button>
        <Button variant="outline" className="border-zinc-800 bg-zinc-900">All Agents</Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-full">
        <Card className="lg:col-span-1 bg-zinc-900 border-zinc-800 flex flex-col h-[500px]">
          <CardHeader className="border-b border-zinc-800 pb-3">
            <CardTitle className="text-sm font-medium">Recent Traces</CardTitle>
          </CardHeader>
          <div className="overflow-y-auto flex-1">
            {mockTraces.map((t, i) => (
              <div 
                key={i} 
                onClick={() => setSelectedTrace(t)}
                className={`p-4 border-b border-zinc-800 cursor-pointer transition-colors ${selectedTrace?.id === t.id ? 'bg-zinc-800/80 border-l-4 border-l-blue-500' : 'hover:bg-zinc-800/30 border-l-4 border-l-transparent'}`}
              >
                <div className="flex justify-between items-start mb-2">
                  <span className="font-mono text-sm text-blue-400">{t.endpoint}</span>
                  <Badge variant="outline" className="text-emerald-400 border-emerald-500/30 bg-emerald-500/10 rounded-sm">200 OK</Badge>
                </div>
                <div className="flex items-center justify-between text-xs text-zinc-500">
                  <span className="font-mono">{t.id.split('-').pop()}</span>
                  <div className="flex items-center space-x-3">
                    <span className="flex items-center"><Clock className="w-3 h-3 mr-1" /> {t.latency}ms</span>
                    <span>{t.time}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card className="lg:col-span-2 bg-zinc-900 border-zinc-800 h-[500px] flex flex-col">
          {selectedTrace ? (
            <>
              <CardHeader className="border-b border-zinc-800 pb-3 bg-zinc-950/50 rounded-t-xl">
                <div className="flex justify-between items-center">
                  <div>
                    <CardTitle className="text-lg font-mono text-blue-400">{selectedTrace.endpoint}</CardTitle>
                    <p className="text-xs text-zinc-500 mt-1">Trace ID: {selectedTrace.id}</p>
                  </div>
                  <div className="text-right">
                    <div className="text-xl font-bold">{selectedTrace.latency} ms</div>
                    <p className="text-xs text-zinc-500">Total Duration</p>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="p-0 overflow-y-auto flex-1">
                <div className="p-4 space-y-1 font-mono text-sm">
                  <div className="flex text-xs text-zinc-500 mb-2 border-b border-zinc-800 pb-2">
                    <div className="w-1/2">Span Name</div>
                    <div className="w-24 text-right">Duration</div>
                    <div className="flex-1">Timeline</div>
                  </div>
                  
                  {selectedTrace.spans.map((span: any, i: number) => (
                    <div key={i} className="flex items-center py-2 hover:bg-zinc-800/30 rounded px-2 group">
                      <div className="w-1/2 flex items-center">
                        {span.level ? (
                          <CornerDownRight className="w-4 h-4 text-zinc-600 ml-4 mr-2" />
                        ) : (
                          <Activity className="w-4 h-4 text-zinc-500 mr-2" />
                        )}
                        <span className={span.name.includes("llm.") ? "text-indigo-400 font-semibold" : "text-zinc-300"}>
                          {span.name}
                        </span>
                        {span.info && (
                          <Badge variant="outline" className="ml-2 bg-zinc-950 border-zinc-700 text-[10px] text-zinc-400">
                            {span.info}
                          </Badge>
                        )}
                      </div>
                      <div className="w-24 text-right pr-4 text-zinc-400">{span.time}ms</div>
                      <div className="flex-1 flex items-center">
                        <div 
                          className={`h-2 rounded-sm ${span.name.includes("llm.") ? 'bg-indigo-500' : 'bg-blue-500'}`} 
                          style={{ width: `${span.bar}%`, minWidth: '4px' }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
                
                <div className="p-4 border-t border-zinc-800 bg-zinc-950/30">
                  <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">LLM Context Inspector</h4>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-zinc-950 border border-zinc-800 rounded p-3 text-xs font-mono text-zinc-400">
                      <div className="text-zinc-500 mb-2 border-b border-zinc-800 pb-1">Prompt Input</div>
                      "Tóm tắt kết quả lương tháng 2026-05 cho nhân viên EMP-1234..."
                    </div>
                    <div className="bg-zinc-950 border border-zinc-800 rounded p-3 text-xs font-mono text-zinc-400">
                      <div className="text-zinc-500 mb-2 border-b border-zinc-800 pb-1">LLM Output</div>
                      "Nhân viên EMP001 tháng 5/2026: Lương gross 15,800,000 VNĐ..."
                    </div>
                  </div>
                </div>
              </CardContent>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-zinc-500">
              <Box className="w-12 h-12 mb-4 opacity-20" />
              <p>Select a trace from the left to view timeline.</p>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
