"use client";
import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { calculateSalary } from "@/lib/api";
import { Calculator, CheckCircle2, ChevronRight, Play } from "lucide-react";

export default function SalaryPage() {
  const [empId, setEmpId] = useState("EMP001");
  const [base, setBase] = useState("15000000");
  const [ot, setOt] = useState("12");
  const [absent, setAbsent] = useState("1");
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: any) => {
    e.preventDefault();
    setLoading(true);
    setResult(null);
    try {
      const res = await calculateSalary({
        employee_id: empId,
        month: "2026-05",
        base_salary: parseFloat(base),
        overtime_hours: parseFloat(ot),
        days_absent: parseInt(absent),
        allowances: { lunch: 800000, transport: 500000 },
        deductions: { social_insurance: true, health_insurance: true, union_fee: true }
      });
      
      // Simulate polling wait for the demo
      if (res.status === "queued") {
        setTimeout(() => {
          setResult({
            gross_salary: parseFloat(base) + 800000 + 500000 + (parseFloat(ot) * 100000), // mock
            net_salary: parseFloat(base) + 800000 + 500000 + (parseFloat(ot) * 100000) * 0.9,
            deductions: { social_insurance: 1200000, health_insurance: 225000, union_fee: 150000, personal_income_tax: 0 },
            summary: `Nhân viên ${empId} tháng 5/2026: lương thực nhận ${(parseFloat(base)*0.9).toLocaleString()} VNĐ`
          });
          setLoading(false);
        }, 1500);
      }
    } catch (e) {
      console.error(e);
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Salary Calculator Agent</h1>
        <p className="text-zinc-400">Pure Python compliance calculator + LLM explanation</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader>
            <CardTitle>Input Data</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Employee ID</label>
                <Input value={empId} onChange={e=>setEmpId(e.target.value)} className="bg-zinc-950 border-zinc-800" />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Base Salary (VND)</label>
                <Input value={base} onChange={e=>setBase(e.target.value)} className="bg-zinc-950 border-zinc-800" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Overtime (hrs)</label>
                  <Input value={ot} onChange={e=>setOt(e.target.value)} className="bg-zinc-950 border-zinc-800" />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Days Absent</label>
                  <Input value={absent} onChange={e=>setAbsent(e.target.value)} className="bg-zinc-950 border-zinc-800" />
                </div>
              </div>
              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? "Processing..." : "Calculate Payroll"} <ChevronRight className="w-4 h-4 ml-2" />
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader>
            <CardTitle>Result</CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex flex-col items-center justify-center h-64 space-y-4">
                <div className="w-12 h-12 rounded-full border-4 border-blue-500/30 border-t-blue-500 animate-spin" />
                <p className="text-sm text-zinc-400">Agent is calculating and formatting...</p>
              </div>
            ) : result ? (
              <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-lg">
                  <div className="flex items-center space-x-2 text-emerald-400 font-bold text-xl mb-1">
                    <CheckCircle2 className="w-6 h-6" />
                    <span>{result.net_salary.toLocaleString()} VNĐ</span>
                  </div>
                  <p className="text-xs text-zinc-500 uppercase tracking-wider font-semibold">Net Salary</p>
                </div>

                <div className="space-y-3 text-sm">
                  <div className="flex justify-between p-2 rounded bg-zinc-950 border border-zinc-800/50">
                    <span className="text-zinc-400">Gross Salary</span>
                    <span className="font-medium">{result.gross_salary.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between p-2 rounded bg-zinc-950 border border-zinc-800/50">
                    <span className="text-zinc-400">Social Insurance</span>
                    <span className="font-medium text-rose-400">-{result.deductions.social_insurance.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between p-2 rounded bg-zinc-950 border border-zinc-800/50">
                    <span className="text-zinc-400">Health Insurance</span>
                    <span className="font-medium text-rose-400">-{result.deductions.health_insurance.toLocaleString()}</span>
                  </div>
                </div>

                <div className="p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg space-y-2">
                  <div className="flex items-center text-blue-400 text-xs font-bold uppercase tracking-wider">
                    <Calculator className="w-4 h-4 mr-2" /> AI Summary
                  </div>
                  <p className="text-sm text-zinc-300 italic leading-relaxed">
                    "{result.summary}"
                  </p>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-center h-64 text-zinc-600 text-sm">
                Submit the form to see calculation results.
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
