"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { WitnessSampleForm } from "@/components/operator/WitnessSampleForm"
import { DayClosurePanel } from "@/components/kiosk/DayClosurePanel"
import { KioskActionGrid } from "@/components/kiosk/KioskActionGrid"
import { KioskActionTile } from "@/components/kiosk/KioskActionTile"
import { KioskPhaseShell } from "@/components/kiosk/KioskPhaseShell"
import { useDayClosure } from "@/lib/hooks/useDayClosure"
import { useEstablishmentFeatures } from "@/lib/hooks/useEstablishmentFeatures"
import { useTimeclock } from "@/lib/contexts/TimeclockContext"

export default function ClosingPage() {
  const router = useRouter()
  const { status, enabled: timeclockEnabled } = useTimeclock()
  const features = useEstablishmentFeatures()
  const { isClosed } = useDayClosure()

  const [witnessOpen, setWitnessOpen] = useState(false)
  const [closureOpen, setClosureOpen] = useState(false)

  const isActive = !timeclockEnabled || status === "active"

  return (
    <KioskPhaseShell phaseId="closing">
      {!isActive && timeclockEnabled && (
        <Alert variant="destructive" className="mb-4 text-[1.1rem]">
          <AlertDescription>Pointez votre arrivée pour accéder aux actions.</AlertDescription>
        </Alert>
      )}

      <KioskActionGrid>
        {features.temperatureEnabled && (
          <KioskActionTile
            emoji="🍱"
            title="Plats Témoins"
            subtitle="Conservation 5 jours au froid positif"
            disabled={!isActive}
            onClick={() => setWitnessOpen(true)}
          />
        )}

        {features.cleaningEnabled && (
          <KioskActionTile
            emoji="🧼"
            title="Ménage & Plan de nettoyage"
            subtitle="Plonge, sols, plans de travail"
            disabled={!isActive}
            onClick={() => router.push("/operator/cleaning")}
          />
        )}

        <KioskActionTile
          emoji="🔒"
          title="Clôturer la Journée"
          subtitle={isClosed ? "Journée déjà validée" : "Figer le registre HACCP"}
          variant={isClosed ? "success" : "default"}
          disabled={!isActive}
          onClick={() => setClosureOpen(true)}
        />
      </KioskActionGrid>

      <WitnessSampleForm open={witnessOpen} onOpenChange={setWitnessOpen} />
      <DayClosurePanel open={closureOpen} onOpenChange={setClosureOpen} />
    </KioskPhaseShell>
  )
}
