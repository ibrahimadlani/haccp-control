"use client"

import { KioskBackButton } from "@/components/kiosk/KioskBackButton"
import { getPhaseConfig } from "@/lib/kiosk/phases"
import { cn } from "@/lib/utils"

export function KioskPhaseShell({ phaseId, title, children, backHref }) {
  const phase = getPhaseConfig(phaseId)

  return (
    <div
      className={cn(
        "flex min-h-0 flex-1 flex-col gap-5 rounded-2xl border border-slate-200 bg-slate-50/80 p-4 shadow-inner sm:p-6",
        phase.borderClass,
      )}
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <KioskBackButton href={backHref} />
        <div className="text-center sm:text-right">
          <p className="text-[1.2rem] font-medium text-slate-500">{phase.hubEmoji} Étape</p>
          <h1 className="text-[1.6rem] font-extrabold leading-tight text-slate-900 sm:text-[1.85rem]">
            {title ?? phase.pageTitle}
          </h1>
        </div>
      </div>
      <div className="flex-1">{children}</div>
    </div>
  )
}
