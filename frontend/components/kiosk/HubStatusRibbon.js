"use client"

import { AlertTriangle, ShieldCheck } from "lucide-react"
import { useSafetyStatus } from "@/lib/hooks/useSafetyStatus"
import { cn } from "@/lib/utils"

/** Voyant conformité cuisine — sans étape suggérée (évite la redondance avec les cartes). */
export function HubStatusRibbon() {
  const { openCount, isSafe, loading } = useSafetyStatus()

  return (
    <div
      className={cn(
        "flex items-center gap-3 rounded-xl border-2 px-4 py-3",
        isSafe ? "border-emerald-300 bg-emerald-50" : "border-red-300 bg-red-50",
      )}
    >
      {loading ? (
        <p className="text-[1.1rem] font-medium text-slate-600">Chargement du statut…</p>
      ) : isSafe ? (
        <>
          <ShieldCheck className="h-6 w-6 shrink-0 text-emerald-600" />
          <p className="text-[1.1rem] font-semibold text-emerald-900">
            Cuisine conforme — aucune alerte en cours
          </p>
        </>
      ) : (
        <>
          <AlertTriangle className="h-6 w-6 shrink-0 animate-pulse text-red-600" />
          <p className="text-[1.1rem] font-bold text-red-900">
            {openCount} alerte{openCount > 1 ? "s" : ""} HACCP — informez le responsable
          </p>
        </>
      )}
    </div>
  )
}
