"use client"

import { useEffect, useState } from "react"
import { AlertTriangle, CheckCircle2, Loader2, Thermometer } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { NumericKeypad } from "@/components/operator/NumericKeypad"
import { createProductionTemperature, getDailyMenu } from "@/lib/api/production"
import { useOperator } from "@/lib/contexts/OperatorContext"
import { loadEstablishmentToken } from "@/lib/session/establishment"
import { cn } from "@/lib/utils"

const CONTROL_TYPES = [
  { value: "COOKING_CORE", label: "Cuisson à cœur", hint: "≥ 63°C" },
  { value: "HOT_HOLDING", label: "Maintien au chaud", hint: "≥ 63°C" },
]

export function CookingQuickRecord({ open, onOpenChange }) {
  const { operator } = useOperator()
  const token = loadEstablishmentToken()
  const credentials = operator ? { pin: operator.pin, operatorId: operator.id } : null

  const [dishName, setDishName] = useState("")
  const [controlType, setControlType] = useState("COOKING_CORE")
  const [temperature, setTemperature] = useState("")
  const [menuDishes, setMenuDishes] = useState([])
  const [submitting, setSubmitting] = useState(false)
  const [lastResult, setLastResult] = useState(null)

  useEffect(() => {
    if (!open || !token) return
    getDailyMenu(token)
      .then((items) => setMenuDishes(items ?? []))
      .catch(() => setMenuDishes([]))
  }, [open, token])

  useEffect(() => {
    if (!open) {
      setDishName("")
      setControlType("COOKING_CORE")
      setTemperature("")
      setLastResult(null)
    }
  }, [open])

  async function handleSubmit() {
    if (!dishName.trim() || !temperature.trim() || !token || !credentials) return
    setSubmitting(true)
    try {
      const result = await createProductionTemperature(token, credentials, {
        dish_name: dishName.trim(),
        control_type: controlType,
        measured_value: temperature,
      })
      setLastResult(result)
      if (result.is_conforme) {
        toast.success(`${result.dish_name} — ${result.measured_value}°C conforme`)
      } else {
        toast.warning(`${result.dish_name} — température insuffisante`)
      }
      setDishName("")
      setTemperature("")
    } catch (err) {
      toast.error(String(err.message))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={submitting ? undefined : onOpenChange}>
      <DialogContent className="flex max-h-[92vh] w-full max-w-lg flex-col gap-0 overflow-hidden p-0 sm:max-w-lg">
        <DialogHeader className="space-y-1 border-b px-5 py-4 text-left">
          <DialogTitle className="flex items-center gap-2 text-xl">
            <Thermometer className="h-5 w-5 text-primary" />
            Température des plats
          </DialogTitle>
          <DialogDescription>
            Relevé à cœur ou maintien au chaud — seuil réglementaire 63°C
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-5">
          {lastResult && (
            <div
              className={cn(
                "flex items-start gap-3 rounded-lg border p-4",
                lastResult.is_conforme
                  ? "border-green-200 bg-green-50 dark:border-green-900 dark:bg-green-950/30"
                  : "border-destructive/30 bg-destructive/5",
              )}
            >
              {lastResult.is_conforme ? (
                <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-green-600" />
              ) : (
                <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-destructive" />
              )}
              <div>
                <p className="font-medium">{lastResult.dish_name}</p>
                <p className="text-sm text-muted-foreground">
                  {lastResult.measured_value}°C —{" "}
                  {lastResult.is_conforme ? "conforme" : "sous le seuil de 63°C"}
                </p>
              </div>
            </div>
          )}

          {menuDishes.length > 0 && (
            <div className="space-y-2">
              <Label className="text-[1.1rem]">Plats du jour</Label>
              <div className="grid max-h-36 grid-cols-1 gap-2 overflow-y-auto sm:grid-cols-2">
                {menuDishes.map((dish) => (
                  <button
                    key={dish.id}
                    type="button"
                    disabled={submitting}
                    onClick={() => setDishName(dish.dish_name)}
                    className={cn(
                      "rounded-xl border-2 px-3 py-2 text-left text-[1.05rem] font-semibold",
                      dishName === dish.dish_name
                        ? "border-orange-500 bg-orange-50"
                        : "border-slate-200 hover:border-orange-300",
                    )}
                  >
                    {dish.dish_name}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="space-y-1.5">
            <Label htmlFor="dish-name" className="text-[1.1rem]">Plat préparé</Label>
            <Input
              id="dish-name"
              value={dishName}
              onChange={(e) => setDishName(e.target.value)}
              placeholder="ex. Blanquette de veau"
              disabled={submitting}
              className="h-12 text-[1.1rem]"
            />
          </div>

          <div className="grid grid-cols-2 gap-2">
            {CONTROL_TYPES.map((type) => (
              <button
                key={type.value}
                type="button"
                disabled={submitting}
                onClick={() => setControlType(type.value)}
                className={cn(
                  "rounded-xl border px-3 py-3 text-left transition-colors",
                  controlType === type.value
                    ? "border-primary bg-primary/5"
                    : "hover:border-primary/40 hover:bg-muted/40",
                )}
              >
                <p className="text-sm font-medium">{type.label}</p>
                <p className="text-xs text-muted-foreground">{type.hint}</p>
              </button>
            ))}
          </div>

          <div className="rounded-xl border bg-muted/30 p-4 text-center">
            <p className="text-sm text-muted-foreground">Température mesurée</p>
            <p className="mt-2 text-4xl font-bold tabular-nums tracking-tight">
              {temperature || "—"}
              <span className="text-2xl text-muted-foreground">°C</span>
            </p>
          </div>

          <NumericKeypad
            value={temperature}
            onChange={setTemperature}
            disabled={submitting}
            allowNegative={false}
          />

          <Button
            className="h-12 w-full text-base"
            onClick={handleSubmit}
            disabled={submitting || !dishName.trim() || !temperature.trim()}
          >
            {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Enregistrer le relevé
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
