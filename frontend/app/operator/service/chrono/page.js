"use client"

import { useState } from "react"
import { AlertTriangle, CheckCircle2, Loader2, Timer } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { KioskBackButton } from "@/components/kiosk/KioskBackButton"
import { KIOSK_PHASES } from "@/lib/kiosk/phases"
import { useCoolingChrono } from "@/lib/hooks/useCoolingChrono"
import { cn } from "@/lib/utils"

export default function CoolingChronoPage() {
  const { active, isRunning, isOverdue, remainingLabel, start, stop } = useCoolingChrono()
  const [label, setLabel] = useState("Cellule de refroidissement")
  const [busy, setBusy] = useState(false)

  function handleStart() {
    setBusy(true)
    start(label.trim() || "Cellule de refroidissement")
    toast.success("Chrono démarré — 2 h maximum")
    setBusy(false)
  }

  function handleStop() {
    stop()
    toast.success("Refroidissement terminé")
  }

  return (
    <div className="mx-auto flex w-full max-w-lg flex-1 flex-col gap-5">
      <div className="flex items-center justify-between gap-4">
        <KioskBackButton href={KIOSK_PHASES.service.route} />
        <h1 className="text-[1.5rem] font-bold">Refroidissement chrono</h1>
      </div>

      <div
        className={cn(
          "rounded-xl border-2 p-6 text-center",
          isOverdue
            ? "border-red-500 bg-red-50"
            : isRunning
              ? "border-orange-400 bg-orange-50"
              : "border-slate-200 bg-white",
        )}
      >
        <Timer className="mx-auto mb-3 h-10 w-10 text-slate-700" />
        {isRunning ? (
          <>
            <p className="text-[1.1rem] font-semibold text-slate-700">{active?.label}</p>
            <p
              className={cn(
                "mt-2 text-4xl font-bold tabular-nums",
                isOverdue ? "text-red-700" : "text-orange-800",
              )}
            >
              {isOverdue ? "00:00:00" : remainingLabel}
            </p>
            <p className="mt-2 text-[1.05rem] text-slate-600">
              {isOverdue
                ? "Délai réglementaire dépassé — séparer ou jeter"
                : "Temps restant avant fin de refroidissement"}
            </p>
          </>
        ) : (
          <p className="text-[1.1rem] text-slate-600">Aucun refroidissement en cours</p>
        )}
      </div>

      {!isRunning ? (
        <div className="space-y-3 rounded-xl border-2 border-slate-200 bg-white p-4">
          <div className="space-y-1">
            <Label className="text-[1rem]">Équipement / préparation</Label>
            <Input
              className="h-11 text-[1.05rem]"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="Cellule de refroidissement"
            />
          </div>
          <Button className="h-14 w-full text-[1.15rem] font-semibold" onClick={handleStart} disabled={busy}>
            {busy && <Loader2 className="mr-2 h-5 w-5 animate-spin" />}
            Démarrer le chrono (2 h)
          </Button>
        </div>
      ) : (
        <div className="space-y-3">
          {isOverdue ? (
            <div className="flex items-start gap-3 rounded-xl border-2 border-red-400 bg-red-50 p-4">
              <AlertTriangle className="h-6 w-6 shrink-0 text-red-600" />
              <p className="text-[1.05rem] font-medium text-red-900">
                Le refroidissement a dépassé 2 heures. Vérifiez la température et appliquez la procédure HACCP.
              </p>
            </div>
          ) : (
            <div className="flex items-start gap-3 rounded-xl border-2 border-emerald-400 bg-emerald-50 p-4">
              <CheckCircle2 className="h-6 w-6 shrink-0 text-emerald-600" />
              <p className="text-[1.05rem] text-emerald-900">
                Refroidissement en cours — le chrono reste visible sur le menu production.
              </p>
            </div>
          )}
          <Button
            variant="outline"
            className="h-14 w-full text-[1.15rem] font-semibold"
            onClick={handleStop}
          >
            Terminer le refroidissement
          </Button>
        </div>
      )}
    </div>
  )
}
