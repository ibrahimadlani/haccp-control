/** Configuration visuelle et routes du kiosque opérateur cantine. */

export const KIOSK_PHASES = {
  morning: {
    id: "morning",
    route: "/operator/morning",
    hubTitle: "Réception du matin",
    hubSubtitle: "Froid, réception, nettoyage avant le repas",
    stepLabel: "Étape 1",
    pageTitle: "Réception du matin",
    borderClass: "border-l-[6px] border-l-sky-500",
    headerAccent: "from-sky-600 to-blue-700",
    tileRing: "ring-sky-500/30",
    accentColor: "text-sky-700",
  },
  service: {
    id: "service",
    route: "/operator/service",
    hubTitle: "Production et service",
    hubSubtitle: "Cuisson, service, traçabilité",
    stepLabel: "Étape 2",
    pageTitle: "Production et service",
    borderClass: "border-l-[6px] border-l-orange-500",
    headerAccent: "from-orange-500 to-amber-600",
    tileRing: "ring-orange-500/30",
    accentColor: "text-orange-700",
  },
  closing: {
    id: "closing",
    route: "/operator/closing",
    hubTitle: "Fermeture et hygiène",
    hubSubtitle: "Nettoyage après le repas, clôture",
    stepLabel: "Étape 3",
    pageTitle: "Fermeture et hygiène",
    borderClass: "border-l-[6px] border-l-violet-500",
    headerAccent: "from-violet-600 to-purple-700",
    tileRing: "ring-violet-500/30",
    accentColor: "text-violet-700",
  },
}

export const HUB_ROUTE = "/operator"
export const MANAGER_ROUTE = "/operator/manager"

export function getPhaseConfig(phaseId) {
  return KIOSK_PHASES[phaseId] ?? KIOSK_PHASES.morning
}
