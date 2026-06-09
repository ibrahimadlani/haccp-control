/** 14 allergènes réglementaires UE — libellés affichés sur la tablette. */
export const EU_ALLERGENS = [
  "Gluten",
  "Crustacés",
  "Œufs",
  "Poisson",
  "Arachides",
  "Soja",
  "Lait",
  "Fruits à coque",
  "Céleri",
  "Moutarde",
  "Sésame",
  "Sulfites",
  "Lupin",
  "Mollusques",
]

const ALLERGEN_COLORS = {
  Gluten: "bg-amber-100 text-amber-900 border-amber-200",
  Crustacés: "bg-orange-100 text-orange-900 border-orange-200",
  Œufs: "bg-yellow-100 text-yellow-900 border-yellow-200",
  Poisson: "bg-sky-100 text-sky-900 border-sky-200",
  Arachides: "bg-rose-100 text-rose-900 border-rose-200",
  Soja: "bg-lime-100 text-lime-900 border-lime-200",
  Lait: "bg-blue-100 text-blue-900 border-blue-200",
  "Fruits à coque": "bg-orange-100 text-orange-950 border-orange-300",
  Céleri: "bg-green-100 text-green-900 border-green-200",
  Moutarde: "bg-yellow-100 text-yellow-950 border-yellow-300",
  Sésame: "bg-stone-100 text-stone-900 border-stone-200",
  Sulfites: "bg-purple-100 text-purple-900 border-purple-200",
  Lupin: "bg-violet-100 text-violet-900 border-violet-200",
  Mollusques: "bg-cyan-100 text-cyan-900 border-cyan-200",
}

export function allergenBadgeClass(name) {
  return ALLERGEN_COLORS[name] ?? "bg-muted text-muted-foreground border-border"
}
