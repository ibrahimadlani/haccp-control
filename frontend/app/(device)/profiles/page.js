"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { Loader2, Shield } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { OperatorCard } from "@/components/auth/OperatorCard"
import { PinPadDialog } from "@/components/auth/PinPadDialog"
import { DeviceHeader } from "@/components/layout/DeviceHeader"
import { getEstablishmentUsers, postEstablishmentSession, postOperatorSession } from "@/lib/api/auth"
import { getTimeclockStatuses } from "@/lib/api/haccp"
import { getEstablishmentSettings } from "@/lib/api/organisation"
import { useOperator } from "@/lib/contexts/OperatorContext"
import {
  loadEstablishmentContext,
  loadEstablishmentId,
  loadEstablishmentToken,
  saveEstablishmentSession,
} from "@/lib/session/establishment"

function isManagerRole(role = "") {
  return /manager|admin|responsable|gerant/i.test(role)
}

export default function ProfilesPage() {
  const router = useRouter()
  const { setOperator } = useOperator()
  const [operators, setOperators] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [statusMap, setStatusMap] = useState({})

  // Operator PIN flow
  const [selectedOperator, setSelectedOperator] = useState(null)
  const [pinLoading, setPinLoading] = useState(false)
  const [pinError, setPinError] = useState(null)

  // Manager password dialog
  const [managerDialogOpen, setManagerDialogOpen] = useState(false)
  const [managerEmail, setManagerEmail] = useState("")
  const [managerPassword, setManagerPassword] = useState("")
  const [managerLoading, setManagerLoading] = useState(false)
  const [managerError, setManagerError] = useState(null)

  useEffect(() => {
    const token = loadEstablishmentToken()
    if (!token) {
      router.replace("/login")
      return
    }
    const ctx = loadEstablishmentContext()
    const etablissementId = ctx?.etablissement_id
    if (!etablissementId) {
      router.replace("/setup")
      return
    }
    Promise.all([
      getEstablishmentUsers(token, etablissementId, "SITE_EMPLOYEE"),
      getEstablishmentSettings(token).catch(() => null),
    ])
      .then(async ([usersData, settingsData]) => {
        const list = Array.isArray(usersData) ? usersData : usersData?.items ?? []
        setOperators(list.filter((u) => u.is_active !== false))
        const timeclockEnabled = settingsData?.timeclock?.enabled ?? true
        if (timeclockEnabled) {
          const statusData = await getTimeclockStatuses(token).catch(() => ({ items: [] }))
          const map = {}
          for (const item of statusData?.items ?? []) {
            map[item.operator_id] = item.status
          }
          setStatusMap(map)
        }
      })
      .catch(() => setError("Impossible de charger les profils."))
      .finally(() => setLoading(false))
  }, [router])

  async function handlePinComplete(pin) {
    if (!selectedOperator) return
    setPinLoading(true)
    setPinError(null)
    const token = loadEstablishmentToken()
    try {
      const data = await postOperatorSession({
        token,
        pin,
        operatorId: selectedOperator.id,
      })
      const role = data.role ?? data.role_name ?? ""
      setOperator({
        id: selectedOperator.id,
        pin,
        name: data.nom_complet ?? `${selectedOperator.prenom ?? ""} ${selectedOperator.nom ?? ""}`.trim(),
        role,
        is_admin: isManagerRole(role),
        raw: data,
      })
      router.replace(isManagerRole(role) ? "/manager" : "/operator")
    } catch {
      setPinError("PIN incorrect.")
      setPinLoading(false)
    }
  }

  async function handleManagerLogin(e) {
    e.preventDefault()
    const etablissement_id = loadEstablishmentId()
    setManagerLoading(true)
    setManagerError(null)
    try {
      const data = await postEstablishmentSession({ email: managerEmail, password: managerPassword, etablissement_id })
      saveEstablishmentSession({ token: data.access_token, establishment: data.establishment })
      setOperator({ id: null, pin: null, name: managerEmail, role: "MANAGER", is_admin: true, raw: data })
      setManagerDialogOpen(false)
      router.replace("/manager")
    } catch (err) {
      setManagerError(err.status === 401 ? "Identifiants incorrects." : String(err.message))
    } finally {
      setManagerLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      <DeviceHeader />

      <main className="flex-1 p-4 sm:p-6">
        <div className="mx-auto max-w-3xl space-y-6">
          <div className="flex items-center justify-between">
            <h1 className="text-xl font-semibold">Choisissez votre profil</h1>
            <Badge
              variant="outline"
              className="cursor-pointer gap-1.5 py-1.5"
              onClick={() => setManagerDialogOpen(true)}
            >
              <Shield className="h-3.5 w-3.5" />
              Accès manager
            </Badge>
          </div>

          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {loading ? (
            <div className="grid gap-4 sm:grid-cols-3">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-36 rounded-xl" />
              ))}
            </div>
          ) : operators.length === 0 ? (
            <p className="text-center text-muted-foreground">
              Aucun opérateur actif sur ce site.
            </p>
          ) : (
            <div className="grid gap-4 sm:grid-cols-3">
              {operators.map((op) => (
                <OperatorCard
                  key={op.id}
                  operator={op}
                  timeclockStatus={statusMap[op.id]}
                  onClick={() => {
                    setSelectedOperator(op)
                    setPinError(null)
                  }}
                />
              ))}
            </div>
          )}
        </div>
      </main>

      {/* Operator PIN dialog */}
      <PinPadDialog
        open={!!selectedOperator}
        onOpenChange={(open) => { if (!open) setSelectedOperator(null) }}
        title={`Bonjour, ${selectedOperator ? ((selectedOperator.prenom ?? selectedOperator.first_name ?? "") + " " + (selectedOperator.nom ?? selectedOperator.last_name ?? "")).trim() : ""}`}
        description={pinError ?? "Saisissez votre code PIN à 4 chiffres."}
        onComplete={handlePinComplete}
        loading={pinLoading}
      />

      {/* Manager password dialog */}
      <Dialog open={managerDialogOpen} onOpenChange={setManagerDialogOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Accès manager</DialogTitle>
            <DialogDescription>Connectez-vous avec vos identifiants manager.</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleManagerLogin} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="m-email">Email</Label>
              <Input
                id="m-email"
                type="email"
                value={managerEmail}
                onChange={(e) => setManagerEmail(e.target.value)}
                disabled={managerLoading}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="m-pass">Mot de passe</Label>
              <Input
                id="m-pass"
                type="password"
                value={managerPassword}
                onChange={(e) => setManagerPassword(e.target.value)}
                disabled={managerLoading}
                required
              />
            </div>
            {managerError && (
              <Alert variant="destructive">
                <AlertDescription>{managerError}</AlertDescription>
              </Alert>
            )}
            <Button type="submit" className="w-full" disabled={managerLoading}>
              {managerLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Connexion
            </Button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
