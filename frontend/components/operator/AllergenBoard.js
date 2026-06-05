"use client"

import { useEffect, useMemo, useState } from "react"
import { AlertCircle, Loader2, ShieldAlert } from "lucide-react"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { allergenBadgeClass, EU_ALLERGENS } from "@/lib/operator/allergens"
import { getDailyMenu } from "@/lib/api/production"
import { loadEstablishmentToken } from "@/lib/session/establishment"
import { cn } from "@/lib/utils"

export function AllergenBoard({ open, onOpenChange }) {
  const token = loadEstablishmentToken()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!open || !token) return
    setLoading(true)
    getDailyMenu(token)
      .then(setItems)
      .catch(() => toast.error("Impossible de charger le menu du jour."))
      .finally(() => setLoading(false))
  }, [open, token])

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
      for (const allergen of item.allergens ?? []) {
        set.add(allergen)
      }
    }
    return set
  }, [items])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[92vh] w-full max-w-lg flex-col gap-0 overflow-hidden p-0 sm:max-w-lg">
        <DialogHeader className="space-y-1 border-b px-5 py-4 text-left">
          <DialogTitle className="flex items-center gap-2 text-xl">
            <ShieldAlert className="h-5 w-5 text-primary" />
            Allergènes du jour
          </DialogTitle>
          <DialogDescription>
            14 allergènes réglementaires — plats servis aujourd&apos;hui
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-5">
          <div className="rounded-lg border bg-muted/20 p-3">
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Légende — 14 allergènes UE
            </p>
            <div className="flex flex-wrap gap-1.5">
              {EU_ALLERGENS.map((name) => (
                <span
                  key={name}
                  className={cn(
                    "rounded-full border px-2 py-0.5 text-xs font-medium",
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
            <div className="flex justify-center py-10">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : items.length === 0 ? (
            <div className="flex flex-col items-center gap-2 py-10 text-center text-muted-foreground">
              <AlertCircle className="h-8 w-8" />
              <p className="text-sm">Aucun plat publié pour aujourd&apos;hui.</p>
            </div>
          ) : (
            grouped.map(([meal, dishes]) => (
              <section key={meal} className="space-y-2">
                <h3 className="text-sm font-semibold text-primary">{meal}</h3>
                <ul className="divide-y rounded-lg border">
                  {dishes.map((dish) => (
                    <li key={dish.id} className="space-y-2 px-3 py-3">
                      <p className="font-medium">{dish.dish_name}</p>
                      {dish.allergens?.length ? (
                        <div className="flex flex-wrap gap-1.5">
                          {dish.allergens.map((allergen) => (
                            <Badge
                              key={allergen}
                              variant="outline"
                              className={cn("text-xs", allergenBadgeClass(allergen))}
                            >
                              {allergen}
                            </Badge>
                          ))}
                        </div>
                      ) : (
                        <p className="text-xs text-muted-foreground">
                          Aucun allergène déclaré
                        </p>
                      )}
                    </li>
                  ))}
                </ul>
              </section>
            ))
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
