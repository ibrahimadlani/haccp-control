/** Configuration visuelle et routes du kiosque opérateur cantine. */

export const KIOSK_PHASES = {
  morning: {
    id: "morning",
    route: "/operator/morning",
    hubTitle: "1. J'arrive et je reçois",
    hubEmoji: "☀️",
    pageTitle: "J'arrive et je reçois",
    borderClass: "border-l-[6px] border-l-sky-500",
    headerAccent: "from-sky-600 to-blue-700",
    tileRing: "ring-sky-500/30",
  },
  service: {
    id: "service",
    route: "/operator/service",
    hubTitle: "2. Je cuisine et je sers",
    hubEmoji: "🔥",
    pageTitle: "Je cuisine et je sers",
    borderClass: "border-l-[6px] border-l-orange-500",
    headerAccent: "from-orange-500 to-amber-600",
    tileRing: "ring-orange-500/30",
  },
  closing: {
    id: "closing",
    route: "/operator/closing",
    hubTitle: "3. Fin de service et rangement",
    hubEmoji: "🌙",
    pageTitle: "Fin de service et rangement",
    borderClass: "border-l-[6px] border-l-violet-500",
    headerAccent: "from-violet-600 to-purple-700",
    tileRing: "ring-violet-500/30",
  },
}

export const HUB_ROUTE = "/operator"
export const MANAGER_ROUTE = "/operator/manager"

export function getPhaseConfig(phaseId) {
  return KIOSK_PHASES[phaseId] ?? KIOSK_PHASES.morning
}
