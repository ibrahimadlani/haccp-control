"use client"

import { useEffect } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Loader2 } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"
import { Textarea } from "@/components/ui/textarea"
import { createSupplier, updateSupplier } from "@/lib/api/suppliers"
import { loadEstablishmentToken } from "@/lib/session/establishment"

const COUNTRIES = [
  "France", "Belgique", "Suisse", "Luxembourg",
  "Allemagne", "Espagne", "Italie", "Pays-Bas", "Royaume-Uni", "Autre",
]

const STATUSES = [
  { value: "pending", label: "En attente" },
  { value: "approved", label: "Agréé" },
  { value: "rejected", label: "Refusé" },
  { value: "occasional", label: "Occasionnel" },
]

const schema = z
  .object({
    name: z.string().min(2, "Minimum 2 caractères"),
    company_registration_id: z.string().optional().or(z.literal("")),
    country: z.string().min(1),
    address: z.string().optional().or(z.literal("")),
    city: z.string().optional().or(z.literal("")),
    postal_code: z.string().optional().or(z.literal("")),
    contact_name: z.string().optional().or(z.literal("")),
    contact_email: z.string().email("Email invalide").optional().or(z.literal("")),
    contact_phone: z.string().optional().or(z.literal("")),
    emergency_contact_name: z.string().optional().or(z.literal("")),
    emergency_phone: z.string().optional().or(z.literal("")),
    status: z.string().min(1),
    certification_type: z.string().optional().or(z.literal("")),
    internal_notes: z.string().optional().or(z.literal("")),
  })
  .refine(
    (d) => {
      if (d.country === "France" && d.company_registration_id) {
        return d.company_registration_id.replace(/\s/g, "").length === 14
      }
      return true
    },
    {
      message: "Le SIRET doit contenir exactement 14 caractères pour la France.",
      path: ["company_registration_id"],
    }
  )

const DEFAULTS = {
  name: "",
  company_registration_id: "",
  country: "France",
  address: "",
  city: "",
  postal_code: "",
  contact_name: "",
  contact_email: "",
  contact_phone: "",
  emergency_contact_name: "",
  emergency_phone: "",
  status: "pending",
  certification_type: "",
  internal_notes: "",
}

