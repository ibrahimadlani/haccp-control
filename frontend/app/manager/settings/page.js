"use client"

import { useEffect, useState } from "react"
import { Clock, Lock, Loader2 } from "lucide-react"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { getEstablishmentSettings, updateEstablishmentSettings } from "@/lib/api/organisation"
import { loadEstablishmentContext, loadEstablishmentToken } from "@/lib/session/establishment"

export default function SettingsPage() {
  const [settings, setSettings] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const isOrgAdmin = loadEstablishmentContext()?.is_org_admin ?? false

  useEffect(() => {
    const token = loadEstablishmentToken()
    if (!token) return
    getEstablishmentSettings(token)
      .then(setSettings)
      .catch(() => toast.error("Impossible de charger les paramètres."))
      .finally(() => setLoading(false))
  }, [])

  async function handleTimeclockToggle(field, value) {
    const token = loadEstablishmentToken()
    if (!token || saving) return
    const optimistic = {
      ...settings,
      timeclock: { ...settings.timeclock, [field]: value },
    }
    setSettings(optimistic)
    setSaving(true)
    try {
      const updated = await updateEstablishmentSettings(token, {
        timeclock: optimistic.timeclock,
      })
      setSettings(updated)
      toast.success("Paramètres enregistrés")
    } catch {
      setSettings(settings)
      toast.error("Erreur lors de la sauvegarde.")
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Paramètres</h1>
        <p className="text-sm text-muted-foreground">Configuration des fonctionnalités du site</p>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
              <Clock className="h-5 w-5 text-primary" />
            </div>
            <div>
              <CardTitle className="text-base">Pointage</CardTitle>
              <CardDescription>Gestion des arrivées, départs et pauses des employés</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-5">
          {!isOrgAdmin && (
            <p className="flex items-center gap-1.5 rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground">
              <Lock className="h-3.5 w-3.5 shrink-0" />
              Seul l'administrateur de l'organisation peut modifier ces paramètres.
            </p>
          )}

          <div className="flex items-center justify-between gap-4">
            <div className="space-y-0.5">
              <Label htmlFor="timeclock-enabled" className="text-sm font-medium">
                Activer la fonctionnalité
              </Label>
              <p className="text-xs text-muted-foreground">
                Les employés peuvent pointer leur arrivée, départ et pauses depuis la tablette.
              </p>
            </div>
            <div className="flex items-center gap-2">
              {saving && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />}
              <Switch
                id="timeclock-enabled"
                checked={settings?.timeclock?.enabled ?? true}
                onCheckedChange={(v) => handleTimeclockToggle("enabled", v)}
                disabled={saving || !isOrgAdmin}
              />
            </div>
          </div>

          <div
            className={`flex items-center justify-between gap-4 transition-opacity ${
              settings?.timeclock?.enabled ? "opacity-100" : "pointer-events-none opacity-40"
            }`}
          >
            <div className="space-y-0.5">
              <Label htmlFor="timeclock-managers" className="text-sm font-medium">
                Appliquer aux managers
                <Badge variant="outline" className="ml-2 text-xs">
                  Tableau de bord
                </Badge>
              </Label>
              <p className="text-xs text-muted-foreground">
                Les managers voient le récapitulatif des présences dans leur tableau de bord.
              </p>
            </div>
            <div className="flex items-center gap-2">
              {saving && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />}
              <Switch
                id="timeclock-managers"
                checked={settings?.timeclock?.applies_to_managers ?? false}
                onCheckedChange={(v) => handleTimeclockToggle("applies_to_managers", v)}
                disabled={saving || !settings?.timeclock?.enabled || !isOrgAdmin}
              />
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
