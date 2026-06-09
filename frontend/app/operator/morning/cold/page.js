"use client"

import { useEffect, useMemo, useState } from "react"
import { AlertTriangle, CheckCircle2, Loader2 } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { KioskBackButton } from "@/components/kiosk/KioskBackButton"
import { KioskProgressBar } from "@/components/kiosk/KioskProgressBar"
import { NumericKeypad } from "@/components/operator/NumericKeypad"
import { KIOSK_PHASES } from "@/lib/kiosk/phases"
import { getEquipments } from "@/lib/api/equipment"
import { postTemperatureRecord } from "@/lib/api/haccp"
import { acknowledgeNonConformity, postCorrectiveAction } from "@/lib/api/nonconformities"
import { filterColdEquipments } from "@/lib/operator/canteenDay"
import { useColdChainProgress } from "@/lib/hooks/useColdChainProgress"
import { useOperator } from "@/lib/contexts/OperatorContext"
import { loadEstablishmentToken } from "@/lib/session/establishment"
import { cn } from "@/lib/utils"

export default function MorningColdPage() {
  const { operator } = useOperator()
  const token = loadEstablishmentToken()
  const credentials = operator ? { pin: operator.pin, operatorId: operator.id } : null

  const [loading, setLoading] = useState(true)
  const [equipments, setEquipments] = useState([])
  const [selectedId, setSelectedId] = useState("")
  const [temperature, setTemperature] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [ncStep, setNcStep] = useState(null)
  const [description, setDescription] = useState("")

  const coldEquipments = useMemo(() => filterColdEquipments(equipments), [equipments])
  const selected = coldEquipments.find((eq) => eq.id === selectedId) ?? null
  const { markDone, doneIds } = useColdChainProgress(equipments)
  const doneCount = doneIds.size
  const totalCount = coldEquipments.length

  useEffect(() => {
    if (!token || !credentials) return
    getEquipments(token, credentials)
      .then((data) => setEquipments(data?.items ?? data ?? []))
      .catch(() => toast.error("Impossible de charger les enceintes froides."))
      .finally(() => setLoading(false))
  }, [token, credentials])

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
        markDone(selectedId)
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
      markDone(selectedId)
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
    <div className="flex flex-1 flex-col gap-5">
      <div className="flex items-center justify-between gap-4">
        <KioskBackButton href={KIOSK_PHASES.morning.route} />
        <div className="text-right">
          <p className="text-[0.95rem] font-semibold uppercase tracking-wide text-sky-700">
            Contrôle matinal
          </p>
          <h1 className="text-[1.5rem] font-bold text-slate-900">Frigos et congélateurs</h1>
        </div>
      </div>

      <KioskProgressBar done={doneCount} total={totalCount} label="Relevés effectués" />

      {ncStep ? (
        <div className="space-y-4 rounded-xl border-2 border-red-300 bg-red-50 p-5">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-6 w-6 shrink-0 text-red-600" />
            <div>
              <p className="text-[1.2rem] font-bold text-red-900">Température hors seuil</p>
              <p className="text-[1.05rem] text-slate-700">
                {ncStep.equipmentName} — {ncStep.value} °C
              </p>
            </div>
          </div>
          <textarea
            className="min-h-24 w-full rounded-lg border border-input bg-white px-3 py-2 text-[1.1rem]"
            placeholder="Action corrective immédiate (obligatoire)…"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <Button className="h-12 w-full text-[1.1rem]" onClick={handleCorrective} disabled={submitting}>
            {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Valider l&apos;action corrective
          </Button>
        </div>
      ) : loading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : coldEquipments.length === 0 ? (
        <p className="py-12 text-center text-[1.1rem] text-slate-600">
          Aucune enceinte froide configurée.
        </p>
      ) : !selectedId ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {coldEquipments.map((eq) => {
            const done = doneIds.has(eq.id)
            return (
              <button
                key={eq.id}
                type="button"
                onClick={() => setSelectedId(eq.id)}
                className={cn(
                  "flex min-h-[5.5rem] flex-col items-start justify-center rounded-xl border-2 px-4 py-4 text-left transition-all active:scale-[0.99]",
                  done
                    ? "border-emerald-400 bg-emerald-50"
                    : "border-slate-200 bg-white hover:border-sky-400",
                )}
              >
                <div className="flex w-full items-center justify-between gap-2">
                  <p className="text-[1.2rem] font-bold text-slate-900">{eq.name}</p>
                  {done && <CheckCircle2 className="h-6 w-6 text-emerald-600" />}
                </div>
                <p className="mt-1 text-[1rem] text-slate-600">
                  Cible {eq.min_target_temperature} °C à {eq.max_target_temperature} °C
                </p>
              </button>
            )
          })}
        </div>
      ) : (
        <div className="space-y-4 rounded-xl border-2 border-slate-200 bg-white p-5">
          <button
            type="button"
            className="text-[1.05rem] font-medium text-sky-700"
            onClick={() => {
              setSelectedId("")
              setTemperature("")
            }}
          >
            ← Retour à la liste
          </button>

          <div className="rounded-xl border bg-slate-50 p-4 text-center">
            <p className="text-[1.05rem] text-slate-600">{selected?.name}</p>
            <p className="mt-2 text-4xl font-bold tabular-nums">
              {temperature || "—"}
              <span className="text-2xl text-slate-500"> °C</span>
            </p>
            <p className="mt-1 text-[1rem] text-slate-500">
              Seuil {selected?.min_target_temperature} °C — {selected?.max_target_temperature} °C
            </p>
          </div>

          <NumericKeypad value={temperature} onChange={setTemperature} disabled={submitting} />

          <Button
            className="h-14 w-full text-[1.15rem] font-semibold"
            onClick={handleSubmit}
            disabled={submitting || !temperature.trim()}
          >
            {submitting && <Loader2 className="mr-2 h-5 w-5 animate-spin" />}
            Enregistrer le relevé
          </Button>
        </div>
      )}

    </div>
  )
}
