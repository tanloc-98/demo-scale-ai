"use client";
import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useMetricsStream } from "@/lib/websocket";
import { CheckCircle2, Clock, XCircle, LayoutList } from "lucide-react";

export default function JobsPage() {
  const metrics = useMetricsStream();
  const [jobs, setJobs] = useState<any[]>([]);

  // Simulate jobs list based on metrics queue depth
  useEffect(() => {
    if (!metrics) return;
    
    // Auto-generate some dummy jobs based on metrics
    const q = metrics.queue_depth;
    const p = metrics.processing;
    const c = metrics.completed_today;
    
    const newJobs = [];
    
    // Add completed
    for(let i=0; i < Math.min(c, 5); i++) {
      newJobs.push({
        id: `job-${Math.floor(Math.random()*10000)}`,
        emp: `EMP${Math.floor(Math.random()*200).toString().padStart(3, '0')}`,
        type: Math.random() > 0.5 ? 'Salary' : 'Timesheet',
        status: 'completed',
        wait: '0.4s',
        dur: '1.2s'
      });
    }
    
    // Add processing
    for(let i=0; i < p; i++) {
      newJobs.push({
        id: `job-${Math.floor(Math.random()*10000)}`,
        emp: `EMP${Math.floor(Math.random()*200).toString().padStart(3, '0')}`,
        type: Math.random() > 0.5 ? 'Salary' : 'Timesheet',
        status: 'processing',
        wait: '2.1s',
        dur: '...'
      });
    }
    
    // Add queued (max 10 for UI)
    for(let i=0; i < Math.min(q, 10); i++) {
      newJobs.push({
        id: `job-${Math.floor(Math.random()*10000)}`,
        emp: `EMP${Math.floor(Math.random()*200).toString().padStart(3, '0')}`,
        type: Math.random() > 0.5 ? 'Salary' : 'Timesheet',
        status: 'queued',
        wait: 'wait ' + Math.floor(Math.random()*30) + 's',
        dur: '-'
      });
    }
    
    setJobs(newJobs);
    
  }, [metrics]);

  if (!metrics) return <div className="flex items-center justify-center h-64 text-zinc-500">Connecting to telemetry stream...</div>;

  const queueFillPercentage = Math.min(100, (metrics.queue_depth / 500) * 100);

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold tracking-tight">Job Queue Monitor</h1>
        <Badge variant="outline" className="animate-pulse bg-emerald-500/10 text-emerald-400 border-emerald-500/30">
          <span className="w-2 h-2 rounded-full bg-emerald-500 mr-2" /> Auto-refresh Live
        </Badge>
      </div>

      <Card className="bg-zinc-900 border-zinc-800">
        <CardContent className="p-6">
          <div className="grid grid-cols-3 gap-4 mb-6">
            <div className="space-y-1">
              <p className="text-sm text-zinc-500 font-medium">Queue Depth</p>
              <p className="text-3xl font-bold text-amber-500">{metrics.queue_depth}</p>
            </div>
            <div className="space-y-1">
              <p className="text-sm text-zinc-500 font-medium">Processing</p>
              <p className="text-3xl font-bold text-blue-500">{metrics.processing}</p>
            </div>
            <div className="space-y-1">
              <p className="text-sm text-zinc-500 font-medium">Done Today</p>
              <p className="text-3xl font-bold text-emerald-500">{metrics.completed_today}</p>
            </div>
          </div>
          
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-zinc-400">Queue Capacity ({metrics.queue_depth}/500)</span>
              <span className="text-zinc-500">Est. drain: {Math.ceil(metrics.queue_depth / 2)} min</span>
            </div>
            <Progress value={queueFillPercentage} className={`h-2 bg-zinc-800 ${queueFillPercentage > 80 ? "[&_[data-slot=progress-indicator]]:bg-rose-500" : "[&_[data-slot=progress-indicator]]:bg-indigo-500"}`} />
          </div>
        </CardContent>
      </Card>

      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-lg flex items-center"><LayoutList className="w-5 h-5 mr-2" /> Recent Jobs</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow className="border-zinc-800 hover:bg-zinc-800/50">
                <TableHead className="text-zinc-400">Job ID</TableHead>
                <TableHead className="text-zinc-400">Employee</TableHead>
                <TableHead className="text-zinc-400">Type</TableHead>
                <TableHead className="text-zinc-400">Status</TableHead>
                <TableHead className="text-zinc-400 text-right">Wait / Dur</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {jobs.map((job, i) => (
                <TableRow key={i} className="border-zinc-800/50 hover:bg-zinc-800/30 transition-colors">
                  <TableCell className="font-mono text-xs text-zinc-300">{job.id}</TableCell>
                  <TableCell className="font-medium text-zinc-200">{job.emp}</TableCell>
                  <TableCell>
                    <Badge variant="secondary" className="bg-zinc-800 text-zinc-300 hover:bg-zinc-700 font-normal">
                      {job.type}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {job.status === 'completed' && <div className="flex items-center text-emerald-400 text-sm"><CheckCircle2 className="w-4 h-4 mr-1.5" /> Done</div>}
                    {job.status === 'processing' && <div className="flex items-center text-blue-400 text-sm"><div className="w-3 h-3 rounded-full border-2 border-blue-400 border-t-transparent animate-spin mr-1.5" /> Proc</div>}
                    {job.status === 'queued' && <div className="flex items-center text-amber-400 text-sm"><Clock className="w-4 h-4 mr-1.5" /> Queued</div>}
                  </TableCell>
                  <TableCell className="text-right text-xs text-zinc-400 font-mono">
                    {job.wait} <span className="text-zinc-600">/</span> {job.dur}
                  </TableCell>
                </TableRow>
              ))}
              {jobs.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="text-center py-8 text-zinc-500">No jobs in queue.</TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
