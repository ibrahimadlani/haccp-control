"use client"

import { HubStatusRibbon } from "@/components/kiosk/HubStatusRibbon"
import { ManagerAccessButton } from "@/components/kiosk/ManagerPinGate"
import { KioskHubCard } from "@/components/kiosk/KioskHubCard"
import { KIOSK_PHASES } from "@/lib/kiosk/phases"
import { getSuggestedDayPhase } from "@/lib/operator/canteenDay"
import { useOperator } from "@/lib/contexts/OperatorContext"
import { useTimeclock } from "@/lib/contexts/TimeclockContext"
import { Alert, AlertDescription } from "@/components/ui/alert"

export default function OperatorHubPage() {
  const { operator } = useOperator()
  const { status, enabled: timeclockEnabled } = useTimeclock()
  const suggested = getSuggestedDayPhase()
  const firstName = operator?.name?.split(" ")[0] ?? "Opérateur"
  const isActive = !timeclockEnabled || status === "active"

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4">
      <header className="shrink-0 text-center sm:text-left">
        <h1 className="text-[1.75rem] font-extrabold text-slate-900 sm:text-[2rem]">
          Ma journée en cuisine
        </h1>
        <p className="mt-1 text-[1.2rem] text-slate-600">Bonjour {firstName}</p>
      </header>

      {!isActive && timeclockEnabled && (
        <Alert variant="destructive" className="text-[1.1rem]">
          <AlertDescription>
            Pointez votre arrivée en haut de l&apos;écran pour débloquer les actions.
          </AlertDescription>
        </Alert>
      )}

      <HubStatusRibbon />

      <div className="flex min-h-0 flex-1 flex-col gap-4">
        <KioskHubCard
          href={KIOSK_PHASES.morning.route}
          emoji={KIOSK_PHASES.morning.hubEmoji}
          title={KIOSK_PHASES.morning.hubTitle}
          accentClass={`bg-gradient-to-br ${KIOSK_PHASES.morning.headerAccent} text-white`}
          ringClass="ring-sky-500/40"
          suggested={suggested === "morning"}
        />
        <KioskHubCard
          href={KIOSK_PHASES.service.route}
          emoji={KIOSK_PHASES.service.hubEmoji}
          title={KIOSK_PHASES.service.hubTitle}
          accentClass={`bg-gradient-to-br ${KIOSK_PHASES.service.headerAccent} text-white`}
          ringClass="ring-orange-500/40"
          suggested={suggested === "service"}
        />
        <KioskHubCard
          href={KIOSK_PHASES.closing.route}
          emoji={KIOSK_PHASES.closing.hubEmoji}
          title={KIOSK_PHASES.closing.hubTitle}
          accentClass={`bg-gradient-to-br ${KIOSK_PHASES.closing.headerAccent} text-white`}
          ringClass="ring-violet-500/40"
          suggested={suggested === "closing"}
        />
      </div>

      <div className="flex shrink-0 justify-end pb-2">
        <ManagerAccessButton className="text-[1rem] text-slate-500 underline-offset-4 hover:text-slate-700 hover:underline" />
      </div>
    </div>
  )
}
