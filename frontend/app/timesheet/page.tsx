"use client";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Upload, FileDown, Check, X, Clock, AlertTriangle, FileText } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export default function TimesheetPage() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);

  const handleProcess = () => {
    setLoading(true);
    setResult(null);
    setTimeout(() => {
      setResult({
        total_working_days: 22,
        days_present: 20,
        days_absent: 1,
        total_hours: 176.5,
        overtime_hours: 12.0,
        late_arrivals: 2,
        anomalies: [
          "2026-05-03: Không có dữ liệu chấm công",
          "2026-05-08: Về sớm 45 phút (check-out lúc 16:45)"
        ],
        records: [
          { date: "2026-05-01", check_in: "08:02", check_out: "17:35", status: "present" },
          { date: "2026-05-02", check_in: "07:55", check_out: "20:10", status: "present" },
          { date: "2026-05-03", check_in: "-", check_out: "-", status: "absent" },
          { date: "2026-05-04", check_in: "08:15", check_out: "17:40", status: "late" },
          { date: "2026-05-05", check_in: "07:50", check_out: "17:30", status: "present" },
        ],
        summary: "Tháng 5/2026, nhân viên có mặt 20/22 ngày công, làm đủ định mức 176.5h. Cần giải trình ngày vắng mặt 03/05 và đi muộn ngày 04/05."
      });
      setLoading(false);
    }, 1500);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Timesheet Processor Agent</h1>
        <p className="text-zinc-400">Upload timesheet CSV, detect anomalies & format explanation with LLM.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        <Card className="lg:col-span-1 bg-zinc-900 border-zinc-800">
          <CardHeader>
            <CardTitle>Data Upload</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            
            <div className="border-2 border-dashed border-zinc-800 rounded-lg p-8 flex flex-col items-center justify-center text-center space-y-4 hover:bg-zinc-800/50 transition-colors cursor-pointer">
              <div className="p-4 bg-zinc-800 rounded-full">
                <Upload className="w-8 h-8 text-zinc-400" />
              </div>
              <div>
                <p className="text-sm font-medium">Click to upload CSV</p>
                <p className="text-xs text-zinc-500 mt-1">checkin_data.csv (max 5MB)</p>
              </div>
            </div>
            
            <div className="flex items-center space-x-2 w-full">
              <div className="flex-1 space-y-1">
                <label className="text-xs text-zinc-500 font-medium uppercase tracking-wider">Employee</label>
                <Input value="EMP001" readOnly className="bg-zinc-950 border-zinc-800" />
              </div>
              <div className="flex-1 space-y-1">
                <label className="text-xs text-zinc-500 font-medium uppercase tracking-wider">Month</label>
                <Input value="2026-05" readOnly className="bg-zinc-950 border-zinc-800" />
              </div>
            </div>
            
            <Button onClick={handleProcess} disabled={loading} className="w-full bg-blue-600 hover:bg-blue-700">
              {loading ? (
                <><div className="w-4 h-4 mr-2 border-2 border-white/30 border-t-white rounded-full animate-spin" /> Processing...</>
              ) : (
                <><FileText className="w-4 h-4 mr-2" /> Process Timesheet</>
              )}
            </Button>
            
          </CardContent>
        </Card>

        <div className="lg:col-span-2 space-y-6">
          {result ? (
            <div className="space-y-6 animate-in fade-in slide-in-from-right-8 duration-500">
              
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-4 rounded-lg bg-zinc-900 border border-zinc-800 flex flex-col">
                  <span className="text-xs text-zinc-500 uppercase font-semibold tracking-wider">Days Present</span>
                  <span className="text-2xl font-bold text-emerald-400">{result.days_present}/{result.total_working_days}</span>
                </div>
                <div className="p-4 rounded-lg bg-zinc-900 border border-zinc-800 flex flex-col">
                  <span className="text-xs text-zinc-500 uppercase font-semibold tracking-wider">Total Hours</span>
                  <span className="text-2xl font-bold text-blue-400">{result.total_hours}</span>
                </div>
                <div className="p-4 rounded-lg bg-zinc-900 border border-zinc-800 flex flex-col">
                  <span className="text-xs text-zinc-500 uppercase font-semibold tracking-wider">Overtime</span>
                  <span className="text-2xl font-bold text-indigo-400">{result.overtime_hours}</span>
                </div>
                <div className="p-4 rounded-lg bg-zinc-900 border border-zinc-800 flex flex-col">
                  <span className="text-xs text-zinc-500 uppercase font-semibold tracking-wider">Anomalies</span>
                  <span className="text-2xl font-bold text-rose-400">{result.anomalies.length}</span>
                </div>
              </div>

              <div className="p-4 rounded-lg bg-amber-500/10 border border-amber-500/20 space-y-3">
                <div className="flex items-center font-semibold text-amber-500">
                  <AlertTriangle className="w-5 h-5 mr-2" /> Action Required: Anomalies Detected
                </div>
                <ul className="space-y-2">
                  {result.anomalies.map((a: string, i: number) => (
                    <li key={i} className="text-sm text-zinc-300 flex items-start">
                      <span className="w-1.5 h-1.5 rounded-full bg-amber-500 mt-1.5 mr-2 flex-shrink-0" />
                      {a}
                    </li>
                  ))}
                </ul>
                <div className="flex space-x-3 pt-2">
                  <Button size="sm" variant="outline" className="border-amber-500/50 text-amber-500 hover:bg-amber-500/10">Request Explanation</Button>
                </div>
              </div>
              
              <div className="p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg space-y-2">
                <div className="flex items-center text-blue-400 text-xs font-bold uppercase tracking-wider">
                  <Clock className="w-4 h-4 mr-2" /> AI Summary
                </div>
                <p className="text-sm text-zinc-300 italic leading-relaxed">
                  "{result.summary}"
                </p>
              </div>

            </div>
          ) : (
            <div className="h-full min-h-[400px] rounded-lg border border-dashed border-zinc-800 flex flex-col items-center justify-center text-zinc-500 space-y-4">
              <FileDown className="w-12 h-12 opacity-50" />
              <p>Upload a timesheet CSV to begin processing.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
