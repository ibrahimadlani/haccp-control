"use client"

import Link from "next/link"
import { ChevronRight } from "lucide-react"
import { cn } from "@/lib/utils"

export function KioskHubCard({ href, title, subtitle, stepLabel, accentColor, ringClass }) {
  return (
    <Link
      href={href}
      className={cn(
        "group flex min-h-[7.5rem] flex-1 items-center gap-4 rounded-xl border-2 border-slate-200 bg-white px-5 py-5 shadow-sm transition-all active:scale-[0.99] sm:min-h-[8rem]",
        ringClass,
        "ring-1 hover:border-slate-300 hover:shadow-md",
      )}
    >
      <div
        className={cn(
          "flex h-14 w-14 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-[1rem] font-bold uppercase tracking-wide",
          accentColor,
        )}
      >
        {stepLabel?.replace("Étape ", "") ?? "·"}
      </div>
      <div className="min-w-0 flex-1 text-left">
        <p className="text-[0.95rem] font-semibold uppercase tracking-wide text-slate-500">
          {stepLabel}
        </p>
        <h2 className="text-[1.35rem] font-bold leading-snug text-slate-900 sm:text-[1.45rem]">
          {title}
        </h2>
        {subtitle && (
          <p className="mt-1 text-[1.05rem] text-slate-600">{subtitle}</p>
        )}
      </div>
      <ChevronRight className="h-6 w-6 shrink-0 text-slate-400 transition-transform group-hover:translate-x-0.5" />
    </Link>
  )
}
