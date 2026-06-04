"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Building2, Users, UserCheck } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { PageHeader } from "@/components/shared/PageHeader"
import { StatCard } from "@/components/shared/StatCard"
import { getOrganisationOverview } from "@/lib/api/organisation"
import { loadOrganisationContext, loadOrganisationToken } from "@/lib/session/organisation"

export default function OrgOverviewPage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = loadOrganisationToken()
    const ctx = loadOrganisationContext()
    if (!token || !ctx?.organisation_id) return
    getOrganisationOverview(token, ctx.organisation_id)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const establishments = data?.establishments ?? []
  const managers = data?.managers ?? []
  const employees = data?.employees ?? []

  return (
    <div className="space-y-6">
      <PageHeader
        title={data?.organization_name ?? "Vue d'ensemble"}
        description="Tableau de bord de votre organisation"
      />

      <div className="grid grid-cols-3 gap-4">
        <StatCard label="Sites" value={establishments.length} accent="text-foreground" loading={loading} />
        <StatCard label="Managers" value={managers.length} accent="text-foreground" loading={loading} />
        <StatCard label="Employés" value={employees.length} accent="text-foreground" loading={loading} />
      </div>

      <div>
        <h2 className="mb-3 text-base font-semibold">Établissements</h2>
        {loading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[1, 2, 3].map((i) => <Skeleton key={i} className="h-28 rounded-xl" />)}
          </div>
        ) : establishments.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucun établissement</p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {establishments.map((site) => (
              <Link key={site.id} href={`/organisation/establishments/${site.id}`}>
                <Card className="cursor-pointer transition-colors hover:bg-accent">
                  <CardHeader className="pb-2">
                    <div className="flex items-center gap-2">
                      <Building2 className="h-4 w-4 text-muted-foreground" />
                      <CardTitle className="text-sm">{site.site_name}</CardTitle>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <Badge variant="outline">{site.timezone}</Badge>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
