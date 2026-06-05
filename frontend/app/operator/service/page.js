"use client"

import { useState } from "react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { AllergenBoard } from "@/components/operator/AllergenBoard"
import { CookingQuickRecord } from "@/components/operator/CookingQuickRecord"
import { OilChangeForm } from "@/components/operator/OilChangeForm"
import { OpenedProductLabelForm } from "@/components/operator/OpenedProductLabelForm"
import { CoolingChrono } from "@/components/kiosk/CoolingChrono"
import { KioskActionGrid } from "@/components/kiosk/KioskActionGrid"
import { KioskActionTile } from "@/components/kiosk/KioskActionTile"
import { KioskPhaseShell } from "@/components/kiosk/KioskPhaseShell"
import { useCoolingChrono } from "@/lib/hooks/useCoolingChrono"
import { useEstablishmentFeatures } from "@/lib/hooks/useEstablishmentFeatures"
import { useTimeclock } from "@/lib/contexts/TimeclockContext"

export default function ServicePage() {
  const { status, enabled: timeclockEnabled } = useTimeclock()
  const features = useEstablishmentFeatures()
  const chrono = useCoolingChrono()

  const [cookingOpen, setCookingOpen] = useState(false)
  const [chronoOpen, setChronoOpen] = useState(false)
  const [labelOpen, setLabelOpen] = useState(false)
  const [oilOpen, setOilOpen] = useState(false)
  const [allergenOpen, setAllergenOpen] = useState(false)

  const isActive = !timeclockEnabled || status === "active"

  return (
    <KioskPhaseShell phaseId="service">
      {!isActive && timeclockEnabled && (
        <Alert variant="destructive" className="mb-4 text-[1.1rem]">
          <AlertDescription>Pointez votre arrivée pour accéder aux actions.</AlertDescription>
        </Alert>
      )}

      <KioskActionGrid>
        {features.temperatureEnabled && (
          <KioskActionTile
            emoji="🌡️"
            title="Température des Plats"
            subtitle="Cuisson ≥ 63°C · maintien au chaud"
            disabled={!isActive}
            onClick={() => setCookingOpen(true)}
          />
        )}

        <KioskActionTile
          emoji="⏳"
          title="Refroidissement Chrono"
          subtitle={
            chrono.isRunning
              ? chrono.isOverdue
                ? "⚠️ Délai dépassé"
                : `Reste ${chrono.remainingLabel}`
              : "Compte à rebours 2 h"
          }
          badge={chrono.isOverdue ? "ALERTE" : chrono.isRunning ? "EN COURS" : null}
          variant={chrono.isOverdue ? "danger" : chrono.isRunning ? "success" : "default"}
          disabled={!isActive}
          onClick={() => setChronoOpen(true)}
        />

        <KioskActionTile
          emoji="🖨️"
          title="Ouverture d'un produit"
          subtitle="DLC secondaire · étiquette bac inox"
          disabled={!isActive}
          onClick={() => setLabelOpen(true)}
        />

        <KioskActionTile
          emoji="🧪"
          title="Huile des Friteuses"
          subtitle="Témoin polaire · changement"
          disabled={!isActive}
          onClick={() => setOilOpen(true)}
        />

        <KioskActionTile
          emoji="🌾"
          title="Tableau des Allergènes"
          subtitle="14 allergènes · plats du jour"
          disabled={!isActive}
          onClick={() => setAllergenOpen(true)}
        />
      </KioskActionGrid>

      <CookingQuickRecord open={cookingOpen} onOpenChange={setCookingOpen} />
      <CoolingChrono open={chronoOpen} onOpenChange={setChronoOpen} />
      <OpenedProductLabelForm open={labelOpen} onOpenChange={setLabelOpen} />
      <OilChangeForm open={oilOpen} onOpenChange={setOilOpen} />
      <AllergenBoard open={allergenOpen} onOpenChange={setAllergenOpen} />
    </KioskPhaseShell>
  )
}
