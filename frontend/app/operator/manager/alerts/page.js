"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { Loader2 } from "lucide-react"
import { toast } from "sonner"
import { KioskBackButton } from "@/components/kiosk/KioskBackButton"
import { getNonConformities } from "@/lib/api/nonconformities"
import { listComplianceCategories } from "@/lib/kiosk/complianceTracker"
import { loadEstablishmentToken } from "@/lib/session/establishment"
import { cn } from "@/lib/utils"

const FILTERS = [
  { id: "ALL", label: "Toutes" },
  { id: "OPEN", label: "À traiter" },
  { id: "URGENT", label: "Urgentes" },
  { id: "TEMPERATURE", label: "🌡️ Température" },
  { id: "RECEPTION", label: "📦 Réception" },
  { id: "DOCUMENTS", label: "📁 Documents" },
]

const WORKFLOW_LABELS = {
  TEMPERATURE: "Température critique",
  RECEPTION: "Réception",
}

function AlertCard({ severity, title, subtitle, href }) {
  const isUrgent = severity === "urgent"
  return (
    <Link
      href={href}
      className={cn(
        "block rounded-2xl border-2 bg-white p-4 shadow-sm transition-all active:scale-[0.99]",
        isUrgent ? "border-red-400 bg-red-50/40" : "border-amber-300 bg-amber-50/30",
      )}
    >
      <div className="mb-2 flex items-center gap-2">
        <span
          className={cn(
            "rounded-full px-2.5 py-0.5 text-[0.9rem] font-bold uppercase",
            isUrgent ? "bg-red-600 text-white" : "bg-amber-500 text-white",
          )}
        >
          {isUrgent ? "Urgent" : "Attention"}
        </span>
      </div>
      <p className="text-[1.25rem] font-extrabold text-slate-900">{title}</p>
      <p className="mt-1 text-[1.05rem] text-slate-600">{subtitle}</p>
    </Link>
  )
}

export default function ManagerAlertsPage() {
  const [filter, setFilter] = useState("ALL")
  const [ncs, setNcs] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = loadEstablishmentToken()
    if (!token) return
    getNonConformities(token, { limit: 50 })
      .then((res) => setNcs(res?.items ?? []))
      .catch(() => toast.error("Impossible de charger les alertes"))
      .finally(() => setLoading(false))
  }, [])

  const docAlerts = useMemo(
    () =>
      listComplianceCategories()
        .filter((c) => c.isLate)
        .map((c) => ({
          id: `doc-${c.id}`,
          kind: "DOCUMENTS",
          severity: "attention",
          title: `${c.title} en retard`,
          subtitle: `Prochain contrôle prévu le ${c.nextLabel}`,
          href: `/operator/morning/documents?type=${c.scanType}&category=${c.id}`,
        })),
    [],
  )

  const ncAlerts = useMemo(
    () =>
      ncs
        .filter((nc) => nc.status !== "CLOSED")
        .map((nc) => {
          const isTemp = nc.workflow_type === "TEMPERATURE"
          const urgent = isTemp && nc.deviation_celsius && Number(nc.deviation_celsius) >= 2
          let subtitle = new Date(nc.opened_at).toLocaleString("fr-FR")
          if (isTemp && nc.equipment_name) {
            subtitle = `${nc.equipment_name} — ${nc.measured_value ?? "?"} °C (plage ${nc.temperature_min}–${nc.temperature_max} °C)`
          }
          return {
            id: nc.id,
            kind: nc.workflow_type,
            severity: urgent ? "urgent" : "attention",
            status: nc.status,
            title: WORKFLOW_LABELS[nc.workflow_type] ?? nc.workflow_type,
            subtitle,
            href: "/operator/manager/nonconformities",
          }
        }),
    [ncs],
  )

  const allAlerts = useMemo(() => [...ncAlerts, ...docAlerts], [ncAlerts, docAlerts])

  const filtered = useMemo(() => {
    return allAlerts.filter((a) => {
      if (filter === "ALL") return true
      if (filter === "OPEN") return a.status === "OPEN" || a.kind === "DOCUMENTS"
      if (filter === "URGENT") return a.severity === "urgent"
      if (filter === "DOCUMENTS") return a.kind === "DOCUMENTS"
      return a.kind === filter
    })
  }, [allAlerts, filter])

  return (
    <div className="flex flex-1 flex-col gap-5">
      <div className="flex items-center justify-between gap-4">
        <KioskBackButton href="/operator/manager" label="MANAGER" />
        <div className="text-right">
          <p className="text-[1.1rem] text-red-700">🔔 Alertes</p>
          <h1 className="text-[1.6rem] font-extrabold">Alertes HACCP</h1>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.id}
            type="button"
            onClick={() => setFilter(f.id)}
            className={cn(
              "rounded-full border-2 px-4 py-2 text-[1.05rem] font-semibold transition-colors",
              filter === f.id
                ? "border-slate-900 bg-slate-900 text-white"
                : "border-slate-200 bg-white text-slate-700",
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin" />
        </div>
      ) : filtered.length === 0 ? (
        <p className="py-12 text-center text-[1.2rem] text-emerald-700">
          ✓ Aucune alerte pour ce filtre
        </p>
      ) : (
        <div className="space-y-3">
          {filtered.map((alert) => (
            <AlertCard
              key={alert.id}
              severity={alert.severity}
              title={alert.title}
              subtitle={alert.subtitle}
              href={alert.href}
            />
          ))}
        </div>
      )}
    </div>
  )
}
