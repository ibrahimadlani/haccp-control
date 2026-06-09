"use client"

import { useEffect, useState } from "react"
import { AlertTriangle, CheckCircle2, Loader2 } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { KioskBackButton } from "@/components/kiosk/KioskBackButton"
import { NumericKeypad } from "@/components/operator/NumericKeypad"
import { KIOSK_PHASES } from "@/lib/kiosk/phases"
import { createProductionTemperature, getDailyMenu } from "@/lib/api/production"
import {
  HOT_HOLDING_MIN_C,
  minTempForControl,
  proteinLabel,
} from "@/lib/operator/proteinTypes"
import { useOperator } from "@/lib/contexts/OperatorContext"
import { loadEstablishmentToken } from "@/lib/session/establishment"
import { cn } from "@/lib/utils"

const CONTROL_TYPES = [
  { value: "COOKING_CORE", label: "Cuisson à cœur" },
  { value: "HOT_HOLDING", label: "Maintien au chaud" },
]

export default function ServiceTemperaturePage() {
  const { operator } = useOperator()
  const token = loadEstablishmentToken()
  const credentials = operator ? { pin: operator.pin, operatorId: operator.id } : null

  const [menuDishes, setMenuDishes] = useState([])
  const [selectedDish, setSelectedDish] = useState(null)
  const [controlType, setControlType] = useState("COOKING_CORE")
  const [temperature, setTemperature] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [lastResult, setLastResult] = useState(null)

  useEffect(() => {
    if (!token) return
    getDailyMenu(token).then((items) => setMenuDishes(items ?? [])).catch(() => {})
  }, [token])

  const minRequired = selectedDish
    ? minTempForControl(selectedDish.protein_type, controlType)
    : controlType === "HOT_HOLDING"
      ? HOT_HOLDING_MIN_C
      : 63

  const tempValue = temperature ? parseFloat(temperature) : null
  const previewConforme = tempValue !== null && !Number.isNaN(tempValue) && tempValue >= minRequired

  async function handleSubmit() {
    if (!selectedDish || !temperature.trim() || !token || !credentials) return
    setSubmitting(true)
    try {
      const result = await createProductionTemperature(token, credentials, {
        dish_name: selectedDish.dish_name,
        control_type: controlType,
        measured_value: temperature,
        menu_item_id: selectedDish.id,
      })
      setLastResult(result)
      if (result.is_conforme) {
        toast.success(`${result.dish_name} — ${result.measured_value} °C conforme`)
      } else {
        toast.warning(`Température insuffisante (seuil ${result.min_required_c} °C)`)
      }
      setTemperature("")
    } catch (err) {
      toast.error(String(err.message))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-lg flex-1 flex-col gap-5">
      <div className="flex items-center justify-between gap-4">
        <KioskBackButton href={KIOSK_PHASES.service.route} />
        <h1 className="text-[1.5rem] font-bold">Température des plats</h1>
      </div>

      {lastResult && (
        <div
          className={cn(
            "flex items-start gap-3 rounded-xl border-2 p-4",
            lastResult.is_conforme ? "border-emerald-400 bg-emerald-50" : "border-red-400 bg-red-50",
          )}
        >
          {lastResult.is_conforme ? (
            <CheckCircle2 className="h-6 w-6 text-emerald-600" />
          ) : (
            <AlertTriangle className="h-6 w-6 text-red-600" />
          )}
          <div>
            <p className="font-bold">{lastResult.dish_name}</p>
            <p className="text-[1.05rem] text-slate-700">
              {lastResult.measured_value} °C — seuil {lastResult.min_required_c} °C
            </p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-2">
        {CONTROL_TYPES.map((type) => (
          <button
            key={type.value}
            type="button"
            onClick={() => setControlType(type.value)}
            className={cn(
              "min-h-[3.5rem] rounded-xl border-2 px-3 py-2 text-[1.05rem] font-semibold",
              controlType === type.value
                ? "border-orange-500 bg-orange-50"
                : "border-slate-200 bg-white",
            )}
          >
            {type.label}
          </button>
        ))}
      </div>

      <div className="space-y-2">
        <p className="text-[1.1rem] font-bold">Plat du menu</p>
        {menuDishes.length === 0 ? (
          <p className="text-[1rem] text-slate-600">
            Aucun plat aujourd&apos;hui — ajoutez le menu dans « Menu de la semaine ».
          </p>
        ) : (
          <div className="grid gap-2 sm:grid-cols-2">
            {menuDishes.map((dish) => (
              <button
                key={dish.id}
                type="button"
                onClick={() => setSelectedDish(dish)}
                className={cn(
                  "rounded-xl border-2 px-3 py-3 text-left",
                  selectedDish?.id === dish.id
                    ? "border-orange-500 bg-orange-50"
                    : "border-slate-200 bg-white",
                )}
              >
                <p className="font-bold">{dish.dish_name}</p>
                <p className="text-[0.9rem] text-slate-600">
                  {proteinLabel(dish.protein_type)} · ≥ {dish.min_core_temp_c ?? 63} °C
                </p>
              </button>
            ))}
          </div>
        )}
      </div>

      {selectedDish && (
        <>
          <div className="rounded-xl border bg-slate-50 p-4 text-center">
            <p className="text-[1rem] text-slate-600">Seuil requis</p>
            <p className="text-3xl font-bold tabular-nums">{minRequired} °C</p>
            <p className="mt-1 text-[0.95rem] text-slate-500">
              {controlType === "HOT_HOLDING"
                ? "Maintien au chaud"
                : proteinLabel(selectedDish.protein_type)}
            </p>
          </div>

          <div className="rounded-xl border bg-white p-4 text-center">
            <p className="text-[1rem] text-slate-600">Température mesurée</p>
            <p
              className={cn(
                "text-4xl font-bold tabular-nums",
                tempValue !== null && !previewConforme && "text-red-600",
              )}
            >
              {temperature || "—"}
              <span className="text-2xl text-slate-500"> °C</span>
            </p>
          </div>

          <NumericKeypad value={temperature} onChange={setTemperature} disabled={submitting} />

          <Button
            className="h-14 w-full text-[1.15rem] font-semibold"
            variant={tempValue !== null && !previewConforme ? "destructive" : "default"}
            onClick={handleSubmit}
            disabled={submitting || !temperature.trim()}
          >
            {submitting && <Loader2 className="mr-2 h-5 w-5 animate-spin" />}
            Enregistrer le relevé
          </Button>
        </>
      )}
    </div>
  )
}
