"use client"

import { useState } from "react"
import { Archive, ClipboardCheck, SprayCan } from "lucide-react"
import { WitnessSampleForm } from "@/components/operator/WitnessSampleForm"
import { DayClosurePanel } from "@/components/kiosk/DayClosurePanel"
import { KioskActionGrid } from "@/components/kiosk/KioskActionGrid"
import { KioskActionTile } from "@/components/kiosk/KioskActionTile"
import { KioskPhaseShell } from "@/components/kiosk/KioskPhaseShell"
import { useDayClosure } from "@/lib/hooks/useDayClosure"
import { cleaningHref } from "@/lib/kiosk/cleaningSchedule"
import { useEstablishmentFeatures } from "@/lib/hooks/useEstablishmentFeatures"

export default function ClosingPage() {
  const features = useEstablishmentFeatures()
  const { isClosed } = useDayClosure()

  const [witnessOpen, setWitnessOpen] = useState(false)
  const [closureOpen, setClosureOpen] = useState(false)

  return (
    <KioskPhaseShell phaseId="closing">
      <KioskActionGrid>
        {features.temperatureEnabled && (
          <KioskActionTile
            icon={Archive}
            title="Plats témoins"
            subtitle="Conservation 5 jours au froid positif"
            onClick={() => setWitnessOpen(true)}
          />
        )}

        {features.cleaningEnabled && (
          <KioskActionTile
            icon={SprayCan}
            title="Nettoyage après le repas"
            subtitle="Fermeture · fin de service"
            href={cleaningHref("CLOSING")}
          />
        )}

        <KioskActionTile
          icon={ClipboardCheck}
          title="Clôturer la journée"
          subtitle={isClosed ? "Journée déjà validée" : "Figer le registre HACCP"}
          variant={isClosed ? "success" : "default"}
          onClick={() => setClosureOpen(true)}
        />
      </KioskActionGrid>

      <WitnessSampleForm open={witnessOpen} onOpenChange={setWitnessOpen} />
      <DayClosurePanel open={closureOpen} onOpenChange={setClosureOpen} />
    </KioskPhaseShell>
  )
}
