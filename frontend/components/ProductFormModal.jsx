"use client"

import { useEffect, useState } from "react"
import { Loader2, Thermometer } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import { createProduct, updateProduct } from "@/lib/api/products"
import { loadEstablishmentToken } from "@/lib/session/establishment"

const EMPTY_FORM = {
  name: "",
  supplier_id: "",
  internal_reference: "",
  gtin: "",
  has_temperature_control: false,
  min_temperature: "",
  max_temperature: "",
}

function buildPayload(form) {
  const payload = {
    name: form.name.trim(),
    supplier_id: form.supplier_id,
    internal_reference: form.internal_reference.trim() || null,
    gtin: form.gtin.trim() || null,
    has_temperature_control: form.has_temperature_control,
    min_temperature: form.has_temperature_control && form.min_temperature !== "" ? parseFloat(form.min_temperature) : null,
    max_temperature: form.has_temperature_control && form.max_temperature !== "" ? parseFloat(form.max_temperature) : null,
  }
  return payload
}

function buildPatch(form, product) {
  const full = buildPayload(form)
  const patch = {}
  if (full.name !== product.name)                     patch.name = full.name
  if (full.supplier_id !== product.supplier_id)       patch.supplier_id = full.supplier_id
  if (full.internal_reference !== (product.internal_reference ?? null)) patch.internal_reference = full.internal_reference
  if (full.gtin !== (product.gtin ?? null))           patch.gtin = full.gtin
  if (full.has_temperature_control !== product.has_temperature_control) {
    patch.has_temperature_control = full.has_temperature_control
    patch.min_temperature = full.min_temperature
    patch.max_temperature = full.max_temperature
  } else if (full.has_temperature_control) {
    if (full.min_temperature !== product.min_temperature) patch.min_temperature = full.min_temperature
    if (full.max_temperature !== product.max_temperature) patch.max_temperature = full.max_temperature
  }
  return patch
}

export function ProductFormModal({ open, onOpenChange, product, suppliers, onSuccess }) {
  const isEditing = Boolean(product)
  const [form, setForm]     = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (open) {
      setForm(
        product
          ? {
              name: product.name,
              supplier_id: product.supplier_id,
              internal_reference: product.internal_reference ?? "",
              gtin: product.gtin ?? "",
              has_temperature_control: product.has_temperature_control,
              min_temperature: product.min_temperature ?? "",
              max_temperature: product.max_temperature ?? "",
            }
          : EMPTY_FORM
      )
    }
  }, [open, product])

  function set(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  function validateLocal() {
    if (!form.name.trim())    { toast.error("Le nom du produit est requis."); return false }
    if (!form.supplier_id)    { toast.error("Veuillez sélectionner un fournisseur."); return false }
    if (form.has_temperature_control) {
      const min = parseFloat(form.min_temperature)
      const max = parseFloat(form.max_temperature)
      if (isNaN(min) || isNaN(max)) { toast.error("Les températures min et max sont requises."); return false }
      if (min > max) { toast.error("La température min doit être ≤ à la température max."); return false }
    }
    return true
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!validateLocal()) return
    const token = loadEstablishmentToken()
    setSaving(true)
    try {
      if (isEditing) {
        const patch = buildPatch(form, product)
        if (Object.keys(patch).length === 0) {
          toast("Aucune modification détectée.")
          onOpenChange(false)
          return
        }
        await updateProduct(token, product.id, patch)
        toast.success("Produit mis à jour.")
      } else {
        await createProduct(token, buildPayload(form))
        toast.success("Produit créé.")
      }
      onSuccess()
    } catch (err) {
      toast.error(String(err.message))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={saving ? undefined : onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{isEditing ? "Modifier le produit" : "Nouveau produit"}</DialogTitle>
          <DialogDescription>
            {isEditing
              ? "Modifiez les informations du produit."
              : "Ajoutez un produit au catalogue de l'établissement."}
          </DialogDescription>
        </DialogHeader>

        <form id="product-form" onSubmit={handleSubmit} className="space-y-5 pt-1">

          {/* ── Identité ── */}
          <div className="space-y-1.5">
            <Label htmlFor="p-name">Nom du produit *</Label>
            <Input
              id="p-name"
              value={form.name}
              onChange={(e) => set("name", e.target.value)}
              placeholder="Steak Haché 15%"
              required
              autoFocus
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="p-supplier">Fournisseur *</Label>
            <select
              id="p-supplier"
              value={form.supplier_id}
              onChange={(e) => set("supplier_id", e.target.value)}
              required
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="">— Choisir un fournisseur —</option>
              {suppliers.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="p-ref">Référence interne</Label>
              <Input
                id="p-ref"
                value={form.internal_reference}
                onChange={(e) => set("internal_reference", e.target.value)}
                placeholder="REF-001"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="p-gtin">GTIN / EAN</Label>
              <Input
                id="p-gtin"
                value={form.gtin}
                onChange={(e) => set("gtin", e.target.value)}
                placeholder="3760123450016"
                inputMode="numeric"
                className="font-mono"
              />
            </div>
          </div>

          <Separator />

          {/* ── Contrôle de température ── */}
          <div className="space-y-3">
            <label className="flex cursor-pointer items-center gap-3">
              <input
                type="checkbox"
                checked={form.has_temperature_control}
                onChange={(e) => set("has_temperature_control", e.target.checked)}
                className="h-4 w-4 rounded border-input accent-primary"
              />
              <span className="flex items-center gap-1.5 text-sm font-medium">
                <Thermometer className="h-4 w-4 text-blue-600" />
                Nécessite un contrôle de température à la réception
              </span>
            </label>

            {form.has_temperature_control && (
              <div className="grid grid-cols-2 gap-3 rounded-md border border-blue-200 bg-blue-50/50 p-3 dark:border-blue-900 dark:bg-blue-950/20">
                <div className="space-y-1.5">
                  <Label htmlFor="p-tmin" className="text-sm">Température min (°C) *</Label>
                  <Input
                    id="p-tmin"
                    type="number"
                    step="0.1"
                    value={form.min_temperature}
                    onChange={(e) => set("min_temperature", e.target.value)}
                    placeholder="0.0"
                    required={form.has_temperature_control}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="p-tmax" className="text-sm">Température max (°C) *</Label>
                  <Input
                    id="p-tmax"
                    type="number"
                    step="0.1"
                    value={form.max_temperature}
                    onChange={(e) => set("max_temperature", e.target.value)}
                    placeholder="4.0"
                    required={form.has_temperature_control}
                  />
                </div>
              </div>
            )}
          </div>
        </form>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={saving}>
            Annuler
          </Button>
          <Button type="submit" form="product-form" disabled={saving}>
            {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {isEditing ? "Enregistrer" : "Créer le produit"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
