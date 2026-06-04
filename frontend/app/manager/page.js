"use client"

import { useEffect, useState } from "react"
import { UserCheck, Coffee, LogOut } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { PageHeader } from "@/components/shared/PageHeader"
import { StatCard } from "@/components/shared/StatCard"
import { getTimeclockStatuses } from "@/lib/api/haccp"
import { getNonConformityStats } from "@/lib/api/nonconformities"
import { getEstablishmentSettings } from "@/lib/api/organisation"
import { loadEstablishmentToken } from "@/lib/session/establishment"

const STATUS_CONFIG = {
  active: { label: "En service", icon: UserCheck, color: "text-emerald-600", dot: "bg-green-500" },
  on_break: { label: "En pause", icon: Coffee, color: "text-amber-600", dot: "bg-yellow-400" },
  clocked_out: { label: "Non pointé", icon: LogOut, color: "text-muted-foreground", dot: "bg-gray-300" },
}

export default function ManagerDashboard() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [timeclockStatuses, setTimeclockStatuses] = useState(null)
  const [showTimeclock, setShowTimeclock] = useState(false)

  useEffect(() => {
    const token = loadEstablishmentToken()
    if (!token) return

    Promise.all([
      getNonConformityStats(token).catch(() => null),
      getEstablishmentSettings(token).catch(() => null),
    ]).then(async ([statsData, settingsData]) => {
      if (statsData) setStats(statsData)
      const applies = settingsData?.timeclock?.enabled && settingsData?.timeclock?.applies_to_managers
      setShowTimeclock(applies ?? false)
      if (applies) {
        const statusData = await getTimeclockStatuses(token).catch(() => null)
        if (statusData) setTimeclockStatuses(statusData.items ?? [])
      }
    }).finally(() => setLoading(false))
  }, [])

  const kpis = [
    { label: "Total", value: stats?.total ?? 0, accent: "text-foreground" },
    { label: "Ouvertes", value: stats?.total_open ?? 0, accent: "text-destructive" },
    { label: "En cours", value: stats?.total_in_progress ?? 0, accent: "text-amber-600" },
    { label: "Résolues", value: stats?.total_resolved ?? 0, accent: "text-emerald-600" },
    { label: "Clôturées", value: stats?.total_closed ?? 0, accent: "text-muted-foreground" },
  ]

  const activeCount = timeclockStatuses?.filter((s) => s.status === "active").length ?? 0
  const onBreakCount = timeclockStatuses?.filter((s) => s.status === "on_break").length ?? 0

  return (
    <div className="space-y-6">
      <PageHeader
        title="Tableau de bord"
        description="Vue d'ensemble des non-conformités HACCP"
      />
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
        {kpis.map((kpi) => (
          <StatCard
            key={kpi.label}
            label={kpi.label}
            value={kpi.value}
            accent={kpi.accent}
            loading={loading}
          />
        ))}
      </div>

      {showTimeclock && timeclockStatuses !== null && (
        <div className="space-y-3">
          <h2 className="text-sm font-medium text-muted-foreground">Présences en cours</h2>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">En service</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold text-emerald-600">{activeCount}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">En pause</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold text-amber-600">{onBreakCount}</p>
              </CardContent>
            </Card>
          </div>

          {timeclockStatuses.filter((s) => s.status !== "clocked_out").length > 0 && (
            <Card>
              <CardContent className="pt-4">
                <ul className="divide-y">
                  {timeclockStatuses
                    .filter((s) => s.status !== "clocked_out")
                    .map((item) => {
                      const cfg = STATUS_CONFIG[item.status] ?? STATUS_CONFIG.clocked_out
                      return (
                        <li key={item.operator_id} className="flex items-center gap-3 py-2.5">
                          <span className={`h-2.5 w-2.5 rounded-full flex-shrink-0 ${cfg.dot}`} />
                          <span className="flex-1 text-sm">
                            {item.operator_name ?? item.operator_id}
                          </span>
                          <span className={`text-xs font-medium ${cfg.color}`}>{cfg.label}</span>
                        </li>
                      )
                    })}
                </ul>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}
