"use client"

import { cn } from "@/lib/utils"

export function KioskProgressBar({ done, total, label = "Progression", className }) {
  const pct = total > 0 ? Math.round((done / total) * 100) : 0

  return (
    <div className={cn("rounded-2xl border-2 border-slate-200 bg-white p-4", className)}>
      <div className="mb-2 flex items-center justify-between gap-3">
        <p className="text-[1.2rem] font-bold text-slate-800">{label}</p>
        <p className="text-[1.35rem] font-extrabold text-primary tabular-nums">
          {done} / {total}
        </p>
      </div>
      <div className="h-4 overflow-hidden rounded-full bg-slate-200">
        <div
          className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-emerald-600 transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="mt-2 text-[1.05rem] font-medium text-slate-600">{pct}% complété</p>
    </div>
  )
}
