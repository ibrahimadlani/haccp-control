"use client"

import { useEffect, useState } from "react"
import { Loader2 } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { KioskBackButton } from "@/components/kiosk/KioskBackButton"
import {
  acknowledgeNonConformity,
  getNonConformities,
  postCorrectiveAction,
} from "@/lib/api/nonconformities"
import { useOperator } from "@/lib/contexts/OperatorContext"
import { loadEstablishmentToken } from "@/lib/session/establishment"

export default function ManagerNonConformitiesPage() {
  const { operator } = useOperator()
  const token = loadEstablishmentToken()
  const credentials = operator ? { pin: operator.pin, operatorId: operator.id } : null

  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null)
  const [description, setDescription] = useState("")
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!token) return
    Promise.all([
      getNonConformities(token, { status: "OPEN" }),
      getNonConformities(token, { status: "IN_PROGRESS" }),
    ])
      .then(([open, inProgress]) => {
        const merged = [...(open?.items ?? []), ...(inProgress?.items ?? [])]
        const seen = new Set()
        setItems(
          merged.filter((nc) => {
            if (seen.has(nc.id)) return false
            seen.add(nc.id)
            return true
          }),
        )
      })
      .catch(() => toast.error("Chargement impossible"))
      .finally(() => setLoading(false))
  }, [token])

  async function handleCorrective() {
    if (!selected || !description.trim() || !token || !credentials) return
    setSubmitting(true)
    try {
      await acknowledgeNonConformity(token, credentials, selected.id)
      const formData = new FormData()
      formData.append("description", description)
      await postCorrectiveAction(token, credentials, selected.id, formData)
      toast.success("Action corrective enregistrée")
      setItems((prev) => prev.filter((nc) => nc.id !== selected.id))
      setSelected(null)
      setDescription("")
    } catch (err) {
      toast.error(String(err.message))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex flex-1 flex-col gap-5">
      <div className="flex items-center justify-between">
        <KioskBackButton href="/operator/manager" label="MANAGER" />
        <h1 className="text-[1.5rem] font-extrabold">Non-conformités</h1>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin" />
        </div>
      ) : items.length === 0 ? (
        <p className="text-center text-[1.2rem] text-slate-600">Aucune NC ouverte.</p>
      ) : (
        <ul className="divide-y rounded-2xl border-2 bg-white">
          {items.map((nc) => (
            <li key={nc.id}>
              <button
                type="button"
                className={`w-full px-4 py-4 text-left ${selected?.id === nc.id ? "bg-red-50" : ""}`}
                onClick={() => setSelected(nc)}
              >
                <p className="text-[1.15rem] font-bold">{nc.workflow_type}</p>
                <p className="text-[1.05rem] text-slate-600">
                  {new Date(nc.opened_at).toLocaleString("fr-FR")} · {nc.status}
                </p>
              </button>
            </li>
          ))}
        </ul>
      )}

      {selected && (
        <div className="space-y-3 rounded-2xl border-2 border-red-200 bg-red-50 p-4">
          <p className="text-[1.15rem] font-semibold">Action corrective — {selected.workflow_type}</p>
          <Textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Marchandise jetée, colis refusé, réparation…"
            className="min-h-28 text-[1.1rem]"
          />
          <Button
            className="h-12 w-full text-[1.15rem]"
            onClick={handleCorrective}
            disabled={submitting || !description.trim()}
          >
            {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Valider l&apos;action corrective
          </Button>
        </div>
      )}
    </div>
  )
}
