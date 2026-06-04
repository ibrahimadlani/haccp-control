"use client"

import { useState } from "react"
import { toast } from "sonner"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { PageHeader } from "@/components/shared/PageHeader"
import { createOrganisation } from "@/lib/api/platform"
import { usePlatform } from "@/lib/contexts/PlatformContext"

const schema = z.object({
  nom_entite: z.string().min(2, "Minimum 2 caractères"),
  type_secteur: z.enum(["PRIVE", "PUBLIC"]),
  identifiant_legal: z.string().optional(),
  admin_login_email: z.string().email("Email invalide"),
  admin_password: z.string().min(12, "Minimum 12 caractères").regex(
    /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^a-zA-Z0-9])/,
    "Doit contenir majuscule, minuscule, chiffre et symbole"
  ),
})

export default function PlatformOrganisationsPage() {
  const { platformKey } = usePlatform()
  const [lastCreated, setLastCreated] = useState(null)

  const form = useForm({
    resolver: zodResolver(schema),
    defaultValues: { nom_entite: "", type_secteur: "PRIVE", identifiant_legal: "", admin_login_email: "", admin_password: "" },
  })

  async function onSubmit(values) {
    try {
      const result = await createOrganisation(platformKey, values)
      setLastCreated(result)
      toast.success(`Organisation "${result.nom_entite}" créée`)
      form.reset()
    } catch (err) {
      toast.error(String(err.message))
    }
  }

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <PageHeader title="Créer une organisation" description="Onboarding d'un nouveau tenant SaaS." />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Nouvelle organisation</CardTitle>
          <CardDescription>Le compte admin pourra ensuite créer ses établissements.</CardDescription>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <FormField control={form.control} name="nom_entite" render={({ field }) => (
                <FormItem><FormLabel>Nom de l'organisation</FormLabel><FormControl><Input placeholder="Groupe Restauration Sud" {...field} /></FormControl><FormMessage /></FormItem>
              )} />
              <div className="grid grid-cols-2 gap-4">
                <FormField control={form.control} name="type_secteur" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Secteur</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl><SelectTrigger><SelectValue /></SelectTrigger></FormControl>
                      <SelectContent>
                        <SelectItem value="PRIVE">Privé</SelectItem>
                        <SelectItem value="PUBLIC">Public</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )} />
                <FormField control={form.control} name="identifiant_legal" render={({ field }) => (
                  <FormItem><FormLabel>SIRET (facultatif)</FormLabel><FormControl><Input maxLength={14} {...field} /></FormControl><FormMessage /></FormItem>
                )} />
              </div>
              <Separator />
              <FormField control={form.control} name="admin_login_email" render={({ field }) => (
                <FormItem><FormLabel>Email admin</FormLabel><FormControl><Input type="email" {...field} /></FormControl><FormMessage /></FormItem>
              )} />
              <FormField control={form.control} name="admin_password" render={({ field }) => (
                <FormItem><FormLabel>Mot de passe admin</FormLabel><FormControl><Input type="password" {...field} /></FormControl><FormMessage /></FormItem>
              )} />
              <Button type="submit" className="w-full">Créer l'organisation</Button>
            </form>
          </Form>
        </CardContent>
      </Card>

      {lastCreated && (
        <Alert>
          <AlertDescription className="space-y-1">
            <p className="font-medium">Organisation créée avec succès</p>
            <p className="text-sm">
              <span className="text-muted-foreground">ID : </span>
              <code className="font-mono text-xs">{lastCreated.id}</code>
            </p>
            <p className="text-sm">
              <Badge>{lastCreated.nom_entite}</Badge>{" "}
              <Badge variant="outline">{lastCreated.type_secteur}</Badge>
            </p>
          </AlertDescription>
        </Alert>
      )}
    </div>
  )
}
