"use client"

import { useEffect, useState } from "react"
import { Eye, EyeOff, KeyRound, Loader2 } from "lucide-react"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { createOperator, updateOperator } from "@/lib/api/operators"
import { loadEstablishmentToken } from "@/lib/session/establishment"

const ROLES = [
  { value: "MANAGER",  label: "Manager" },
  { value: "CHEF",     label: "Chef de cuisine" },
  { value: "COMMIS",   label: "Commis" },
  { value: "PLONGEUR", label: "Plongeur" },
]

const EMPTY_FORM = {
  first_name: "",
  last_name: "",
  role: "COMMIS",
  pin_code: "",
  hygiene_training_date: "",
  medical_check_date: "",
}

function buildPatch(form, operator) {
  const patch = {}
  if (form.first_name !== operator.first_name)         patch.first_name = form.first_name
  if (form.last_name !== operator.last_name)           patch.last_name  = form.last_name
  if (form.role !== operator.role)                     patch.role       = form.role
  if (form.hygiene_training_date !== (operator.hygiene_training_date ?? ""))
    patch.hygiene_training_date = form.hygiene_training_date || null
  if (form.medical_check_date !== (operator.medical_check_date ?? ""))
    patch.medical_check_date = form.medical_check_date || null
  if (form.pin_code.trim() !== "")
    patch.pin_code = form.pin_code
  return patch
}

export function OperatorModal({ open, onClose, operator, onSaved }) {
  const isEdit = Boolean(operator)
  const [form, setForm] = useState(EMPTY_FORM)
  const [showPin, setShowPin] = useState(false)
  const [saving, setSaving] = useState(false)

  // Populate form when editing
  useEffect(() => {
    if (open) {
      setForm(
        operator
          ? {
              first_name: operator.first_name,
              last_name: operator.last_name,
              role: operator.role,
              pin_code: "",
              hygiene_training_date: operator.hygiene_training_date ?? "",
              medical_check_date: operator.medical_check_date ?? "",
            }
          : EMPTY_FORM
      )
      setShowPin(false)
    }
  }, [open, operator])

  function set(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  function pinIsValid(pin) {
    return /^\d{4}$/.test(pin)
  }

  async function handleSubmit(e) {
    e.preventDefault()

    if (!isEdit && !pinIsValid(form.pin_code)) {
      toast.error("Le code PIN doit être exactement 4 chiffres.")
      return
    }
    if (isEdit && form.pin_code !== "" && !pinIsValid(form.pin_code)) {
      toast.error("Le code PIN doit être exactement 4 chiffres.")
      return
    }

    const token = loadEstablishmentToken()
    if (!token) return
    setSaving(true)
    try {
      let saved
      if (isEdit) {
        const patch = buildPatch(form, operator)
        if (Object.keys(patch).length === 0) {
          toast("Aucune modification détectée.")
          onClose()
          return
        }
        saved = await updateOperator(token, operator.id, patch)
      } else {
        saved = await createOperator(token, {
          first_name: form.first_name,
          last_name: form.last_name,
          role: form.role,
          pin_code: form.pin_code,
          hygiene_training_date: form.hygiene_training_date || null,
          medical_check_date: form.medical_check_date || null,
        })
      }
      toast.success(isEdit ? "Opérateur mis à jour" : "Opérateur créé")
      onSaved(saved, isEdit)
    } catch (err) {
      toast.error(String(err.message))
    } finally {
      setSaving(false)
    }
  }

  const pinStrength =
    form.pin_code.length === 0 ? null
    : /^\d{4}$/.test(form.pin_code) ? "valid"
    : "invalid"

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>
            {isEdit ? "Modifier l'opérateur" : "Nouvel opérateur"}
          </DialogTitle>
          <DialogDescription>
            {isEdit
              ? "Laissez le code PIN vide pour conserver l'actuel."
              : "Un code PIN à 4 chiffres sera requis pour signer sur la tablette."}
          </DialogDescription>
        </DialogHeader>

        <form id="operator-form" onSubmit={handleSubmit} className="space-y-5 pt-1">
          {/* Identity */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="op-first">Prénom *</Label>
              <Input
                id="op-first"
                value={form.first_name}
                onChange={(e) => set("first_name", e.target.value)}
                placeholder="Jean-Pierre"
                required
                autoFocus
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="op-last">Nom *</Label>
              <Input
                id="op-last"
                value={form.last_name}
                onChange={(e) => set("last_name", e.target.value)}
                placeholder="Rousseau"
                required
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label>Rôle *</Label>
            <Select value={form.role} onValueChange={(v) => set("role", v)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ROLES.map((r) => (
                  <SelectItem key={r.value} value={r.value}>
                    {r.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <Separator />

          {/* PIN */}
          <div className="space-y-1.5">
            <Label htmlFor="op-pin" className="flex items-center gap-1.5">
              <KeyRound className="h-3.5 w-3.5" />
              Code PIN (4 chiffres){!isEdit && " *"}
            </Label>
            <div className="relative">
              <Input
                id="op-pin"
                type={showPin ? "text" : "password"}
                inputMode="numeric"
                maxLength={4}
                pattern="\d{4}"
                value={form.pin_code}
                onChange={(e) => set("pin_code", e.target.value.replace(/\D/g, "").slice(0, 4))}
                placeholder={isEdit ? "Laisser vide = inchangé" : "••••"}
                required={!isEdit}
                className={`pr-10 font-mono tracking-widest ${
                  pinStrength === "invalid" ? "border-destructive focus-visible:ring-destructive" : ""
                }`}
              />
              <button
                type="button"
                className="absolute inset-y-0 right-3 flex items-center text-muted-foreground hover:text-foreground"
                onClick={() => setShowPin((v) => !v)}
                tabIndex={-1}
              >
                {showPin ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            {pinStrength === "invalid" && (
              <p className="text-xs text-destructive">Exactement 4 chiffres requis.</p>
            )}
            {pinStrength === "valid" && (
              <p className="text-xs text-emerald-600">Code PIN valide ✓</p>
            )}
          </div>

          <Separator />

          {/* Compliance dates */}
          <div className="space-y-3">
            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Conformité réglementaire
            </p>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="op-hygiene" className="text-sm">
                  Formation hygiène
                </Label>
                <Input
                  id="op-hygiene"
                  type="date"
                  value={form.hygiene_training_date}
                  onChange={(e) => set("hygiene_training_date", e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="op-medical" className="text-sm">
                  Visite médicale
                </Label>
                <Input
                  id="op-medical"
                  type="date"
                  value={form.medical_check_date}
                  onChange={(e) => set("medical_check_date", e.target.value)}
                />
              </div>
            </div>
          </div>
        </form>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={saving}>
            Annuler
          </Button>
          <Button type="submit" form="operator-form" disabled={saving}>
            {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {isEdit ? "Enregistrer" : "Créer l'opérateur"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
