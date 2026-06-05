/**
 * Rythme cantine scolaire — 3 moments de la journée.
 * Horaires indicatifs (restauration collective lycée/collège).
 */

export const DAY_PHASES = {
  MORNING: "morning",
  SERVICE: "service",
  CLOSING: "closing",
}

export const PHASE_META = {
  [DAY_PHASES.MORNING]: {
    id: DAY_PHASES.MORNING,
    label: "J'arrive",
    shortLabel: "Matin",
    subtitle: "Réception & chaîne du froid",
    hint: "Contrôles à l'ouverture — livraisons et enceintes froides",
    /** Début suggéré (minutes depuis minuit) */
    fromMinutes: 5 * 60 + 30, // 05:30
    untilMinutes: 10 * 60, // 10:00
  },
  [DAY_PHASES.SERVICE]: {
    id: DAY_PHASES.SERVICE,
    label: "Je cuisine",
    shortLabel: "Service",
    subtitle: "Cuisson & self",
    hint: "Production du midi — températures à cœur et maintien au chaud",
    fromMinutes: 10 * 60,
    untilMinutes: 14 * 60, // 14:00
  },
  [DAY_PHASES.CLOSING]: {
    id: DAY_PHASES.CLOSING,
    label: "Je range",
    shortLabel: "Fin",
    subtitle: "Nettoyage & clôture",
    hint: "Après le service — ménage, plats témoins, fermeture",
    fromMinutes: 13 * 60, // 13:00 (chevauche fin de service cantine)
    untilMinutes: 16 * 60,
  },
}

const PHASE_ORDER = [DAY_PHASES.MORNING, DAY_PHASES.SERVICE, DAY_PHASES.CLOSING]

/** Types d'équipement = chaîne du froid (relevés matinaux). */
export const COLD_EQUIPMENT_TYPES = new Set([
  "CHAMBRE_FROIDE_POSITIVE",
  "CHAMBRE_FROIDE_NEGATIVE",
  "REFRIGERATEUR_VIANDE",
  "REFRIGERATEUR_POISSON",
  "VITRINE_REFRIGEREE",
  "CELLULE_REFROIDISSEMENT",
  "CONGELATEUR_CONSERVATEUR",
])

export function minutesSinceMidnight(date = new Date()) {
  return date.getHours() * 60 + date.getMinutes()
}

/** Phase suggérée selon l'heure locale de la tablette. */
export function getSuggestedDayPhase(date = new Date()) {
  const now = minutesSinceMidnight(date)

  if (now < PHASE_META[DAY_PHASES.MORNING].untilMinutes) {
    return DAY_PHASES.MORNING
  }
  if (now < PHASE_META[DAY_PHASES.CLOSING].fromMinutes) {
    return DAY_PHASES.SERVICE
  }
  return DAY_PHASES.CLOSING
}

export function isPhaseSuggested(phase, date = new Date()) {
  return getSuggestedDayPhase(date) === phase
}

export function listDayPhases() {
  return PHASE_ORDER.map((id) => PHASE_META[id])
}

export function filterColdEquipments(equipments = []) {
  return equipments.filter(
    (eq) => eq.is_active !== false && COLD_EQUIPMENT_TYPES.has(eq.equipment_type),
  )
}
