"use client"

import { useEffect, useState } from "react"
import { RefreshCcw } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
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
import { Textarea } from "@/components/ui/textarea"
import { PageHeader } from "@/components/shared/PageHeader"
import { StatusBadge } from "@/components/shared/StatusBadge"
import { getNonConformities, closeNonConformity } from "@/lib/api/nonconformities"
import { loadEstablishmentToken } from "@/lib/session/establishment"

const STATUS_OPTIONS = [
  { value: "ALL", label: "Tous les statuts" },
  { value: "OPEN", label: "Ouvertes" },
  { value: "IN_PROGRESS", label: "En cours" },
  { value: "RESOLVED", label: "Résolues" },
  { value: "CLOSED", label: "Clôturées" },
]

function fmt(dt) {
  if (!dt) return "—"
  return new Intl.DateTimeFormat("fr-FR", { dateStyle: "short", timeStyle: "short" }).format(new Date(dt))
}

export default function NonConformitiesPage() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState("ALL")
  const [closeTarget, setCloseTarget] = useState(null)
  const [closingComment, setClosingComment] = useState("")
  const [closeLoading, setCloseLoading] = useState(false)

  const token = loadEstablishmentToken()

  function load() {
    if (!token) return
    setLoading(true)
    const opts = statusFilter !== "ALL" ? { status: statusFilter } : {}
    getNonConformities(token, opts)
      .then((d) => setItems(d?.items ?? []))
      .catch(() => toast.error("Chargement impossible"))
      .finally(() => setLoading(false))
  }

  useEffect(load, [statusFilter])

  async function handleClose() {
    if (!closeTarget) return
    setCloseLoading(true)
    try {
      await closeNonConformity(token, closeTarget.id, closingComment || null)
      toast.success("Non-conformité clôturée")
      setCloseTarget(null)
      setClosingComment("")
      load()
    } catch (err) {
      toast.error(String(err.message))
    } finally {
      setCloseLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Non-conformités" description="Suivi des tickets HACCP et actions correctives.">
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
      </PageHeader>

      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Ouverture</TableHead>
              <TableHead className="hidden md:table-cell">Équipement</TableHead>
              <TableHead className="hidden md:table-cell">Mesure</TableHead>
              <TableHead>Statut</TableHead>
              <TableHead className="hidden lg:table-cell">Opérateur</TableHead>
              <TableHead className="text-right">Action</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow><TableCell colSpan={6} className="text-center text-muted-foreground">Chargement…</TableCell></TableRow>
            ) : items.length === 0 ? (
              <TableRow><TableCell colSpan={6} className="text-center text-muted-foreground">Aucune non-conformité</TableCell></TableRow>
            ) : (
              items.map((nc) => (
                <TableRow key={nc.id}>
                  <TableCell className="text-sm">{fmt(nc.opened_at)}</TableCell>
                  <TableCell className="hidden md:table-cell">
                    <span className="font-medium">{nc.equipment_name ?? "—"}</span>
                  </TableCell>
                  <TableCell className="hidden tabular-nums md:table-cell">
                    {nc.measured_value != null ? `${nc.measured_value}°C` : "—"}
                    {nc.deviation_celsius != null && (
                      <span className="ml-1 text-xs text-destructive">(+{nc.deviation_celsius}°)</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={nc.status} />
                  </TableCell>
                  <TableCell className="hidden lg:table-cell text-sm text-muted-foreground">
                    {nc.opened_by_name}
                  </TableCell>
                  <TableCell className="text-right">
                    {nc.status === "RESOLVED" && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setCloseTarget(nc)
                          setClosingComment("")
                        }}
                      >
                        Clôturer
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Close dialog */}
      <Dialog open={!!closeTarget} onOpenChange={(o) => { if (!o && !closeLoading) setCloseTarget(null) }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Clôturer la non-conformité</DialogTitle>
            <DialogDescription>
              {closeTarget?.equipment_name} — relevé du {fmt(closeTarget?.opened_at)}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            {closeTarget?.corrective_action_description && (
              <div className="rounded-lg border bg-muted/50 p-3 text-sm">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Action corrective</p>
                <p className="mt-1">{closeTarget.corrective_action_description}</p>
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="close-comment">Commentaire de clôture (facultatif)</Label>
              <Textarea
                id="close-comment"
                placeholder="Ex : vérification réalisée, conformité rétablie…"
                value={closingComment}
                onChange={(e) => setClosingComment(e.target.value)}
                disabled={closeLoading}
                rows={3}
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setCloseTarget(null)} disabled={closeLoading}>Annuler</Button>
              <Button onClick={handleClose} disabled={closeLoading}>
                {closeLoading ? "En cours…" : "Confirmer la clôture"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
