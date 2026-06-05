"use client"

import { useEffect, useState } from "react"
import { CheckCircle2, Loader2 } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { KioskBackButton } from "@/components/kiosk/KioskBackButton"
import {
  acknowledgeNonConformity,
  closeNonConformity,
  getNonConformities,
  postCorrectiveAction,
} from "@/lib/api/nonconformities"
import { useOperator } from "@/lib/contexts/OperatorContext"
import { loadEstablishmentToken } from "@/lib/session/establishment"
import { cn } from "@/lib/utils"

const STATUS_LABELS = {
  OPEN: { label: "Ouvert", className: "bg-orange-100 text-orange-800" },
  IN_PROGRESS: { label: "En cours", className: "bg-blue-100 text-blue-800" },
  RESOLVED: { label: "Résolu", className: "bg-emerald-100 text-emerald-800" },
  CLOSED: { label: "Fermé", className: "bg-slate-100 text-slate-600" },
}

const WORKFLOW_LABELS = {
  TEMPERATURE: "Température",
  RECEPTION: "Réception",
}

function ncDescription(nc) {
  if (nc.workflow_type === "TEMPERATURE" && nc.equipment_name) {
    return `Température ${nc.measured_value ?? "?"} °C sur « ${nc.equipment_name} » (plage ${nc.temperature_min}–${nc.temperature_max} °C)`
  }
  return `Non-conformité ${WORKFLOW_LABELS[nc.workflow_type] ?? nc.workflow_type}`
}

export default function ManagerNonConformitiesPage() {
  const { operator } = useOperator()
  const token = loadEstablishmentToken()
  const credentials = operator ? { pin: operator.pin, operatorId: operator.id } : null

  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null)
  const [description, setDescription] = useState("")
  const [submitting, setSubmitting] = useState(false)

  async function loadItems() {
    if (!token) return
    try {
      const res = await getNonConformities(token, { limit: 50 })
      setItems((res?.items ?? []).filter((nc) => nc.status !== "CLOSED"))
    } catch {
      toast.error("Chargement impossible")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadItems()
  }, [token])

  async function handleCorrective() {
    if (!selected || !description.trim() || !token || !credentials) return
    setSubmitting(true)
    try {
      if (selected.status === "OPEN") {
        await acknowledgeNonConformity(token, credentials, selected.id)
      }
      const formData = new FormData()
      formData.append("description", description)
      await postCorrectiveAction(token, credentials, selected.id, formData)
      toast.success("Action corrective enregistrée")
      setSelected(null)
      setDescription("")
      await loadItems()
    } catch (err) {
      toast.error(String(err.message))
    } finally {
      setSubmitting(false)
    }
  }

  async function handleClose(nc) {
    if (!token) return
    setSubmitting(true)
    try {
      await closeNonConformity(token, nc.id, "Clôturé depuis la tablette manager")
      toast.success("Ticket fermé")
      setItems((prev) => prev.filter((item) => item.id !== nc.id))
      if (selected?.id === nc.id) setSelected(null)
    } catch (err) {
      toast.error(String(err.message))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex flex-1 flex-col gap-5">
      <div className="flex items-center justify-between gap-4">
        <KioskBackButton href="/operator/manager" label="MANAGER" />
        <div className="text-right">
          <p className="text-[1.1rem] text-red-700">🚨 NC</p>
          <h1 className="text-[1.6rem] font-extrabold">Non-conformités</h1>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin" />
        </div>
      ) : items.length === 0 ? (
        <p className="py-12 text-center text-[1.2rem] text-emerald-700">
          ✓ Aucune non-conformité ouverte
        </p>
      ) : (
        <div className="space-y-4">
          {items.map((nc) => {
            const status = STATUS_LABELS[nc.status] ?? STATUS_LABELS.OPEN
            const isSelected = selected?.id === nc.id
            return (
              <div
                key={nc.id}
                className={cn(
                  "rounded-2xl border-2 bg-white p-4 shadow-sm",
                  isSelected ? "border-red-400 ring-2 ring-red-200" : "border-slate-200",
                )}
              >
                <div className="mb-3 flex flex-wrap items-center gap-2">
                  <span className="rounded-lg bg-sky-100 px-2.5 py-1 text-[0.95rem] font-bold text-sky-800">
                    {String(nc.id).slice(0, 8).toUpperCase()}
                  </span>
                  <span className={cn("rounded-full px-3 py-1 text-[0.95rem] font-bold", status.className)}>
                    {status.label}
                  </span>
                  <span className="rounded-full bg-slate-100 px-3 py-1 text-[0.95rem] font-semibold text-slate-700">
                    {WORKFLOW_LABELS[nc.workflow_type] ?? nc.workflow_type}
                  </span>
                </div>

                <p className="text-[1.2rem] font-bold text-slate-900">{ncDescription(nc)}</p>
                <p className="mt-1 text-[1.05rem] text-slate-600">
                  {new Date(nc.opened_at).toLocaleString("fr-FR")} · {nc.opened_by_name}
                </p>

                {nc.status === "RESOLVED" ? (
                  <Button
                    className="mt-4 h-12 w-full text-[1.15rem] font-bold"
                    onClick={() => handleClose(nc)}
                    disabled={submitting}
                  >
                    <CheckCircle2 className="mr-2 h-5 w-5" />
                    Fermer le ticket
                  </Button>
                ) : nc.status !== "CLOSED" && (
                  <Button
                    variant={isSelected ? "secondary" : "outline"}
                    className="mt-4 h-12 w-full text-[1.15rem] font-bold"
                    onClick={() => {
                      setSelected(isSelected ? null : nc)
                      setDescription("")
                    }}
                  >
                    {isSelected ? "Annuler" : "Traiter — action corrective"}
                  </Button>
                )}
              </div>
            )
          })}
        </div>
      )}

      {selected && selected.status !== "RESOLVED" && (
        <div className="space-y-3 rounded-2xl border-2 border-red-300 bg-red-50 p-4">
          <p className="text-[1.2rem] font-bold text-red-900">Action corrective immédiate</p>
          <Textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Marchandise jetée, colis refusé, réparation effectuée…"
            className="min-h-28 text-[1.1rem]"
          />
          <Button
            className="h-14 w-full text-[1.2rem] font-bold"
            onClick={handleCorrective}
            disabled={submitting || !description.trim()}
          >
            {submitting && <Loader2 className="mr-2 h-5 w-5 animate-spin" />}
            Valider l&apos;action corrective
          </Button>
        </div>
      )}
    </div>
  )
}