export function SupplierFormModal({ open, onOpenChange, supplier, onSuccess }) {
  const isEditing = !!supplier

  const form = useForm({
    resolver: zodResolver(schema),
    defaultValues: DEFAULTS,
  })

  const watchedCountry = form.watch("country")

  useEffect(() => {
    if (open) {
      form.reset(
        supplier
          ? {
              name: supplier.name ?? "",
              company_registration_id: supplier.company_registration_id ?? "",
              country: supplier.country ?? "France",
              address: supplier.address ?? "",
              city: supplier.city ?? "",
              postal_code: supplier.postal_code ?? "",
              contact_name: supplier.contact_name ?? "",
              contact_email: supplier.contact_email ?? "",
              contact_phone: supplier.contact_phone ?? "",
              emergency_contact_name: supplier.emergency_contact_name ?? "",
              emergency_phone: supplier.emergency_phone ?? "",
              status: supplier.status ?? "pending",
              certification_type: supplier.certification_type ?? "",
              internal_notes: supplier.internal_notes ?? "",
            }
          : DEFAULTS
      )
    }
  }, [open, supplier])

  async function onSubmit(values) {
    const token = loadEstablishmentToken()
    const payload = Object.fromEntries(
      Object.entries(values).map(([k, v]) => [k, v === "" ? null : v])
    )
    try {
      if (isEditing) {
        await updateSupplier(token, supplier.id, payload)
        toast.success("Fournisseur mis à jour.")
      } else {
        await createSupplier(token, payload)
        toast.success("Fournisseur créé.")
      }
      onSuccess()
    } catch (err) {
      toast.error(String(err.message))
    }
  }

  const registrationLabel =
    watchedCountry === "France" ? "SIRET (14 chiffres)" : "N° d'identification (TVA / équivalent)"

  return (
    <Dialog open={open} onOpenChange={form.formState.isSubmitting ? undefined : onOpenChange}>
      <DialogContent className="max-h-[90vh] w-full max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEditing ? "Modifier le fournisseur" : "Nouveau fournisseur"}</DialogTitle>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">

            {/* ── Identité ── */}
            <section className="space-y-4">
              <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                Identité
              </p>

              <div className="grid gap-4 sm:grid-cols-2">
                <FormField control={form.control} name="name" render={({ field }) => (
                  <FormItem className="sm:col-span-2">
                    <FormLabel>Nom du fournisseur *</FormLabel>
                    <FormControl><Input placeholder="Boucherie Martin" {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )} />

                <FormField control={form.control} name="country" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Pays *</FormLabel>
                    <FormControl>
                      <select
                        {...field}
                        className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
                      >
                        {COUNTRIES.map((c) => (
                          <option key={c} value={c}>{c}</option>
                        ))}
                      </select>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )} />

                <FormField control={form.control} name="company_registration_id" render={({ field }) => (
                  <FormItem>
                    <FormLabel>{registrationLabel}</FormLabel>
                    <FormControl>
                      <Input
                        placeholder={watchedCountry === "France" ? "12345678901234" : "Optionnel"}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )} />
              </div>
            </section>

            <Separator />

            {/* ── Adresse ── */}
            <section className="space-y-4">
              <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                Adresse
              </p>
              <div className="grid gap-4 sm:grid-cols-3">
                <FormField control={form.control} name="address" render={({ field }) => (
                  <FormItem className="sm:col-span-3">
                    <FormLabel>Adresse</FormLabel>
                    <FormControl><Input placeholder="12 rue des Bouchers" {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )} />
                <FormField control={form.control} name="postal_code" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Code postal</FormLabel>
                    <FormControl><Input placeholder="75001" {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )} />
                <FormField control={form.control} name="city" render={({ field }) => (
                  <FormItem className="sm:col-span-2">
                    <FormLabel>Ville</FormLabel>
                    <FormControl><Input placeholder="Paris" {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )} />
              </div>
            </section>

            <Separator />

            {/* ── Contact ── */}
            <section className="space-y-4">
              <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                Contact principal
              </p>
              <div className="grid gap-4 sm:grid-cols-2">
                <FormField control={form.control} name="contact_name" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Nom du contact</FormLabel>
                    <FormControl><Input placeholder="Jean Dupont" {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )} />
                <FormField control={form.control} name="contact_phone" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Téléphone</FormLabel>
                    <FormControl><Input type="tel" placeholder="+33 6 12 34 56 78" {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )} />
                <FormField control={form.control} name="contact_email" render={({ field }) => (
                  <FormItem className="sm:col-span-2">
                    <FormLabel>Email</FormLabel>
                    <FormControl><Input type="email" placeholder="contact@fournisseur.fr" {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )} />
              </div>
            </section>

            <Separator />

            {/* ── Contact urgence ── */}
            <section className="space-y-4">
              <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                Contact d'urgence
              </p>
              <div className="grid gap-4 sm:grid-cols-2">
                <FormField control={form.control} name="emergency_contact_name" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Nom</FormLabel>
                    <FormControl><Input placeholder="Marie Martin" {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )} />
                <FormField control={form.control} name="emergency_phone" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Téléphone d'urgence</FormLabel>
                    <FormControl><Input type="tel" placeholder="+33 6 00 00 00 00" {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )} />
              </div>
            </section>

            <Separator />

            {/* ── Agrément ── */}
            <section className="space-y-4">
              <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                Agrément sanitaire
              </p>
              <div className="grid gap-4 sm:grid-cols-2">
                <FormField control={form.control} name="status" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Statut *</FormLabel>
                    <FormControl>
                      <select
                        {...field}
                        className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
                      >
                        {STATUSES.map(({ value, label }) => (
                          <option key={value} value={value}>{label}</option>
                        ))}
                      </select>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )} />
                <FormField control={form.control} name="certification_type" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Type de certification</FormLabel>
                    <FormControl><Input placeholder="IFS, BRC, ISO 22000…" {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )} />
              </div>

              <FormField control={form.control} name="internal_notes" render={({ field }) => (
                <FormItem>
                  <FormLabel>Notes internes</FormLabel>
                  <FormControl>
                    <Textarea
                      placeholder="Observations, conditions particulières, historique…"
                      rows={3}
                      className="resize-none"
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )} />
            </section>

            {/* ── Actions ── */}
            <div className="flex justify-end gap-2 border-t pt-4">
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={form.formState.isSubmitting}
              >
                Annuler
              </Button>
              <Button type="submit" disabled={form.formState.isSubmitting}>
                {form.formState.isSubmitting && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                {isEditing ? "Mettre à jour" : "Créer le fournisseur"}
              </Button>
            </div>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
