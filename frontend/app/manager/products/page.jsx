"use client"

import { useEffect, useState } from "react"
import { Plus, Pencil, Trash2, RefreshCcw, Thermometer } from "lucide-react"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
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
import { ProductFormModal } from "@/components/ProductFormModal"
import { getProducts, deleteProduct } from "@/lib/api/products"
import { getSuppliers } from "@/lib/api/suppliers"
import { loadEstablishmentToken } from "@/lib/session/establishment"

function TempBadge({ product }) {
  if (!product.has_temperature_control) {
    return <Badge variant="secondary" className="text-xs font-normal">Non</Badge>
  }
  return (
    <Badge className="gap-1 bg-blue-600 text-xs font-normal hover:bg-blue-700">
      <Thermometer className="h-3 w-3" />
      {product.min_temperature}°C → {product.max_temperature}°C
    </Badge>
  )
}

export default function ProductsPage() {
  const [products, setProducts]     = useState([])
  const [suppliers, setSuppliers]   = useState([])
  const [loading, setLoading]       = useState(true)
  const [formOpen, setFormOpen]     = useState(false)
  const [editTarget, setEditTarget] = useState(null)
  const [deleteTarget, setDeleteTarget]   = useState(null)
  const [deleteLoading, setDeleteLoading] = useState(false)

  function load() {
    const token = loadEstablishmentToken()
    if (!token) return
    setLoading(true)
    Promise.all([
      getProducts(token),
      getSuppliers(token),
    ])
      .then(([p, s]) => {
        setProducts(p?.items ?? [])
        setSuppliers(s?.items ?? [])
      })
      .catch(() => toast.error("Impossible de charger le catalogue."))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  function supplierName(id) {
    return suppliers.find((s) => s.id === id)?.name ?? "—"
  }

  function openCreate() {
    setEditTarget(null)
    setFormOpen(true)
  }

  function openEdit(product) {
    setEditTarget(product)
    setFormOpen(true)
  }

  async function confirmDelete() {
    if (!deleteTarget) return
    const token = loadEstablishmentToken()
    setDeleteLoading(true)
    try {
      await deleteProduct(token, deleteTarget.id)
      toast.success(`"${deleteTarget.name}" désactivé.`)
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
        title="Catalogue Produits"
        description="Gérez les produits et leurs règles de contrôle sanitaire à la réception."
      >
        <Button variant="outline" size="icon" onClick={load} aria-label="Rafraîchir">
          <RefreshCcw className="h-4 w-4" />
        </Button>
        <Button onClick={openCreate}>
          <Plus className="mr-2 h-4 w-4" />
          Ajouter un produit
        </Button>
      </PageHeader>

      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Produit</TableHead>
              <TableHead className="hidden md:table-cell">Fournisseur</TableHead>
              <TableHead className="hidden lg:table-cell">Réf / GTIN</TableHead>
              <TableHead>Contrôle T°</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              Array.from({ length: 4 }).map((_, i) => (
                <TableRow key={i}>
                  {Array.from({ length: 5 }).map((_, j) => (
                    <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>
                  ))}
                </TableRow>
              ))
            ) : products.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="py-12 text-center text-muted-foreground">
                  Aucun produit dans le catalogue. Commencez par en ajouter un.
                </TableCell>
              </TableRow>
            ) : (
              products.map((p) => (
                <TableRow key={p.id}>
                  <TableCell>
                    <p className="font-medium">{p.name}</p>
                  </TableCell>
                  <TableCell className="hidden md:table-cell text-sm text-muted-foreground">
                    {supplierName(p.supplier_id)}
                  </TableCell>
                  <TableCell className="hidden lg:table-cell">
                    {p.internal_reference || p.gtin ? (
                      <div className="space-y-0.5">
                        {p.internal_reference && (
                          <p className="text-sm">{p.internal_reference}</p>
                        )}
                        {p.gtin && (
                          <p className="font-mono text-xs text-muted-foreground">{p.gtin}</p>
                        )}
                      </div>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <TempBadge product={p} />
                  </TableCell>
                  <TableCell className="space-x-1 text-right">
                    <Button variant="ghost" size="icon" onClick={() => openEdit(p)} aria-label="Modifier">
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setDeleteTarget(p)}
                      aria-label="Désactiver"
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

      <ProductFormModal
        open={formOpen}
        onOpenChange={setFormOpen}
        product={editTarget}
        suppliers={suppliers}
        onSuccess={() => { setFormOpen(false); load() }}
      />

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(o) => { if (!o) setDeleteTarget(null) }}
        title="Désactiver ce produit ?"
        description={`"${deleteTarget?.name}" sera marqué inactif. L'historique des réceptions est conservé.`}
        onConfirm={confirmDelete}
        loading={deleteLoading}
      />
    </div>
  )
}
