"use client"

import { HubStatusRibbon } from "@/components/kiosk/HubStatusRibbon"
import { KioskHubCard } from "@/components/kiosk/KioskHubCard"
import { KIOSK_PHASES } from "@/lib/kiosk/phases"
import { useOperator } from "@/lib/contexts/OperatorContext"
import { useTimeclock } from "@/lib/contexts/TimeclockContext"
import { Alert, AlertDescription } from "@/components/ui/alert"

export default function OperatorHubPage() {
  const { operator } = useOperator()
  const { status, enabled: timeclockEnabled } = useTimeclock()
  const firstName = operator?.name?.split(" ")[0] ?? "Opérateur"
  const isActive = !timeclockEnabled || status === "active"

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4">
      <header className="shrink-0">
        <h1 className="text-[1.65rem] font-bold text-slate-900 sm:text-[1.85rem]">
          Tableau de bord cuisine
        </h1>
        <p className="mt-1 text-[1.1rem] text-slate-600">Bonjour {firstName}</p>
      </header>

      {!isActive && timeclockEnabled && (
        <Alert variant="destructive" className="text-[1.05rem]">
          <AlertDescription>
            Pointez votre arrivée en haut de l&apos;écran pour débloquer les actions.
          </AlertDescription>
        </Alert>
      )}

      <HubStatusRibbon />

      <div className="flex min-h-0 flex-1 flex-col gap-3">
        <KioskHubCard
          href={KIOSK_PHASES.morning.route}
          stepLabel={KIOSK_PHASES.morning.stepLabel}
          title={KIOSK_PHASES.morning.hubTitle}
          subtitle={KIOSK_PHASES.morning.hubSubtitle}
          accentColor={KIOSK_PHASES.morning.accentColor}
          ringClass={KIOSK_PHASES.morning.tileRing}
        />
        <KioskHubCard
          href={KIOSK_PHASES.service.route}
          stepLabel={KIOSK_PHASES.service.stepLabel}
          title={KIOSK_PHASES.service.hubTitle}
          subtitle={KIOSK_PHASES.service.hubSubtitle}
          accentColor={KIOSK_PHASES.service.accentColor}
          ringClass={KIOSK_PHASES.service.tileRing}
        />
        <KioskHubCard
          href={KIOSK_PHASES.closing.route}
          stepLabel={KIOSK_PHASES.closing.stepLabel}
          title={KIOSK_PHASES.closing.hubTitle}
          subtitle={KIOSK_PHASES.closing.hubSubtitle}
          accentColor={KIOSK_PHASES.closing.accentColor}
          ringClass={KIOSK_PHASES.closing.tileRing}
        />
      </div>
    </div>
  )
}
