import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Link from "next/link";
import { Activity, LayoutDashboard, Calculator, Clock, LayoutList, ShieldAlert, Zap } from "lucide-react";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "HR AI Agents",
  description: "Scale AI Demo",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} bg-zinc-950 text-zinc-50 min-h-screen flex flex-col`}>
        <nav className="border-b border-zinc-800 bg-zinc-900/50 backdrop-blur-md sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex items-center justify-between h-16">
              <div className="flex items-center space-x-8">
                <Link href="/" className="font-bold text-xl bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent flex items-center space-x-2">
                  <Activity className="h-6 w-6 text-blue-400" />
                  <span>Scale HR AI</span>
                </Link>
                <div className="hidden md:flex space-x-4">
                  <Link href="/" className="hover:text-blue-400 transition-colors flex items-center space-x-2 text-zinc-300 text-sm font-medium"><LayoutDashboard className="w-4 h-4" /><span>Dashboard</span></Link>
                  <Link href="/salary" className="hover:text-blue-400 transition-colors flex items-center space-x-2 text-zinc-300 text-sm font-medium"><Calculator className="w-4 h-4" /><span>Salary</span></Link>
                  <Link href="/timesheet" className="hover:text-blue-400 transition-colors flex items-center space-x-2 text-zinc-300 text-sm font-medium"><Clock className="w-4 h-4" /><span>Timesheet</span></Link>
                  <Link href="/jobs" className="hover:text-blue-400 transition-colors flex items-center space-x-2 text-zinc-300 text-sm font-medium"><LayoutList className="w-4 h-4" /><span>Jobs Queue</span></Link>
                  <Link href="/scale-demo" className="hover:text-indigo-400 transition-colors flex items-center space-x-2 text-zinc-300 text-sm font-medium"><Zap className="w-4 h-4" /><span>Scale Demo</span></Link>
                  <Link href="/red-team" className="hover:text-red-400 transition-colors flex items-center space-x-2 text-zinc-300 text-sm font-medium"><ShieldAlert className="w-4 h-4" /><span>Red-team</span></Link>
                </div>
              </div>
            </div>
          </div>
        </nav>
        <main className="flex-1 w-full max-w-7xl mx-auto p-4 sm:p-6 lg:p-8">
          {children}
        </main>
      </body>
    </html>
  );
}
