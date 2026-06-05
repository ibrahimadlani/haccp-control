"use client"

import { useEffect, useState } from "react"
import { CheckCircle2, Loader2, UtensilsCrossed } from "lucide-react"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
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
import { createWitnessSample, getWitnessSamples } from "@/lib/api/production"
import { useOperator } from "@/lib/contexts/OperatorContext"
import { loadEstablishmentToken } from "@/lib/session/establishment"

const MEAL_SERVICES = ["Déjeuner", "Dîner", "Goûter", "Petit-déjeuner"]

export function WitnessSampleForm({ open, onOpenChange }) {
  const { operator } = useOperator()
  const token = loadEstablishmentToken()
  const credentials = operator ? { pin: operator.pin, operatorId: operator.id } : null

  const [dishName, setDishName] = useState("")
  const [mealService, setMealService] = useState("Déjeuner")
  const [samples, setSamples] = useState([])
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!open || !token) return
    setLoading(true)
    getWitnessSamples(token)
      .then(setSamples)
      .catch(() => toast.error("Impossible de charger les plats témoins."))
      .finally(() => setLoading(false))
  }, [open, token])

  useEffect(() => {
    if (!open) {
      setDishName("")
      setMealService("Déjeuner")
    }
  }, [open])

  async function handleSubmit(e) {
    e.preventDefault()
    if (!dishName.trim() || !token || !credentials) return
    setSubmitting(true)
    try {
      const sample = await createWitnessSample(token, credentials, {
        dish_name: dishName.trim(),
        meal_service: mealService,
      })
      setSamples((prev) => [sample, ...prev])
      toast.success(`Plat témoin enregistré — à jeter le ${formatDate(sample.discard_on)}`)
      setDishName("")
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
            <UtensilsCrossed className="h-5 w-5 text-primary" />
            Plats témoins
          </DialogTitle>
          <DialogDescription>
            Échantillons conservés 5 jours au frais — obligation restauration collective
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-5">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="witness-dish">Plat du service</Label>
              <Input
                id="witness-dish"
                value={dishName}
                onChange={(e) => setDishName(e.target.value)}
                placeholder="ex. Gratin dauphinois"
                disabled={submitting}
                required
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="witness-meal">Service</Label>
              <select
                id="witness-meal"
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                value={mealService}
                onChange={(e) => setMealService(e.target.value)}
                disabled={submitting}
              >
                {MEAL_SERVICES.map((service) => (
                  <option key={service} value={service}>
                    {service}
                  </option>
                ))}
              </select>
            </div>

            <Button
              type="submit"
              className="h-12 w-full text-base"
              disabled={submitting || !dishName.trim()}
            >
              {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Enregistrer le plat témoin
            </Button>
          </form>

          <div className="space-y-2 border-t pt-4">
            <p className="text-sm font-medium">Conservés actuellement</p>
            {loading ? (
              <div className="flex justify-center py-6">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : samples.length === 0 ? (
              <p className="text-sm text-muted-foreground">Aucun plat témoin en cours.</p>
            ) : (
              <ul className="divide-y rounded-lg border">
                {samples.map((sample) => (
                  <li key={sample.id} className="flex items-center gap-3 px-3 py-3">
                    <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{sample.dish_name}</p>
                      <p className="text-xs text-muted-foreground">
                        {sample.meal_service} · à jeter le {formatDate(sample.discard_on)}
                      </p>
                    </div>
                    <Badge variant="outline" className="shrink-0 text-xs">
                      J+5
                    </Badge>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

function formatDate(isoDate) {
  return new Date(isoDate).toLocaleDateString("fr-FR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  })
}
