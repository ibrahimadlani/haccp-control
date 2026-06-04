"use client"

import { useEffect, useState } from "react"
import { Plus, Trash2 } from "lucide-react"
import { toast } from "sonner"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Badge } from "@/components/ui/badge"
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { PageHeader } from "@/components/shared/PageHeader"
import { ConfirmDialog } from "@/components/shared/ConfirmDialog"
import {
  createEstablishment,
  deleteEstablishment,
  getOrganisationOverview,
} from "@/lib/api/organisation"
import { loadOrganisationContext, loadOrganisationToken } from "@/lib/session/organisation"

const schema = z.object({
  nom_site: z.string().min(2, "Minimum 2 caractères"),
  adresse: z.string().optional(),
  timezone: z.string().min(2).default("Europe/Paris"),
  telephone_site: z.string().optional(),
})

export default function EstablishmentsPage() {
  const [sites, setSites] = useState([])
  const [loading, setLoading] = useState(true)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleteLoading, setDeleteLoading] = useState(false)

  const token = loadOrganisationToken()
  const ctx = loadOrganisationContext()
  const orgId = ctx?.organisation_id

  const form = useForm({ resolver: zodResolver(schema), defaultValues: { nom_site: "", adresse: "", timezone: "Europe/Paris", telephone_site: "" } })

  function load() {
    if (!token || !orgId) return
    setLoading(true)
    getOrganisationOverview(token, orgId)
      .then((d) => setSites(d?.establishments ?? []))
      .catch(() => toast.error("Chargement impossible"))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  async function onSubmit(values) {
    try {
      await createEstablishment(token, orgId, values)
      toast.success("Établissement créé")
      setDialogOpen(false)
      load()
    } catch (err) {
      toast.error(String(err.message))
    }
  }

  async function confirmDelete() {
    if (!deleteTarget) return
    setDeleteLoading(true)
    try {
      await deleteEstablishment(token, deleteTarget.id)
      toast.success("Établissement supprimé")
      setDeleteTarget(null)
      load()
    } catch (err) {
      toast.error(String(err.message))
    } finally {
      setDeleteLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Établissements" description="Gérez les sites de votre organisation.">
        <Button onClick={() => { form.reset(); setDialogOpen(true) }}>
          <Plus className="mr-2 h-4 w-4" />
          Nouveau site
        </Button>
      </PageHeader>

      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Nom</TableHead>
              <TableHead>Fuseau horaire</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow><TableCell colSpan={3} className="text-center text-muted-foreground">Chargement…</TableCell></TableRow>
            ) : sites.length === 0 ? (
              <TableRow><TableCell colSpan={3} className="text-center text-muted-foreground">Aucun établissement</TableCell></TableRow>
            ) : (
              sites.map((s) => (
                <TableRow key={s.id}>
                  <TableCell className="font-medium">{s.site_name}</TableCell>
                  <TableCell><Badge variant="outline">{s.timezone}</Badge></TableCell>
                  <TableCell className="text-right">
                    <Button variant="ghost" size="icon" onClick={() => setDeleteTarget(s)}>
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader><DialogTitle>Nouvel établissement</DialogTitle></DialogHeader>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <FormField control={form.control} name="nom_site" render={({ field }) => (
                <FormItem><FormLabel>Nom du site</FormLabel><FormControl><Input placeholder="Restaurant Le Provençal" {...field} /></FormControl><FormMessage /></FormItem>
              )} />
              <FormField control={form.control} name="adresse" render={({ field }) => (
                <FormItem><FormLabel>Adresse (facultatif)</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>
              )} />
              <FormField control={form.control} name="timezone" render={({ field }) => (
                <FormItem><FormLabel>Fuseau horaire</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>
              )} />
              <FormField control={form.control} name="telephone_site" render={({ field }) => (
                <FormItem><FormLabel>Téléphone (facultatif)</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>
              )} />
              <div className="flex justify-end gap-2 pt-2">
                <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>Annuler</Button>
                <Button type="submit">Créer</Button>
              </div>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(o) => { if (!o) setDeleteTarget(null) }}
        title="Supprimer l'établissement ?"
        description={`"${deleteTarget?.site_name}" et toutes ses données seront archivés.`}
        onConfirm={confirmDelete}
        loading={deleteLoading}
      />
    </div>
  )
}
