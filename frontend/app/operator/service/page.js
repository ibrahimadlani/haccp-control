"use client"

import Link from "next/link"
import {
  CalendarDays,
  Droplets,
  Printer,
  ShieldAlert,
  Thermometer,
  Timer,
} from "lucide-react"
import { KioskActionGrid } from "@/components/kiosk/KioskActionGrid"
import { KioskActionTile } from "@/components/kiosk/KioskActionTile"
import { KioskPhaseShell } from "@/components/kiosk/KioskPhaseShell"
import { useCoolingChrono } from "@/lib/hooks/useCoolingChrono"
import { useEstablishmentFeatures } from "@/lib/hooks/useEstablishmentFeatures"
import { cn } from "@/lib/utils"

export default function ServicePage() {
  const features = useEstablishmentFeatures()
  const chrono = useCoolingChrono()

  return (
    <KioskPhaseShell phaseId="service">
      {chrono.isRunning && (
        <Link
          href="/operator/service/chrono"
          className={cn(
            "flex items-center justify-between gap-3 rounded-xl border-2 px-4 py-3 transition-colors",
            chrono.isOverdue
              ? "animate-pulse border-red-500 bg-red-50 text-red-900"
              : "border-orange-400 bg-orange-50 text-orange-900",
          )}
        >
          <div className="flex items-center gap-3">
            <Timer className="h-6 w-6 shrink-0" />
            <div>
              <p className="text-[1.05rem] font-semibold uppercase tracking-wide">
                Refroidissement en cours
              </p>
              <p className="text-[1.2rem] font-bold">
                {chrono.isOverdue ? "Délai dépassé — agir maintenant" : chrono.remainingLabel}
              </p>
            </div>
          </div>
          <span className="text-[1rem] font-semibold underline">Voir →</span>
        </Link>
      )}

      <KioskActionGrid>
        <KioskActionTile
          icon={CalendarDays}
          title="Menu de la semaine"
          subtitle="Plats, allergènes, type de viande"
          href="/operator/service/menu"
        />

        {features.temperatureEnabled && (
          <KioskActionTile
            icon={Thermometer}
            title="Température des plats"
            subtitle="Cuisson à cœur · maintien au chaud"
            href="/operator/service/temperature"
          />
        )}

        <KioskActionTile
          icon={Timer}
          title="Refroidissement chrono"
          subtitle={
            chrono.isRunning
              ? chrono.isOverdue
                ? "Délai dépassé"
                : `En cours — ${chrono.remainingLabel}`
              : "Compte à rebours 2 h"
          }
          badge={chrono.isOverdue ? "ALERTE" : chrono.isRunning ? "EN COURS" : null}
          variant={chrono.isOverdue ? "danger" : chrono.isRunning ? "success" : "default"}
          href="/operator/service/chrono"
        />

        <KioskActionTile
          icon={Printer}
          title="Ouverture de produit"
          subtitle="Sélection · imprimante thermique"
          href="/operator/service/labels"
        />

        <KioskActionTile
          icon={Droplets}
          title="Huile des friteuses"
          subtitle="Témoin polaire · changement"
          href="/operator/service/oil"
        />

        <KioskActionTile
          icon={ShieldAlert}
          title="Allergènes du jour"
          subtitle="14 allergènes réglementaires"
          href="/operator/service/allergens"
        />
      </KioskActionGrid>
    </KioskPhaseShell>
  )
}
