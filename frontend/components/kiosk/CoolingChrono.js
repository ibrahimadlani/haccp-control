"use client"

import { useState } from "react"
import { AlertTriangle, CheckCircle2, Loader2, Timer } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useCoolingChrono } from "@/lib/hooks/useCoolingChrono"
import { cn } from "@/lib/utils"

export function CoolingChrono({ open, onOpenChange }) {
  const { active, isRunning, isOverdue, remainingLabel, start, stop } = useCoolingChrono()
  const [label, setLabel] = useState("Cellule de refroidissement")
  const [busy, setBusy] = useState(false)

  function handleStart() {
    setBusy(true)
    start(label.trim() || "Cellule de refroidissement")
    toast.success("Refroidissement démarré — 2 h maximum")
    setBusy(false)
  }

  function handleStop() {
    stop()
    toast.success("Refroidissement terminé")
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={busy ? undefined : onOpenChange}>
      <DialogContent className="max-w-md gap-0 p-0 sm:max-w-lg">
        <DialogHeader className="border-b px-5 py-4 text-left">
          <DialogTitle className="flex items-center gap-2 text-[1.5rem]">
            <Timer className="h-6 w-6 text-primary" />
            Refroidissement chrono
          </DialogTitle>
          <DialogDescription className="text-[1.1rem]">
            Compte à rebours réglementaire de 2 heures en cellule
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5 p-5">
          {isRunning ? (
            <>
              <div
                className={cn(
                  "rounded-2xl border-2 p-6 text-center",
                  isOverdue
                    ? "border-red-500 bg-red-50"
                    : "border-emerald-400 bg-emerald-50",
                )}
              >
                <p className="text-[1.2rem] font-medium text-slate-600">{active.label}</p>
                <p
                  className={cn(
                    "mt-2 font-mono text-5xl font-black tabular-nums",
                    isOverdue ? "text-red-600" : "text-emerald-700",
                  )}
                >
                  {isOverdue ? "DÉPASSÉ" : remainingLabel}
                </p>
                {isOverdue ? (
                  <p className="mt-3 flex items-center justify-center gap-2 text-[1.15rem] font-bold text-red-700">
                    <AlertTriangle className="h-5 w-5" />
                    Délai de 2 h dépassé — contrôle obligatoire
                  </p>
                ) : (
                  <p className="mt-3 text-[1.1rem] text-slate-600">Temps restant</p>
                )}
              </div>
              <Button className="h-14 w-full text-[1.25rem]" onClick={handleStop}>
                <CheckCircle2 className="mr-2 h-5 w-5" />
                Refroidissement terminé
              </Button>
            </>
          ) : (
            <>
              <div className="space-y-2">
                <Label htmlFor="chrono-label" className="text-[1.15rem]">
                  Produit / bac en refroidissement
                </Label>
                <Input
                  id="chrono-label"
                  value={label}
                  onChange={(e) => setLabel(e.target.value)}
                  className="h-12 text-[1.15rem]"
                  placeholder="ex. Ratatouille — bac GN 1/1"
                />
              </div>
              <Button
                className="h-14 w-full text-[1.25rem]"
                onClick={handleStart}
                disabled={busy}
              >
                {busy && <Loader2 className="mr-2 h-5 w-5 animate-spin" />}
                Démarrer le chrono 2 h
              </Button>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
