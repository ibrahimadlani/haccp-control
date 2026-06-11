"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { ChefHat, PackageSearch, SprayCan, Thermometer } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { TemperatureRecordModal } from "@/components/haccp/TemperatureRecordModal"
import { useTimeclock } from "@/lib/contexts/TimeclockContext"
import { useOperator } from "@/lib/contexts/OperatorContext"

export default function OperatorDashboard() {
  const router = useRouter()
  const { operator } = useOperator()
  const { status, enabled } = useTimeclock()
  const firstName = operator?.name?.split(" ")[0] ?? "Opérateur"
  const [recordOpen, setRecordOpen] = useState(false)

  // When timeclock is disabled there's no presence tracking — all actions are open
  const isActive = !enabled || status === "active"

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Bonjour, {firstName}</h1>
        <p className="text-muted-foreground">Que souhaitez-vous faire ?</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className={!isActive ? "opacity-60" : ""}>
          <CardHeader>
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
              <Thermometer className="h-5 w-5 text-primary" />
            </div>
            <CardTitle className="mt-3">Relevé HACCP</CardTitle>
            <CardDescription>
              {isActive
                ? "Enregistrer une mesure de température"
                : "Pointez votre arrivée pour accéder à cette fonctionnalité"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button className="w-full" onClick={() => setRecordOpen(true)} disabled={!isActive}>
              Commencer
            </Button>
          </CardContent>
        </Card>

        <Card className={!isActive ? "opacity-60" : ""}>
          <CardHeader>
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
              <PackageSearch className="h-5 w-5 text-primary" />
            </div>
            <CardTitle className="mt-3">Réception</CardTitle>
            <CardDescription>
              {isActive
                ? "Scanner et valider une livraison"
                : "Pointez-vous pour accéder à cette fonctionnalité"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              variant="outline"
              className="w-full"
              onClick={() => router.push("/operator/reception")}
              disabled={!isActive}
            >
              Démarrer
            </Button>
          </CardContent>
        </Card>

        <Card className={!isActive ? "opacity-60" : ""}>
          <CardHeader>
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
              <ChefHat className="h-5 w-5 text-primary" />
            </div>
            <CardTitle className="mt-3">Production</CardTitle>
            <CardDescription>
              {isActive
                ? "Relevés cuisson et refroidissement"
                : "Pointez-vous pour accéder à cette fonctionnalité"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              variant="outline"
              className="w-full"
              onClick={() => router.push("/operator/production")}
              disabled={!isActive}
            >
              Démarrer
            </Button>
          </CardContent>
        </Card>

        <Card className={!isActive ? "opacity-60" : ""}>
          <CardHeader>
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
              <SprayCan className="h-5 w-5 text-primary" />
            </div>
            <CardTitle className="mt-3">Nettoyage</CardTitle>
            <CardDescription>
              {isActive
                ? "Valider le plan de nettoyage"
                : "Pointez-vous pour accéder à cette fonctionnalité"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              variant="outline"
              className="w-full"
              onClick={() => router.push("/operator/cleaning")}
              disabled={!isActive}
            >
              Démarrer
            </Button>
          </CardContent>
        </Card>
      </div>

      <TemperatureRecordModal open={recordOpen} onOpenChange={setRecordOpen} />
    </div>
  )
}
