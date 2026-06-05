"use client"

import { useRouter } from "next/navigation"
import { KioskActionGrid } from "@/components/kiosk/KioskActionGrid"
import { KioskActionTile } from "@/components/kiosk/KioskActionTile"
import { KioskBackButton } from "@/components/kiosk/KioskBackButton"
import { HUB_ROUTE } from "@/lib/kiosk/phases"

export default function ManagerHubPage() {
  const router = useRouter()

  return (
    <div className="flex flex-1 flex-col gap-5">
      <div className="flex items-center justify-between gap-4">
        <KioskBackButton href={HUB_ROUTE} />
        <div className="text-right">
          <p className="text-[1.2rem] text-slate-500">⚙️ Bureau du chef</p>
          <h1 className="text-[1.6rem] font-extrabold text-slate-900">Espace Manager</h1>
        </div>
      </div>

      <KioskActionGrid>
        <KioskActionTile
          emoji="🚨"
          title="Non-Conformités"
          subtitle="Déclarer, traiter, clôturer"
          onClick={() => router.push("/operator/manager/nonconformities")}
        />
        <KioskActionTile
          emoji="⚠️"
          title="Plan de Rappel Sanitaire"
          subtitle="Recherche par n° de lot"
          onClick={() => router.push("/operator/manager/recall")}
        />
        <KioskActionTile
          emoji="📁"
          title="Coffre-fort Documentaire"
          subtitle="DDPP, dératisation, analyses"
          onClick={() => router.push("/operator/manager/documents")}
        />
        <KioskActionTile
          emoji="🖨️"
          title="Export DDPP"
          subtitle="Registre HACCP officiel PDF"
          onClick={() => router.push("/operator/manager/export")}
        />
      </KioskActionGrid>
    </div>
  )
}
