"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { ColdChainQuickRecord } from "@/components/operator/ColdChainQuickRecord"
import { KioskActionGrid } from "@/components/kiosk/KioskActionGrid"
import { KioskActionTile } from "@/components/kiosk/KioskActionTile"
import { KioskPhaseShell } from "@/components/kiosk/KioskPhaseShell"
import { getEquipments } from "@/lib/api/equipment"
import { useColdChainProgress } from "@/lib/hooks/useColdChainProgress"
import { useEstablishmentFeatures } from "@/lib/hooks/useEstablishmentFeatures"
import { useOperator } from "@/lib/contexts/OperatorContext"
import { useTimeclock } from "@/lib/contexts/TimeclockContext"
import { loadEstablishmentToken } from "@/lib/session/establishment"

export default function MorningPage() {
  const router = useRouter()
  const { operator } = useOperator()
  const { status, enabled: timeclockEnabled } = useTimeclock()
  const features = useEstablishmentFeatures()
  const [coldOpen, setColdOpen] = useState(false)
  const [equipments, setEquipments] = useState([])

  const isActive = !timeclockEnabled || status === "active"
  const token = loadEstablishmentToken()
  const credentials = operator ? { pin: operator.pin, operatorId: operator.id } : null
  const { badge, markDone } = useColdChainProgress(equipments)

  useEffect(() => {
    if (!token || !credentials) return
    getEquipments(token, credentials)
      .then((data) => setEquipments(data?.items ?? data ?? []))
      .catch(() => {})
  }, [token, credentials])

  return (
    <KioskPhaseShell phaseId="morning">
      {!isActive && timeclockEnabled && (
        <Alert variant="destructive" className="mb-4 text-[1.1rem]">
          <AlertDescription>Pointez votre arrivée pour accéder aux actions.</AlertDescription>
        </Alert>
      )}

      <KioskActionGrid>
        {features.temperatureEnabled && (
          <KioskActionTile
            emoji="❄️"
            title="Mes Frigos & Congélateurs"
            subtitle="Pavé numérique — 2 clics max"
            badge={badge}
            disabled={!isActive}
            onClick={() => setColdOpen(true)}
          />
        )}

        {features.receptionsEnabled && (
          <KioskActionTile
            emoji="🚚"
            title="Arrivée des Marchandises"
            subtitle="Fournisseur, température, check-list"
            disabled={!isActive}
            onClick={() => router.push("/operator/reception")}
          />
        )}

        <KioskActionTile
          emoji="📸"
          title="Scanner un document"
          subtitle="BL ou fiche microbiologique"
          disabled={!isActive}
          onClick={() => router.push("/operator/morning/documents")}
        />
      </KioskActionGrid>

      <ColdChainQuickRecord
        open={coldOpen}
        onOpenChange={setColdOpen}
        onEquipmentDone={markDone}
      />
    </KioskPhaseShell>
  )
}
