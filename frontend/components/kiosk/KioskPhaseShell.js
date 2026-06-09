"use client"

import { KioskBackButton } from "@/components/kiosk/KioskBackButton"
import { getPhaseConfig } from "@/lib/kiosk/phases"
import { cn } from "@/lib/utils"

export function KioskPhaseShell({ phaseId, title, children, backHref }) {
  const phase = getPhaseConfig(phaseId)

  return (
    <div
      className={cn(
        "flex min-h-0 flex-1 flex-col gap-5 rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6",
        phase.borderClass,
      )}
    >
      <div className="flex flex-col gap-3 border-b border-slate-100 pb-4 sm:flex-row sm:items-center sm:justify-between">
        <KioskBackButton href={backHref} />
        <div className="text-left sm:text-right">
          <p className={cn("text-[0.95rem] font-semibold uppercase tracking-wide", phase.accentColor)}>
            {phase.stepLabel}
          </p>
          <h1 className="text-[1.5rem] font-bold leading-tight text-slate-900 sm:text-[1.65rem]">
            {title ?? phase.pageTitle}
          </h1>
        </div>
      </div>
      <div className="flex-1">{children}</div>
    </div>
  )
}
