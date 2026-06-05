"use client"

import { AlertTriangle, ShieldCheck } from "lucide-react"
import { useSafetyStatus } from "@/lib/hooks/useSafetyStatus"
import { cn } from "@/lib/utils"

export function KioskFooter() {
  const { openCount, isSafe, loading } = useSafetyStatus()

  return (
    <footer
      className={cn(
        "kiosk-footer fixed inset-x-0 bottom-0 z-40 border-t-2 px-4 py-3 text-center shadow-[0_-4px_24px_rgba(0,0,0,0.15)]",
        isSafe
          ? "border-emerald-500 bg-emerald-600 text-white"
          : "kiosk-footer-alert border-red-600 bg-red-600 text-white",
      )}
      role="status"
      aria-live="polite"
    >
      <div className="mx-auto flex max-w-4xl items-center justify-center gap-3">
        {loading ? (
          <p className="text-[1.2rem] font-semibold">Vérification sécurité…</p>
        ) : isSafe ? (
          <>
            <ShieldCheck className="h-7 w-7 shrink-0" />
            <p className="text-[1.2rem] font-bold sm:text-[1.35rem]">
              Aucun incident aujourd&apos;hui. Tout est conforme !
            </p>
          </>
        ) : (
          <>
            <AlertTriangle className="h-7 w-7 shrink-0 animate-pulse" />
            <p className="text-[1.2rem] font-bold sm:text-[1.35rem]">
              {openCount} non-conformité{openCount > 1 ? "s" : ""} en attente — alertez le chef !
            </p>
          </>
        )}
      </div>
    </footer>
  )
}
