/** Affichage UI uniquement — les seuils HACCP sont appliqués côté API. */
export const FOOD_TYPES = [
  { value: "VOLAILLE", label: "Volaille", targetC: 74 },
  { value: "VIANDE_HACHEE", label: "Viande hachée", targetC: 65 },
  { value: "VIANDE_PIECE", label: "Viande en pièce", targetC: 55 },
  { value: "LEGUMES_FECULENTS", label: "Légumes / féculents", targetC: 63 },
  { value: "POISSON", label: "Poisson", targetC: 65 },
  { value: "AUTRE", label: "Autre", targetC: 63 },
]

export function foodTypeLabel(value) {
  return FOOD_TYPES.find((t) => t.value === value)?.label ?? value ?? "—"
}

export function foodTypeTarget(value) {
  return FOOD_TYPES.find((t) => t.value === value)?.targetC ?? 63
}

export const STEP_LABELS = {
  CUISSON_A_COEUR: "Cuisson à cœur",
  REFROIDISSEMENT_DEBUT: "Refroidissement — début",
  REFROIDISSEMENT_FIN: "Refroidissement — fin",
}
