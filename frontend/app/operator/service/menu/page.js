"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { Loader2, Plus, Trash2 } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { KioskBackButton } from "@/components/kiosk/KioskBackButton"
import { KIOSK_PHASES } from "@/lib/kiosk/phases"
import { formatDayLabel, getWeekDates, isToday } from "@/lib/kiosk/weekDates"
import {
  createDailyMenuItem,
  deleteDailyMenuItem,
  getDailyMenu,
} from "@/lib/api/production"
import { EU_ALLERGENS } from "@/lib/operator/allergens"
import { PROTEIN_TYPES } from "@/lib/operator/proteinTypes"
import { loadEstablishmentToken } from "@/lib/session/establishment"
import { cn } from "@/lib/utils"

const MEALS = ["Déjeuner", "Goûter", "Dîner"]

export default function WeeklyMenuPage() {
  const token = loadEstablishmentToken()
  const weekDates = useMemo(() => getWeekDates(), [])
  const [selectedDate, setSelectedDate] = useState(
    () => weekDates.find(isToday) ?? weekDates[0],
  )
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const [dishName, setDishName] = useState("")
  const [mealService, setMealService] = useState("Déjeuner")
  const [proteinType, setProteinType] = useState("WHOLE_MEAT")
  const [allergens, setAllergens] = useState([])

  const loadWeek = useCallback(async () => {
    if (!token) return
    setLoading(true)
    try {
      const data = await getDailyMenu(token, {
        from: weekDates[0],
        to: weekDates[6],
      })
      setItems(data ?? [])
    } catch {
      toast.error("Impossible de charger le menu.")
    } finally {
      setLoading(false)
    }
  }, [token, weekDates])

  useEffect(() => {
    loadWeek()
  }, [loadWeek])

  const dayItems = items.filter((i) => i.service_date === selectedDate)

  function toggleAllergen(name) {
    setAllergens((prev) =>
      prev.includes(name) ? prev.filter((a) => a !== name) : [...prev, name],
    )
  }

  async function handleAddDish() {
    if (!token || !dishName.trim()) return
    setSaving(true)
    try {
      const created = await createDailyMenuItem(token, {
        service_date: selectedDate,
        meal_service: mealService,
        dish_name: dishName.trim(),
        protein_type: proteinType,
        allergens,
      })
      setItems((prev) => [...prev, created])
      setDishName("")
      setAllergens([])
      toast.success("Plat ajouté au menu")
    } catch (err) {
      toast.error(String(err.message))
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(id) {
    if (!token) return
    try {
      await deleteDailyMenuItem(token, id)
      setItems((prev) => prev.filter((i) => i.id !== id))
      toast.success("Plat retiré")
    } catch (err) {
      toast.error(String(err.message))
    }
  }

  return (
    <div className="flex flex-1 flex-col gap-5">
      <div className="flex items-center justify-between gap-4">
        <KioskBackButton href={KIOSK_PHASES.service.route} />
        <div className="text-right">
          <p className="text-[0.95rem] font-semibold uppercase tracking-wide text-orange-700">
            Planification
          </p>
          <h1 className="text-[1.5rem] font-bold text-slate-900">Menu de la semaine</h1>
        </div>
      </div>

      <div className="flex gap-2 overflow-x-auto pb-1">
        {weekDates.map((iso) => (
          <button
            key={iso}
            type="button"
            onClick={() => setSelectedDate(iso)}
            className={cn(
              "shrink-0 rounded-lg border-2 px-3 py-2 text-left text-[0.95rem] font-semibold",
              selectedDate === iso
                ? "border-orange-500 bg-orange-50 text-orange-900"
                : "border-slate-200 bg-white text-slate-700",
              isToday(iso) && "ring-2 ring-orange-200",
            )}
          >
            {formatDayLabel(iso)}
          </button>
        ))}
      </div>

      <div className="rounded-xl border-2 border-slate-200 bg-white p-4">
        <h2 className="mb-3 text-[1.15rem] font-bold">Ajouter un plat — {formatDayLabel(selectedDate)}</h2>
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <Label className="text-[1rem]">Nom du plat *</Label>
              <Input
                className="h-11 text-[1.05rem]"
                value={dishName}
                onChange={(e) => setDishName(e.target.value)}
                placeholder="ex. Blanquette de veau"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-[1rem]">Service</Label>
              <select
                className="flex h-11 w-full rounded-lg border px-3 text-[1.05rem]"
                value={mealService}
                onChange={(e) => setMealService(e.target.value)}
              >
                {MEALS.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="space-y-1">
            <Label className="text-[1rem]">Type de protéine (seuil cuisson)</Label>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {PROTEIN_TYPES.map((p) => (
                <button
                  key={p.value}
                  type="button"
                  onClick={() => setProteinType(p.value)}
                  className={cn(
                    "rounded-lg border-2 px-3 py-2 text-left text-[0.95rem]",
                    proteinType === p.value
                      ? "border-orange-500 bg-orange-50"
                      : "border-slate-200",
                  )}
                >
                  <span className="font-semibold">{p.label}</span>
                  <span className="block text-[0.85rem] text-slate-500">{p.hint}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-1">
            <Label className="text-[1rem]">Allergènes</Label>
            <div className="flex flex-wrap gap-1.5">
              {EU_ALLERGENS.map((name) => (
                <button
                  key={name}
                  type="button"
                  onClick={() => toggleAllergen(name)}
                  className={cn(
                    "rounded-full border px-2.5 py-1 text-[0.9rem] font-medium",
                    allergens.includes(name)
                      ? "border-orange-500 bg-orange-100 text-orange-900"
                      : "border-slate-200 bg-slate-50 text-slate-600",
                  )}
                >
                  {name}
                </button>
              ))}
            </div>
          </div>

          <Button
            className="h-12 w-full text-[1.1rem]"
            onClick={handleAddDish}
            disabled={saving || !dishName.trim()}
          >
            {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}
            Ajouter au menu
          </Button>
        </div>
      </div>

      <section className="space-y-2">
        <h2 className="text-[1.15rem] font-bold">
          Plats prévus ({dayItems.length})
        </h2>
        {loading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
        ) : dayItems.length === 0 ? (
          <p className="text-[1.05rem] text-slate-600">Aucun plat pour ce jour.</p>
        ) : (
          <ul className="space-y-2">
            {dayItems.map((item) => (
              <li
                key={item.id}
                className="flex items-start justify-between gap-3 rounded-xl border-2 border-slate-200 bg-white p-3"
              >
                <div>
                  <p className="text-[1.1rem] font-bold">{item.dish_name}</p>
                  <p className="text-[0.95rem] text-slate-600">
                    {item.meal_service} · {PROTEIN_TYPES.find((p) => p.value === item.protein_type)?.label}
                    {" · "}≥ {item.min_core_temp_c ?? 63} °C
                  </p>
                  {item.allergens?.length > 0 && (
                    <p className="mt-1 text-[0.9rem] text-slate-500">
                      {item.allergens.join(", ")}
                    </p>
                  )}
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={() => handleDelete(item.id)}
                  aria-label="Supprimer"
                >
                  <Trash2 className="h-5 w-5 text-red-600" />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
