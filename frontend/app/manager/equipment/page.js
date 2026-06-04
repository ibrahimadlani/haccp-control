"use client"

import { useEffect, useState } from "react"
import { Plus, Pencil, Trash2 } from "lucide-react"
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
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
import { createEquipment, deleteEquipment, getEquipments, updateEquipment } from "@/lib/api/equipment"
import { loadEstablishmentContext, loadEstablishmentToken } from "@/lib/session/establishment"

const EQUIPMENT_TYPES = [
  ["CHAMBRE_FROIDE_POSITIVE", "Chambre froide positive"],
  ["CHAMBRE_FROIDE_NEGATIVE", "Chambre froide négative"],
  ["REFRIGERATEUR_VIANDE", "Réfrigérateur viande"],
  ["REFRIGERATEUR_POISSON", "Réfrigérateur poisson"],
  ["VITRINE_REFRIGEREE", "Vitrine réfrigérée"],
  ["VITRINE_CHAUFFANTE", "Vitrine chauffante"],
  ["CELLULE_REFROIDISSEMENT", "Cellule de refroidissement"],
  ["CHAUFFE_ASSIETTE_FOUR", "Chauffe-assiette / four"],
  ["CONGELATEUR_CONSERVATEUR", "Congélateur conservateur"],
  ["RESERVE_SECHE", "Réserve sèche"],
  ["AUTRE", "Autre"],
]

const schema = z
  .object({
    name: z.string().min(2, "Minimum 2 caractères"),
    equipment_type: z.string().min(1, "Requis"),
    min_target_temperature: z.string().regex(/^-?\d{1,3}(\.\d{1,2})?$/, "Format invalide"),
    max_target_temperature: z.string().regex(/^-?\d{1,3}(\.\d{1,2})?$/, "Format invalide"),
  })
  .refine((d) => parseFloat(d.min_target_temperature) < parseFloat(d.max_target_temperature), {
    message: "Min doit être inférieur à Max",
    path: ["max_target_temperature"],
  })

export default function EquipmentPage() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleteLoading, setDeleteLoading] = useState(false)

  const form = useForm({ resolver: zodResolver(schema) })

  const token = loadEstablishmentToken()
  const ctx = loadEstablishmentContext()
  const establishmentId = ctx?.etablissement_id

  function load() {
    if (!token) return
    setLoading(true)
    getEquipments(token)
      .then((d) => setItems(d?.items ?? []))
      .catch(() => toast.error("Chargement impossible"))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  function openCreate() {
    setEditing(null)
    form.reset({ name: "", equipment_type: "CHAMBRE_FROIDE_POSITIVE", min_target_temperature: "0.00", max_target_temperature: "4.00" })
    setDialogOpen(true)
  }

  function openEdit(item) {
    setEditing(item)
    form.reset({
      name: item.name,
      equipment_type: item.equipment_type,
      min_target_temperature: String(item.min_target_temperature),
      max_target_temperature: String(item.max_target_temperature),
    })
    setDialogOpen(true)
  }

  async function onSubmit(values) {
    try {
      if (editing) {
        await updateEquipment(token, editing.id, values)
        toast.success("Équipement mis à jour")
      } else {
        await createEquipment(token, { ...values, establishment_id: establishmentId })
        toast.success("Équipement créé")
      }
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
      await deleteEquipment(token, deleteTarget.id)
      toast.success("Équipement supprimé")
      setDeleteTarget(null)
      load()
    } catch (err) {
      toast.error(String(err.message))
    } finally {
      setDeleteLoading(false)
    }
  }

  const typeLabel = (t) => EQUIPMENT_TYPES.find(([v]) => v === t)?.[1] ?? t

  return (
    <div className="space-y-6">
      <PageHeader title="Équipements HACCP" description="Gérez les équipements et leurs seuils de température.">
        <Button onClick={openCreate}>
          <Plus className="mr-2 h-4 w-4" />
          Ajouter
        </Button>
      </PageHeader>

      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Nom</TableHead>
              <TableHead className="hidden sm:table-cell">Type</TableHead>
              <TableHead>Seuils (°C)</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={4} className="text-center text-muted-foreground">
                  Chargement…
                </TableCell>
              </TableRow>
            ) : items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} className="text-center text-muted-foreground">
                  Aucun équipement
                </TableCell>
              </TableRow>
            ) : (
              items.map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="font-medium">{item.name}</TableCell>
                  <TableCell className="hidden sm:table-cell">
                    <Badge variant="outline">{typeLabel(item.equipment_type)}</Badge>
                  </TableCell>
                  <TableCell className="tabular-nums">
                    {item.min_target_temperature} / {item.max_target_temperature}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button variant="ghost" size="icon" onClick={() => openEdit(item)}>
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="icon" onClick={() => setDeleteTarget(item)}>
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Create / Edit dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{editing ? "Modifier l'équipement" : "Nouvel équipement"}</DialogTitle>
          </DialogHeader>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <FormField control={form.control} name="name" render={({ field }) => (
                <FormItem>
                  <FormLabel>Nom</FormLabel>
                  <FormControl><Input placeholder="Chambre froide positive 1" {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="equipment_type" render={({ field }) => (
                <FormItem>
                  <FormLabel>Type</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl><SelectTrigger><SelectValue /></SelectTrigger></FormControl>
                    <SelectContent>
                      {EQUIPMENT_TYPES.map(([v, l]) => (
                        <SelectItem key={v} value={v}>{l}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )} />
              <div className="grid grid-cols-2 gap-4">
                <FormField control={form.control} name="min_target_temperature" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Temp. min (°C)</FormLabel>
                    <FormControl><Input type="number" step="0.01" {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )} />
                <FormField control={form.control} name="max_target_temperature" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Temp. max (°C)</FormLabel>
                    <FormControl><Input type="number" step="0.01" {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )} />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>Annuler</Button>
                <Button type="submit">{editing ? "Mettre à jour" : "Créer"}</Button>
              </div>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(o) => { if (!o) setDeleteTarget(null) }}
        title="Supprimer l'équipement ?"
        description={`"${deleteTarget?.name}" sera archivé. Cette action peut être annulée par un administrateur.`}
        onConfirm={confirmDelete}
        loading={deleteLoading}
      />
    </div>
  )
}
