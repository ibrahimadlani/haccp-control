"use client"

import { Package, SprayCan, ThermometerSnowflake } from "lucide-react"
import { useRouter } from "next/navigation"
import { KioskActionGrid } from "@/components/kiosk/KioskActionGrid"
import { KioskActionTile } from "@/components/kiosk/KioskActionTile"
import { KioskPhaseShell } from "@/components/kiosk/KioskPhaseShell"
import { useColdChainProgress } from "@/lib/hooks/useColdChainProgress"
import { useEstablishmentFeatures } from "@/lib/hooks/useEstablishmentFeatures"
import { useEffect, useState } from "react"
import { getEquipments } from "@/lib/api/equipment"
import { useOperator } from "@/lib/contexts/OperatorContext"
import { cleaningHref } from "@/lib/kiosk/cleaningSchedule"
import { loadEstablishmentToken } from "@/lib/session/establishment"

export default function MorningPage() {
  const router = useRouter()
  const { operator } = useOperator()
  const features = useEstablishmentFeatures()
  const [equipments, setEquipments] = useState([])

  const token = loadEstablishmentToken()
  const credentials = operator ? { pin: operator.pin, operatorId: operator.id } : null
  const { badge } = useColdChainProgress(equipments)

  useEffect(() => {
    if (!token || !credentials) return
    getEquipments(token, credentials)
      .then((data) => setEquipments(data?.items ?? data ?? []))
      .catch(() => {})
  }, [token, credentials])

  return (
    <KioskPhaseShell phaseId="morning">
      <KioskActionGrid>
        {features.temperatureEnabled && (
          <KioskActionTile
            icon={ThermometerSnowflake}
            title="Frigos et congélateurs"
            subtitle="Relevé de température à l'ouverture"
            badge={badge}
            href="/operator/morning/cold"
          />
        )}

        {features.receptionsEnabled && (
          <KioskActionTile
            icon={Package}
            title="Nouvelle réception"
            subtitle="Fournisseur, produit, conformité livraison"
            onClick={() => router.push("/operator/reception")}
          />
        )}

        {features.cleaningEnabled && (
          <KioskActionTile
            icon={SprayCan}
            title="Nettoyage avant le repas"
            subtitle="Ouverture · préparation du service"
            href={cleaningHref("OPENING")}
          />
        )}
      </KioskActionGrid>
    </KioskPhaseShell>
  )
}
