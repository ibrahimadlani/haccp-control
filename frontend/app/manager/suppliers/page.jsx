"use client"

import { useEffect, useState } from "react"
import { Plus, Pencil, Trash2, RefreshCcw } from "lucide-react"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { PageHeader } from "@/components/shared/PageHeader"
import { ConfirmDialog } from "@/components/shared/ConfirmDialog"
import { StatusBadge } from "@/components/shared/StatusBadge"
import { SupplierFormModal } from "@/components/SupplierFormModal"
import { getSuppliers, deleteSupplier } from "@/lib/api/suppliers"
import { loadEstablishmentToken } from "@/lib/session/establishment"

const STATUS_OPTIONS = [
  { value: "ALL", label: "Tous les statuts" },
  { value: "pending", label: "En attente" },
  { value: "approved", label: "Agréés" },
  { value: "rejected", label: "Refusés" },
  { value: "occasional", label: "Occasionnels" },
]

export default function SuppliersPage() {
  const [suppliers, setSuppliers] = useState([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState("ALL")

  const [formOpen, setFormOpen] = useState(false)
  const [editTarget, setEditTarget] = useState(null)

  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleteLoading, setDeleteLoading] = useState(false)

  function load() {
    const token = loadEstablishmentToken()
    if (!token) return
    setLoading(true)
    const opts = statusFilter !== "ALL" ? { status: statusFilter } : {}
    getSuppliers(token, opts)
      .then((d) => setSuppliers(d?.items ?? []))
      .catch(() => toast.error("Impossible de charger les fournisseurs."))
      .finally(() => setLoading(false))
  }

  useEffect(load, [statusFilter])

  function openCreate() {
    setEditTarget(null)
    setFormOpen(true)
  }

  function openEdit(supplier) {
    setEditTarget(supplier)
    setFormOpen(true)
  }

  async function confirmDelete() {
    if (!deleteTarget) return
    const token = loadEstablishmentToken()
    setDeleteLoading(true)
    try {
      await deleteSupplier(token, deleteTarget.id)
      toast.success(`Fournisseur "${deleteTarget.name}" désactivé.`)
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
      <PageHeader
        title="Fournisseurs"
        description="Gérez vos fournisseurs et leurs agréments sanitaires."
      >
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {STATUS_OPTIONS.map(({ value, label }) => (
              <SelectItem key={value} value={value}>{label}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Button variant="outline" size="icon" onClick={load}>
          <RefreshCcw className="h-4 w-4" />
        </Button>

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
              <TableHead className="hidden md:table-cell">Pays</TableHead>
              <TableHead>Statut</TableHead>
              <TableHead className="hidden lg:table-cell">Contact</TableHead>
              <TableHead className="hidden lg:table-cell">Tél. urgence</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              Array.from({ length: 4 }).map((_, i) => (
                <TableRow key={i}>
                  {Array.from({ length: 6 }).map((_, j) => (
                    <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>
                  ))}
                </TableRow>
              ))
            ) : suppliers.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="py-12 text-center text-muted-foreground">
                  Aucun fournisseur{statusFilter !== "ALL" ? " pour ce statut" : ""}.
                </TableCell>
              </TableRow>
            ) : (
              suppliers.map((s) => (
                <TableRow key={s.id}>
                  <TableCell>
                    <div>
                      <p className="font-medium">{s.name}</p>
                      {s.company_registration_id && (
                        <p className="font-mono text-xs text-muted-foreground">
                          {s.company_registration_id}
                        </p>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    <Badge variant="outline">{s.country}</Badge>
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={s.status} />
                  </TableCell>
                  <TableCell className="hidden lg:table-cell">
                    {s.contact_name ? (
                      <div className="text-sm">
                        <p>{s.contact_name}</p>
                        {s.contact_email && (
                          <p className="text-muted-foreground">{s.contact_email}</p>
                        )}
                      </div>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell className="hidden lg:table-cell">
                    {s.emergency_phone ? (
                      <div className="text-sm">
                        <p>{s.emergency_phone}</p>
                        {s.emergency_contact_name && (
                          <p className="text-muted-foreground">{s.emergency_contact_name}</p>
                        )}
                      </div>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button variant="ghost" size="icon" onClick={() => openEdit(s)}>
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setDeleteTarget(s)}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <SupplierFormModal
        open={formOpen}
        onOpenChange={setFormOpen}
        supplier={editTarget}
        onSuccess={() => { setFormOpen(false); load() }}
      />

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(o) => { if (!o) setDeleteTarget(null) }}
        title="Désactiver ce fournisseur ?"
        description={`"${deleteTarget?.name}" sera marqué inactif (soft delete). Il n'apparaîtra plus dans les listes mais ses données sont conservées.`}
        onConfirm={confirmDelete}
        loading={deleteLoading}
      />
    </div>
  )
}
