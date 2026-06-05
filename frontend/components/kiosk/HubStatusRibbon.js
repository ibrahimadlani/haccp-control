"use client"

import Link from "next/link"
import { AlertTriangle, ShieldCheck } from "lucide-react"
import { useSafetyStatus } from "@/lib/hooks/useSafetyStatus"
import { getPhaseConfig } from "@/lib/kiosk/phases"
import { getSuggestedDayPhase } from "@/lib/operator/canteenDay"
import { cn } from "@/lib/utils"

export function HubStatusRibbon() {
  const { openCount, isSafe, loading } = useSafetyStatus()
  const suggested = getPhaseConfig(getSuggestedDayPhase())

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <div
        className={cn(
          "flex items-center gap-3 rounded-2xl border-2 px-4 py-3",
          isSafe ? "border-emerald-300 bg-emerald-50" : "border-red-300 bg-red-50",
        )}
      >
        {loading ? (
          <p className="text-[1.1rem] font-medium text-slate-600">Chargement…</p>
        ) : isSafe ? (
          <>
            <ShieldCheck className="h-7 w-7 shrink-0 text-emerald-600" />
            <p className="text-[1.1rem] font-semibold text-emerald-900">
              Cuisine conforme — aucune alerte
            </p>
          </>
        ) : (
          <>
            <AlertTriangle className="h-7 w-7 shrink-0 animate-pulse text-red-600" />
            <div>
              <p className="text-[1.1rem] font-bold text-red-900">
                {openCount} alerte{openCount > 1 ? "s" : ""} HACCP
              </p>
              <Link
                href="/operator/manager/alerts"
                className="text-[1rem] font-medium text-red-700 underline"
              >
                Voir les alertes →
              </Link>
            </div>
          </>
        )}
      </div>

      <Link
        href={suggested.route}
        className={cn(
          "flex items-center gap-3 rounded-2xl border-2 px-4 py-3 transition-colors hover:opacity-90",
          suggested.borderClass,
          "bg-white",
        )}
      >
        <span className="text-3xl" aria-hidden>
          {suggested.hubEmoji}
        </span>
        <div>
          <p className="text-[1rem] text-slate-500">Étape suggérée</p>
          <p className="text-[1.15rem] font-bold text-slate-900">{suggested.hubTitle}</p>
        </div>
      </Link>
    </div>
  )
}
