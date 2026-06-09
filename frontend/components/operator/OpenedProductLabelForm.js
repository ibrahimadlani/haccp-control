"use client"

import { useEffect, useState } from "react"
import { CheckCircle2, Loader2, Tag } from "lucide-react"
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
import { createOpenedProductLabel, getOpenedProductLabels } from "@/lib/api/production"
import { useOperator } from "@/lib/contexts/OperatorContext"
import { loadEstablishmentToken } from "@/lib/session/establishment"
import { cn } from "@/lib/utils"

const STORAGE_OPTIONS = [
  { value: "COLD_POSITIVE", label: "Frigo positif", hint: "0 à +4 °C" },
  { value: "COLD_NEGATIVE", label: "Frigo négatif", hint: "Surgelé" },
  { value: "AMBIENT", label: "Ambiant", hint: "Réserve sèche" },
]

const DLC_OFFSETS = [
  { days: 1, label: "+1 j" },
  { days: 2, label: "+2 j" },
  { days: 3, label: "+3 j" },
  { days: 7, label: "+7 j" },
]

function addDays(days) {
  const d = new Date()
  d.setDate(d.getDate() + days)
  return d.toISOString().split("T")[0]
}

function formatDate(isoDate) {
  return new Date(isoDate).toLocaleDateString("fr-FR", {
    day: "2-digit",
    month: "short",
  })
}

const STORAGE_LABELS = Object.fromEntries(STORAGE_OPTIONS.map((o) => [o.value, o.label]))

export function OpenedProductLabelForm({ open, onOpenChange }) {
  const { operator } = useOperator()
  const token = loadEstablishmentToken()
  const credentials = operator ? { pin: operator.pin, operatorId: operator.id } : null

  const [productName, setProductName] = useState("")
  const [secondaryUseBy, setSecondaryUseBy] = useState(addDays(3))
  const [storageLocation, setStorageLocation] = useState("COLD_POSITIVE")
  const [labels, setLabels] = useState([])
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!open || !token) return
    setLoading(true)
    getOpenedProductLabels(token)
      .then(setLabels)
      .catch(() => toast.error("Impossible de charger les étiquettes."))
      .finally(() => setLoading(false))
  }, [open, token])

  useEffect(() => {
    if (!open) {
      setProductName("")
      setSecondaryUseBy(addDays(3))
      setStorageLocation("COLD_POSITIVE")
    }
  }, [open])

  async function handleSubmit(e) {
    e.preventDefault()
    if (!productName.trim() || !token || !credentials) return
    setSubmitting(true)
    try {
      const label = await createOpenedProductLabel(token, credentials, {
        product_name: productName.trim(),
        secondary_use_by: secondaryUseBy,
        storage_location: storageLocation,
      })
      setLabels((prev) =>
        [...prev, label].sort(
          (a, b) => new Date(a.secondary_use_by) - new Date(b.secondary_use_by),
        ),
      )
      toast.success(`Étiquette créée — DLC ${formatDate(label.secondary_use_by)}`)
      setProductName("")
      setSecondaryUseBy(addDays(3))
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
            <Tag className="h-5 w-5 text-primary" />
            Étiquettes DLC secondaire
          </DialogTitle>
          <DialogDescription>
            Après ouverture — date limite de consommation et lieu de stockage
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-5">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="opened-product">Produit ouvert</Label>
              <Input
                id="opened-product"
                value={productName}
                onChange={(e) => setProductName(e.target.value)}
                placeholder="ex. Sauce tomate industrielle"
                disabled={submitting}
                required
              />
            </div>

            <div className="space-y-2">
              <Label>DLC secondaire</Label>
              <div className="flex flex-wrap gap-2">
                {DLC_OFFSETS.map(({ days, label }) => (
                  <Button
                    key={days}
                    type="button"
                    size="sm"
                    variant={secondaryUseBy === addDays(days) ? "default" : "outline"}
                    onClick={() => setSecondaryUseBy(addDays(days))}
                    disabled={submitting}
                  >
                    {label}
                  </Button>
                ))}
              </div>
              <Input
                type="date"
                value={secondaryUseBy}
                min={addDays(0)}
                onChange={(e) => setSecondaryUseBy(e.target.value)}
                disabled={submitting}
                required
              />
            </div>

            <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
              {STORAGE_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  disabled={submitting}
                  onClick={() => setStorageLocation(opt.value)}
                  className={cn(
                    "rounded-xl border px-3 py-3 text-left transition-colors",
                    storageLocation === opt.value
                      ? "border-primary bg-primary/5"
                      : "hover:border-primary/40 hover:bg-muted/40",
                  )}
                >
                  <p className="text-sm font-medium">{opt.label}</p>
                  <p className="text-xs text-muted-foreground">{opt.hint}</p>
                </button>
              ))}
            </div>

            <Button
              type="submit"
              className="h-12 w-full text-base"
              disabled={submitting || !productName.trim()}
            >
              {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Créer l&apos;étiquette
            </Button>
          </form>

          <div className="space-y-2 border-t pt-4">
            <p className="text-sm font-medium">Étiquettes actives</p>
            {loading ? (
              <div className="flex justify-center py-4">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            ) : labels.length === 0 ? (
              <p className="text-sm text-muted-foreground">Aucune étiquette en cours.</p>
            ) : (
              <ul className="divide-y rounded-lg border">
                {labels.map((label) => (
                  <li key={label.id} className="flex items-center gap-3 px-3 py-3">
                    <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{label.product_name}</p>
                      <p className="text-xs text-muted-foreground">
                        DLC {formatDate(label.secondary_use_by)} ·{" "}
                        {STORAGE_LABELS[label.storage_location]}
                      </p>
                    </div>
                    <Badge variant="outline" className="shrink-0 text-xs">
                      {formatDate(label.secondary_use_by)}
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
