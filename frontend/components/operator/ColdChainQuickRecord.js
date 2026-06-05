"use client"

import { useEffect, useMemo, useState } from "react"
import { AlertTriangle, CheckCircle2, Loader2, Snowflake } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { NumericKeypad } from "@/components/operator/NumericKeypad"
import { getEquipments } from "@/lib/api/equipment"
import { postTemperatureRecord } from "@/lib/api/haccp"
import { acknowledgeNonConformity, postCorrectiveAction } from "@/lib/api/nonconformities"
import { filterColdEquipments } from "@/lib/operator/canteenDay"
import { useOperator } from "@/lib/contexts/OperatorContext"
import { loadEstablishmentToken } from "@/lib/session/establishment"
import { cn } from "@/lib/utils"

export function ColdChainQuickRecord({ open, onOpenChange, onEquipmentDone }) {
  const { operator } = useOperator()
  const token = loadEstablishmentToken()
  const credentials = operator ? { pin: operator.pin, operatorId: operator.id } : null

  const [loading, setLoading] = useState(false)
  const [equipments, setEquipments] = useState([])
  const [selectedId, setSelectedId] = useState("")
  const [temperature, setTemperature] = useState("")
  const [doneIds, setDoneIds] = useState(() => new Set())
  const [submitting, setSubmitting] = useState(false)
  const [ncStep, setNcStep] = useState(null)
  const [description, setDescription] = useState("")

  const coldEquipments = useMemo(() => filterColdEquipments(equipments), [equipments])
  const selected = coldEquipments.find((eq) => eq.id === selectedId) ?? null
  const progress = coldEquipments.length
    ? `${doneIds.size}/${coldEquipments.length}`
    : "0/0"

  useEffect(() => {
    if (!open || !token || !credentials) return
    setLoading(true)
    getEquipments(token, credentials)
      .then((data) => setEquipments(data?.items ?? data ?? []))
      .catch(() => toast.error("Impossible de charger les enceintes froides."))
      .finally(() => setLoading(false))
  }, [open, token, credentials])

  useEffect(() => {
    if (!open) {
      setSelectedId("")
      setTemperature("")
      setNcStep(null)
      setDescription("")
    }
  }, [open])

  async function handleSubmit() {
    if (!selectedId || !temperature.trim() || !token || !credentials) return
    setSubmitting(true)
    try {
      const result = await postTemperatureRecord(token, credentials, {
        equipment_id: selectedId,
        measured_value: temperature,
        source: "MANUEL",
      })

      if (result.is_conforme) {
        toast.success(`${selected?.name ?? "Équipement"} — relevé conforme`)
        setDoneIds((prev) => new Set(prev).add(selectedId))
        onEquipmentDone?.(selectedId)
        setSelectedId("")
        setTemperature("")
      } else {
        setNcStep({
          ncId: result.nonconformity_id,
          equipmentName: selected?.name ?? "Équipement",
          value: result.measured_value,
        })
      }
    } catch (err) {
      toast.error(String(err.message))
    } finally {
      setSubmitting(false)
    }
  }

  async function handleCorrective() {
    if (!description.trim() || !ncStep || !token || !credentials) return
    setSubmitting(true)
    try {
      await acknowledgeNonConformity(token, credentials, ncStep.ncId)
      const formData = new FormData()
      formData.append("description", description)
      await postCorrectiveAction(token, credentials, ncStep.ncId, formData)
      toast.success("Non-conformité traitée")
      setDoneIds((prev) => new Set(prev).add(selectedId))
      onEquipmentDone?.(selectedId)
      setNcStep(null)
      setDescription("")
      setSelectedId("")
      setTemperature("")
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
            <Snowflake className="h-5 w-5 text-primary" />
            Mes frigos & congélateurs
          </DialogTitle>
          <DialogDescription>
            Relevé matinal — progression {progress}
          </DialogDescription>
        </DialogHeader>

        {ncStep ? (
          <div className="space-y-4 p-5">
            <div className="flex items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4">
              <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-destructive" />
              <div>
                <p className="font-semibold text-destructive">Température hors seuil</p>
                <p className="text-sm text-muted-foreground">
                  {ncStep.equipmentName} — {ncStep.value}°C
                </p>
              </div>
            </div>
            <textarea
              className="min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              placeholder="Action corrective immédiate (obligatoire)…"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
            <Button className="h-12 w-full" onClick={handleCorrective} disabled={submitting}>
              {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Valider l&apos;action corrective
            </Button>
          </div>
        ) : (
          <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-5">
            {loading ? (
              <div className="flex justify-center py-10">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : coldEquipments.length === 0 ? (
              <p className="py-8 text-center text-sm text-muted-foreground">
                Aucune enceinte froide configurée pour cet établissement.
              </p>
            ) : !selectedId ? (
              <div className="grid gap-2">
                {coldEquipments.map((eq) => {
                  const done = doneIds.has(eq.id)
                  return (
                    <button
                      key={eq.id}
                      type="button"
                      onClick={() => setSelectedId(eq.id)}
                      className={cn(
                        "flex items-center justify-between rounded-xl border px-4 py-4 text-left transition-colors",
                        done
                          ? "border-green-200 bg-green-50 dark:border-green-900 dark:bg-green-950/30"
                          : "hover:border-primary/40 hover:bg-muted/40",
                      )}
                    >
                      <div>
                        <p className="font-medium">{eq.name}</p>
                        <p className="text-xs text-muted-foreground">
                          Cible {eq.min_target_temperature}°C à {eq.max_target_temperature}°C
                        </p>
                      </div>
                      {done ? (
                        <CheckCircle2 className="h-5 w-5 text-green-600" />
                      ) : (
                        <span className="text-xs font-medium text-primary">Relever</span>
                      )}
                    </button>
                  )
                })}
              </div>
            ) : (
              <>
                <button
                  type="button"
                  className="text-left text-sm text-primary"
                  onClick={() => {
                    setSelectedId("")
                    setTemperature("")
                  }}
                >
                  ← Choisir une autre enceinte
                </button>

                <div className="rounded-xl border bg-muted/30 p-4 text-center">
                  <p className="text-sm text-muted-foreground">{selected?.name}</p>
                  <p className="mt-2 text-4xl font-bold tabular-nums tracking-tight">
                    {temperature || "—"}
                    <span className="text-2xl text-muted-foreground">°C</span>
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Seuil {selected?.min_target_temperature}°C — {selected?.max_target_temperature}°C
                  </p>
                </div>

                <NumericKeypad
                  value={temperature}
                  onChange={setTemperature}
                  disabled={submitting}
                />

                <Button
                  className="h-12 w-full text-base"
                  onClick={handleSubmit}
                  disabled={submitting || !temperature.trim()}
                >
                  {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Enregistrer
                </Button>
              </>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
