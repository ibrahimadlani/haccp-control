"use client"

import { useEffect, useState } from "react"
import { AlertTriangle, CheckCircle2, Droplets, Loader2 } from "lucide-react"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { NumericKeypad } from "@/components/operator/NumericKeypad"
import { createOilChange, getOilChanges } from "@/lib/api/production"
import { useOperator } from "@/lib/contexts/OperatorContext"
import { loadEstablishmentToken } from "@/lib/session/establishment"
import { cn } from "@/lib/utils"

const FRYERS = ["Friteuse — Ligne self", "Friteuse — Cuisine centrale"]
const MAX_POLAR_PERCENT = 25

export function OilChangeForm({ open, onOpenChange }) {
  const { operator } = useOperator()
  const token = loadEstablishmentToken()
  const credentials = operator ? { pin: operator.pin, operatorId: operator.id } : null

  const [fryerName, setFryerName] = useState(FRYERS[0])
  const [action, setAction] = useState("FILTER")
  const [polarTest, setPolarTest] = useState("")
  const [records, setRecords] = useState([])
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const polarValue = polarTest ? parseFloat(polarTest) : null
  const polarConforme =
    action === "OIL_CHANGE" || polarValue === null ? true : polarValue <= MAX_POLAR_PERCENT

  useEffect(() => {
    if (!open || !token) return
    setLoading(true)
    getOilChanges(token)
      .then(setRecords)
      .catch(() => toast.error("Impossible de charger les contrôles huile."))
      .finally(() => setLoading(false))
  }, [open, token])

  useEffect(() => {
    if (!open) {
      setFryerName(FRYERS[0])
      setAction("FILTER")
      setPolarTest("")
    }
  }, [open])

  async function handleSubmit() {
    if (!token || !credentials) return
    if (action === "FILTER" && !polarTest.trim()) {
      toast.error("Saisissez le témoin polaire après filtration.")
      return
    }
    setSubmitting(true)
    try {
      const result = await createOilChange(token, credentials, {
        fryer_name: fryerName,
        action,
        polar_test_percent: action === "FILTER" ? polarTest : null,
      })
      setRecords((prev) => [result, ...prev])
      if (result.is_conforme) {
        toast.success(
          action === "OIL_CHANGE"
            ? "Changement d'huile enregistré"
            : `Filtration OK — témoin ${result.polar_test_percent} %`,
        )
      } else {
        toast.warning(`Témoin polaire ${result.polar_test_percent} % — changement d'huile requis`)
      }
      setPolarTest("")
    } catch (err) {
      toast.error(String(err.message))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={submitting ? undefined : onOpenChange}>
      <DialogContent className="flex max-h-[92vh] w-full max-w-lg flex-col gap-0 overflow-hidden p-0 sm:max-w-lg">
        <DialogHeader className="space-y-1 border-b px-5 py-4 text-left">
          <DialogTitle className="flex items-center gap-2 text-xl">
            <Droplets className="h-5 w-5 text-primary" />
            Huile des friteuses
          </DialogTitle>
          <DialogDescription>
            Filtration avec témoin polaire (≤ {MAX_POLAR_PERCENT} %) ou changement complet
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-5">
          <div className="space-y-1.5">
            <Label htmlFor="fryer">Friteuse</Label>
            <select
              id="fryer"
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={fryerName}
              onChange={(e) => setFryerName(e.target.value)}
              disabled={submitting}
            >
              {FRYERS.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-2">
            {[
              { value: "FILTER", label: "Filtrer l'huile", hint: "Témoin polaire" },
              { value: "OIL_CHANGE", label: "Changer l'huile", hint: "Vidange complète" },
            ].map((opt) => (
              <button
                key={opt.value}
                type="button"
                disabled={submitting}
                onClick={() => {
                  setAction(opt.value)
                  if (opt.value === "OIL_CHANGE") setPolarTest("")
                }}
                className={cn(
                  "rounded-xl border px-3 py-3 text-left transition-colors",
                  action === opt.value
                    ? "border-primary bg-primary/5"
                    : "hover:border-primary/40 hover:bg-muted/40",
                )}
              >
                <p className="text-sm font-medium">{opt.label}</p>
                <p className="text-xs text-muted-foreground">{opt.hint}</p>
              </button>
            ))}
          </div>

          {action === "FILTER" && (
            <>
              <div
                className={cn(
                  "rounded-xl border p-4 text-center",
                  polarTest && !polarConforme
                    ? "border-destructive/40 bg-destructive/5"
                    : "bg-muted/30",
                )}
              >
                <p className="text-sm text-muted-foreground">Témoin polaire</p>
                <p className="mt-2 text-4xl font-bold tabular-nums">
                  {polarTest || "—"}
                  <span className="text-2xl text-muted-foreground"> %</span>
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Seuil max {MAX_POLAR_PERCENT} %
                </p>
              </div>
              <NumericKeypad
                value={polarTest}
                onChange={setPolarTest}
                disabled={submitting}
                allowNegative={false}
              />
            </>
          )}

          <Button
            className="h-12 w-full text-base"
            variant={action === "FILTER" && polarTest && !polarConforme ? "destructive" : "default"}
            onClick={handleSubmit}
            disabled={submitting || (action === "FILTER" && !polarTest.trim())}
          >
            {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Enregistrer
          </Button>

          <div className="space-y-2 border-t pt-4">
            <p className="text-sm font-medium">Contrôles du jour</p>
            {loading ? (
              <div className="flex justify-center py-4">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            ) : records.length === 0 ? (
              <p className="text-sm text-muted-foreground">Aucun contrôle aujourd&apos;hui.</p>
            ) : (
              <ul className="divide-y rounded-lg border">
                {records.map((record) => (
                  <li key={record.id} className="flex items-center gap-3 px-3 py-3">
                    {record.is_conforme ? (
                      <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500" />
                    ) : (
                      <AlertTriangle className="h-4 w-4 shrink-0 text-destructive" />
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{record.fryer_name}</p>
                      <p className="text-xs text-muted-foreground">
                        {record.action === "OIL_CHANGE"
                          ? "Changement d'huile"
                          : `Filtration — ${record.polar_test_percent} %`}
                      </p>
                    </div>
                    <Badge variant="outline" className="shrink-0 text-xs">
                      {new Date(record.recorded_at).toLocaleTimeString("fr-FR", {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </Badge>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
