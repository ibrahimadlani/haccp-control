/** Types de protéine — seuils cuisson à cœur (maintien au chaud : 63 °C pour tous). */

export const PROTEIN_TYPES = [
  {
    value: "POULTRY",
    label: "Volaille",
    coreTemp: 75,
    hint: "Cuisson à cœur ≥ 75 °C",
  },
  {
    value: "MINCED_MEAT",
    label: "Viande hachée",
    coreTemp: 75,
    hint: "Cuisson à cœur ≥ 75 °C",
  },
  {
    value: "WHOLE_MEAT",
    label: "Viande entière",
    coreTemp: 63,
    hint: "Cuisson à cœur ≥ 63 °C",
  },
  {
    value: "FISH",
    label: "Poisson",
    coreTemp: 63,
    hint: "Cuisson à cœur ≥ 63 °C",
  },
  {
    value: "VEGETARIAN",
    label: "Végétarien",
    coreTemp: 63,
    hint: "Cuisson à cœur ≥ 63 °C",
  },
  {
    value: "OTHER",
    label: "Autre",
    coreTemp: 63,
    hint: "Cuisson à cœur ≥ 63 °C",
  },
]

export const HOT_HOLDING_MIN_C = 63

export function proteinLabel(value) {
  return PROTEIN_TYPES.find((p) => p.value === value)?.label ?? value
}

export function minCoreTempForProtein(proteinType) {
  return PROTEIN_TYPES.find((p) => p.value === proteinType)?.coreTemp ?? 63
}

export function minTempForControl(proteinType, controlType) {
  if (controlType === "HOT_HOLDING") return HOT_HOLDING_MIN_C
  return minCoreTempForProtein(proteinType)
}
