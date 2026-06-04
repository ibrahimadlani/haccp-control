"use client"

import { useEffect, useState } from "react"
import { Plus, Pencil, Trash2, RefreshCw } from "lucide-react"
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
import { PageHeader } from "@/components/shared/PageHeader"
import { ConfirmDialog } from "@/components/shared/ConfirmDialog"
import { OperatorModal } from "@/components/operators/OperatorModal"
import { getOperators, deactivateOperator } from "@/lib/api/operators"
import { loadEstablishmentToken } from "@/lib/session/establishment"

const ROLE_LABELS = {
  MANAGER:  "Manager",
  CHEF:     "Chef de cuisine",
  COMMIS:   "Commis",
  PLONGEUR: "Plongeur",
}

function isExpiredOrMissing(dateStr) {
  if (!dateStr) return "missing"
  const oneYearAgo = new Date()
  oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1)
  return new Date(dateStr) < oneYearAgo ? "expired" : "ok"
}

function ComplianceBadge({ date }) {
  const status = isExpiredOrMissing(date)
  if (status === "missing") {
    return (
      <Badge variant="destructive" className="text-xs font-normal">
        À faire
      </Badge>
    )
  }
  if (status === "expired") {
    return (
      <Badge variant="destructive" className="text-xs font-normal">
        Expiré
      </Badge>
    )
  }
  return (
    <Badge className="bg-emerald-600 text-xs font-normal hover:bg-emerald-700">
      À jour
    </Badge>
  )
}

export default function StaffPage() {
  const [operators, setOperators] = useState([])
  const [loading, setLoading]     = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const [editTarget, setEditTarget]   = useState(null)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleteLoading, setDeleteLoading] = useState(false)

  const token = loadEstablishmentToken()

  function load() {
    if (!token) return
    setLoading(true)
    getOperators(token)
      .then((res) => setOperators(res.items ?? []))
      .catch(() => toast.error("Impossible de charger le personnel"))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  function openCreate() {
    setEditTarget(null)
    setModalOpen(true)
  }

  function openEdit(op) {
    setEditTarget(op)
    setModalOpen(true)
  }

  function handleSaved(saved, isEdit) {
    setModalOpen(false)
    if (isEdit) {
      setOperators((prev) => prev.map((op) => (op.id === saved.id ? saved : op)))
    } else {
      setOperators((prev) => [...prev, saved])
    }
  }

  async function confirmDelete() {
    if (!deleteTarget) return
    setDeleteLoading(true)
    try {
      await deactivateOperator(token, deleteTarget.id)
      toast.success(`${deleteTarget.first_name} ${deleteTarget.last_name} archivé`)
      setOperators((prev) => prev.filter((op) => op.id !== deleteTarget.id))
      setDeleteTarget(null)
    } catch (err) {
      toast.error(String(err.message))
    } finally {
      setDeleteLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Registre du Personnel"
        description="Opérateurs habilités à signer les actions HACCP sur tablette."
      >
        <Button variant="outline" size="icon" onClick={load} aria-label="Rafraîchir">
          <RefreshCw className="h-4 w-4" />
        </Button>
        <Button onClick={openCreate}>
          <Plus className="mr-2 h-4 w-4" />
          Ajouter un opérateur
        </Button>
      </PageHeader>

      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Nom complet</TableHead>
              <TableHead className="hidden sm:table-cell">Rôle</TableHead>
              <TableHead>Formation hygiène</TableHead>
              <TableHead className="hidden md:table-cell">Visite médicale</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={5} className="py-8 text-center text-muted-foreground">
                  Chargement…
                </TableCell>
              </TableRow>
            ) : operators.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="py-8 text-center text-muted-foreground">
                  Aucun opérateur enregistré. Commencez par en ajouter un.
                </TableCell>
              </TableRow>
            ) : (
              operators.map((op) => (
                <TableRow key={op.id}>
                  <TableCell className="font-medium">
                    {op.first_name} {op.last_name}
                  </TableCell>
                  <TableCell className="hidden sm:table-cell">
                    <Badge variant="outline">{ROLE_LABELS[op.role] ?? op.role}</Badge>
                  </TableCell>
                  <TableCell>
                    <ComplianceBadge date={op.hygiene_training_date} />
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    <ComplianceBadge date={op.medical_check_date} />
                  </TableCell>
                  <TableCell className="space-x-1 text-right">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => openEdit(op)}
                      aria-label="Modifier"
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setDeleteTarget(op)}
                      aria-label="Archiver"
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

      <OperatorModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        operator={editTarget}
        onSaved={handleSaved}
      />

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(o) => { if (!o) setDeleteTarget(null) }}
        title="Archiver cet opérateur ?"
        description={`"${deleteTarget?.first_name} ${deleteTarget?.last_name}" sera désactivé. Ses signatures HACCP passées restent conservées pour la traçabilité.`}
        onConfirm={confirmDelete}
        loading={deleteLoading}
      />
    </div>
  )
}
