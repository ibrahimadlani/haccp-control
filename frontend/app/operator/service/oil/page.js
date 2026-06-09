"use client"

import { useEffect, useMemo, useState } from "react"
import { Loader2 } from "lucide-react"
import { OilChangeForm } from "@/components/operator/OilChangeForm"
import { KioskBackButton } from "@/components/kiosk/KioskBackButton"
import { KIOSK_PHASES } from "@/lib/kiosk/phases"
import { getOilChanges } from "@/lib/api/production"
import { loadEstablishmentToken } from "@/lib/session/establishment"
import { cn } from "@/lib/utils"

const FRYERS = ["Friteuse — Ligne self", "Friteuse — Cuisine centrale"]

function formatLastChange(iso) {
  if (!iso) return "—"
  return new Date(iso).toLocaleDateString("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  })
}

export default function OilTrackingPage() {
  const [records, setRecords] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedFryer, setSelectedFryer] = useState(null)
  const [formOpen, setFormOpen] = useState(false)

  useEffect(() => {
    const token = loadEstablishmentToken()
    if (!token) return
    getOilChanges(token)
      .then(setRecords)
      .finally(() => setLoading(false))
  }, [])

  const lastByFryer = useMemo(() => {
    const map = {}
    for (const r of records) {
      if (!map[r.fryer_name] || new Date(r.recorded_at) > new Date(map[r.fryer_name].recorded_at)) {
        map[r.fryer_name] = r
      }
    }
    return map
  }, [records])

  function openFryer(name) {
    setSelectedFryer(name)
    setFormOpen(true)
  }

  return (
    <div className="flex flex-1 flex-col gap-5">
      <div className="flex items-center justify-between gap-4">
        <KioskBackButton href={KIOSK_PHASES.service.route} />
        <div className="text-right">
          <p className="text-[0.95rem] font-semibold uppercase tracking-wide text-amber-700">
            Contrôle huile
          </p>
          <h1 className="text-[1.5rem] font-bold">Suivi par friteuse</h1>
        </div>
      </div>

      <p className="text-[1.15rem] text-slate-600">
        Touchez une friteuse pour enregistrer filtration ou changement d&apos;huile.
      </p>

      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {FRYERS.map((name) => {
            const last = lastByFryer[name]
            const overdue = last && !last.is_conforme
            return (
              <button
                key={name}
                type="button"
                onClick={() => openFryer(name)}
                className={cn(
                  "flex min-h-[10rem] flex-col items-start justify-between rounded-2xl border-2 bg-white p-5 text-left shadow-sm transition-all active:scale-[0.98]",
                  overdue ? "border-red-400 bg-red-50/50" : "border-amber-300 hover:border-amber-500",
                )}
              >
                <div>
                  <p className="text-[1.3rem] font-extrabold text-slate-900">{name}</p>
                  <p className="mt-2 text-[1.05rem] text-slate-600">
                    Dernier contrôle : {formatLastChange(last?.recorded_at)}
                  </p>
                  {last && (
                    <p className="mt-1 text-[1rem] font-medium text-slate-500">
                      {last.action === "OIL_CHANGE"
                        ? "Changement complet"
                        : `Filtration — ${last.polar_test_percent} %`}
                    </p>
                  )}
                </div>
              </button>
            )
          })}
        </div>
      )}

      <OilChangeForm
        open={formOpen}
        onOpenChange={setFormOpen}
        defaultFryer={selectedFryer}
        onRecorded={() => {
          const token = loadEstablishmentToken()
          if (token) getOilChanges(token).then(setRecords)
        }}
      />
    </div>
  )
}
