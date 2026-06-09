"use client"

import { useState } from "react"
import { CheckCircle2, Loader2, Lock } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { useDayClosure } from "@/lib/hooks/useDayClosure"
import { useOperator } from "@/lib/contexts/OperatorContext"

export function DayClosurePanel({ open, onOpenChange }) {
  const { operator } = useOperator()
  const { closedAt, isClosed, closeDay } = useDayClosure()
  const [busy, setBusy] = useState(false)

  async function handleClose() {
    setBusy(true)
    try {
      closeDay(operator?.name ?? "Opérateur")
      toast.success("Journée clôturée — registre figé pour aujourd'hui")
      onOpenChange(false)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={busy ? undefined : onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-[1.5rem]">
            <Lock className="h-6 w-6" />
            Clôturer la journée
          </DialogTitle>
          <DialogDescription className="text-[1.15rem]">
            Validation finale — les données du jour sont verrouillées pour le registre HACCP.
          </DialogDescription>
        </DialogHeader>

        {isClosed ? (
          <div className="rounded-xl border border-emerald-300 bg-emerald-50 p-4 text-center">
            <CheckCircle2 className="mx-auto h-10 w-10 text-emerald-600" />
            <p className="mt-3 text-[1.2rem] font-bold text-emerald-800">Journée déjà clôturée</p>
            <p className="mt-1 text-[1.05rem] text-emerald-700">
              {closedAt?.operator_name} —{" "}
              {new Date(closedAt.closed_at).toLocaleString("fr-FR")}
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            <p className="text-[1.15rem] leading-relaxed text-slate-600">
              Confirmez que les relevés, réceptions, production et nettoyage du jour sont terminés.
            </p>
            <Button
              className="h-14 w-full bg-violet-700 text-[1.25rem] hover:bg-violet-800"
              onClick={handleClose}
              disabled={busy}
            >
              {busy && <Loader2 className="mr-2 h-5 w-5 animate-spin" />}
              Valider la clôture
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
