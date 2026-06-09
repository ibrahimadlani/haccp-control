/** Libellés créneaux nettoyage — cantine collective. */

import { KIOSK_PHASES } from "@/lib/kiosk/phases"

export const CLEANING_SCHEDULES = [
  {
    value: "OPENING",
    label: "Avant le repas",
    hint: "Ouverture · préparation du service",
  },
  {
    value: "CLOSING",
    label: "Après le repas",
    hint: "Fermeture · fin de service",
  },
  {
    value: "WEEKLY",
    label: "Hebdomadaire",
    hint: "Nettoyage en profondeur",
  },
  {
    value: "MONTHLY",
    label: "Mensuel",
    hint: "Entretien périodique",
  },
]

const VALID_VALUES = new Set(CLEANING_SCHEDULES.map((s) => s.value))

export function scheduleLabel(value) {
  return CLEANING_SCHEDULES.find((s) => s.value === value)?.label ?? value
}

export function parseScheduleParam(value) {
  if (value && VALID_VALUES.has(value)) return value
  return "OPENING"
}

/** Route de retour selon le créneau (matin = avant repas, fermeture = après). */
export function backRouteForSchedule(schedule) {
  if (schedule === "OPENING") return KIOSK_PHASES.morning.route
  return KIOSK_PHASES.closing.route
}

export function cleaningHref(schedule) {
  return `/operator/cleaning?schedule=${schedule}`
}
