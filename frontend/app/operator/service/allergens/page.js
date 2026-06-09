"use client"

import { useEffect, useMemo, useState } from "react"
import { Loader2 } from "lucide-react"
import { toast } from "sonner"
import { KioskBackButton } from "@/components/kiosk/KioskBackButton"
import { KIOSK_PHASES } from "@/lib/kiosk/phases"
import { getDailyMenu } from "@/lib/api/production"
import { allergenBadgeClass, EU_ALLERGENS } from "@/lib/operator/allergens"
import { loadEstablishmentToken } from "@/lib/session/establishment"
import { cn } from "@/lib/utils"

export default function AllergensPage() {
  const token = loadEstablishmentToken()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!token) return
    getDailyMenu(token)
      .then(setItems)
      .catch(() => toast.error("Impossible de charger le menu."))
      .finally(() => setLoading(false))
  }, [token])

  const grouped = useMemo(() => {
    const map = new Map()
    for (const item of items) {
      const list = map.get(item.meal_service) ?? []
      list.push(item)
      map.set(item.meal_service, list)
    }
    return [...map.entries()]
  }, [items])

  const allergensInMenu = useMemo(() => {
    const set = new Set()
    for (const item of items) {
      for (const a of item.allergens ?? []) set.add(a)
    }
    return set
  }, [items])

  return (
    <div className="flex flex-1 flex-col gap-5">
      <div className="flex items-center justify-between gap-4">
        <KioskBackButton href={KIOSK_PHASES.service.route} />
        <h1 className="text-[1.5rem] font-bold">Allergènes du jour</h1>
      </div>

      <div className="rounded-xl border-2 border-slate-200 bg-white p-4">
        <p className="mb-2 text-[0.95rem] font-semibold uppercase text-slate-500">14 allergènes UE</p>
        <div className="flex flex-wrap gap-1.5">
          {EU_ALLERGENS.map((name) => (
            <span
              key={name}
              className={cn(
                "rounded-full border px-2.5 py-1 text-[0.9rem] font-medium",
                allergenBadgeClass(name),
                !allergensInMenu.has(name) && "opacity-40",
              )}
            >
              {name}
            </span>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin" />
        </div>
      ) : items.length === 0 ? (
        <p className="text-center text-[1.1rem] text-slate-600">
          Aucun plat publié — renseignez le menu de la semaine.
        </p>
      ) : (
        grouped.map(([meal, dishes]) => (
          <section key={meal} className="space-y-2">
            <h2 className="text-[1.15rem] font-bold text-orange-800">{meal}</h2>
            <ul className="divide-y rounded-xl border-2 border-slate-200 bg-white">
              {dishes.map((dish) => (
                <li key={dish.id} className="space-y-2 px-4 py-3">
                  <p className="text-[1.15rem] font-bold">{dish.dish_name}</p>
                  {dish.allergens?.length ? (
                    <div className="flex flex-wrap gap-1.5">
                      {dish.allergens.map((allergen) => (
                        <span
                          key={allergen}
                          className={cn(
                            "rounded-full border px-2.5 py-0.5 text-[0.9rem]",
                            allergenBadgeClass(allergen),
                          )}
                        >
                          {allergen}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="text-[0.95rem] text-slate-500">Aucun allergène déclaré</p>
                  )}
                </li>
              ))}
            </ul>
          </section>
        ))
      )}
    </div>
  )
}
