"use client"

import { KioskBackButton } from "@/components/kiosk/KioskBackButton"
import { getPhaseConfig } from "@/lib/kiosk/phases"

export function OperatorBackLink({ phase = "morning" }) {
  const config = getPhaseConfig(phase)
  return <KioskBackButton href={config.route} label="RETOUR" />
}
