"use client"

import { useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import {
  AlertTriangle,
  CheckCircle2,
  Loader2,
  PackageCheck,
  Plus,
  Thermometer,
  X,
} from "lucide-react"
import { toast } from "sonner"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import { Switch } from "@/components/ui/switch"
import {
  addReceptionItem,
  closeReceptionSession,
  createProduct,
  getProducts,
  openReceptionSession,
} from "@/lib/api/reception"
import { createSupplier, getSuppliers } from "@/lib/api/suppliers"
import { useOperator } from "@/lib/contexts/OperatorContext"
import { loadEstablishmentToken } from "@/lib/session/establishment"

// ── helpers ───────────────────────────────────────────────────────────────────

function isTempOutOfRange(temp, product) {
  if (!product?.has_temperature_control) return false
  if (temp === "" || temp === null || temp === undefined) return false
  const t = parseFloat(temp)
  if (isNaN(t)) return false
  return t < product.min_target_temperature || t > product.max_target_temperature
}

const TODAY_ISO = new Date().toISOString().split("T")[0]

/** Round a Date to the nearest 15-minute boundary. */
function roundToNearest15(d) {
  const ms = 15 * 60 * 1000
  return new Date(Math.round(d.getTime() / ms) * ms)
}

/** Default received_at: today + current time rounded to 15 min. */
function defaultReceivedAt() {
  const rounded = roundToNearest15(new Date())
  const pad = (n) => String(n).padStart(2, "0")
  const date = `${rounded.getFullYear()}-${pad(rounded.getMonth() + 1)}-${pad(rounded.getDate())}`
  const time = `${pad(rounded.getHours())}:${pad(rounded.getMinutes())}`
  return { date, time }
}

/** Build all 15-min slots for a day (96 entries). */
function timeSlots() {
  const slots = []
  for (let h = 0; h < 24; h++) {
    for (let m = 0; m < 60; m += 15) {
      const hh = String(h).padStart(2, "0")
      const mm = String(m).padStart(2, "0")
      slots.push(`${hh}:${mm}`)
    }
  }
  return slots
}
const TIME_SLOTS = timeSlots()

// ── DateTimePicker ────────────────────────────────────────────────────────────

function DateTimePicker({ date, time, onDateChange, onTimeChange }) {
  return (
    <div className="grid grid-cols-2 gap-2">
      <div className="space-y-1.5">
        <Label htmlFor="recv-date">Date de réception</Label>
        <Input
          id="recv-date"
          type="date"
          value={date}
          onChange={(e) => onDateChange(e.target.value)}
          required
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="recv-time">Heure</Label>
        <select
          id="recv-time"
          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          value={time}
          onChange={(e) => onTimeChange(e.target.value)}
        >
          {TIME_SLOTS.map((slot) => (
            <option key={slot} value={slot}>{slot}</option>
          ))}
        </select>
      </div>
    </div>
  )
}

// ── Quick-add dialogs ─────────────────────────────────────────────────────────

function AddSupplierDialog({ open, onClose, onCreated }) {
  const [name, setName] = useState("")
  const [country, setCountry] = useState("France")
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    const token = loadEstablishmentToken()
    if (!token || !name.trim()) return
    setLoading(true)
    try {
      const supplier = await createSupplier(token, { name: name.trim(), country })
      toast.success(`Fournisseur "${supplier.name}" ajouté`)
      onCreated(supplier)
      setName("")
      setCountry("France")
    } catch (err) {
      toast.error(String(err.message))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Nouveau fournisseur</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 pt-2">
          <div className="space-y-1.5">
            <Label htmlFor="s-name">Nom *</Label>
            <Input
              id="s-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Boucherie Dupont"
              required
              autoFocus
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="s-country">Pays</Label>
            <select
              id="s-country"
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              value={country}
              onChange={(e) => setCountry(e.target.value)}
            >
              {["France","Belgique","Suisse","Luxembourg","Allemagne","Espagne","Italie","Pays-Bas","Royaume-Uni","Autre"].map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
          <div className="flex gap-2 pt-1">
            <Button type="button" variant="outline" className="flex-1" onClick={onClose} disabled={loading}>
              Annuler
            </Button>
            <Button type="submit" className="flex-1" disabled={!name.trim() || loading}>
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Ajouter
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function AddProductDialog({ open, onClose, onCreated, supplierId }) {
  const [name, setName] = useState("")
  const [reference, setReference] = useState("")
  const [hasTempControl, setHasTempControl] = useState(false)
  const [minTemp, setMinTemp] = useState("")
  const [maxTemp, setMaxTemp] = useState("")
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    const token = loadEstablishmentToken()
    if (!token || !name.trim()) return
    setLoading(true)
    try {
      const payload = {
        name: name.trim(),
        reference: reference.trim() || null,
        supplier_id: supplierId ?? null,
        has_temperature_control: hasTempControl,
        min_target_temperature: hasTempControl ? parseFloat(minTemp) : null,
        max_target_temperature: hasTempControl ? parseFloat(maxTemp) : null,
      }
      const product = await createProduct(token, payload)
      toast.success(`Produit "${product.name}" ajouté`)
      onCreated(product)
      setName(""); setReference(""); setHasTempControl(false); setMinTemp(""); setMaxTemp("")
    } catch (err) {
      toast.error(String(err.message))
    } finally {
      setLoading(false)
    }
  }

  const tempValid = !hasTempControl || (
    minTemp !== "" && maxTemp !== "" && parseFloat(minTemp) < parseFloat(maxTemp)
  )

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Nouveau produit</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 pt-2">
          <div className="space-y-1.5">
            <Label htmlFor="p-name">Nom *</Label>
            <Input
              id="p-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Escalope de veau"
              required
              autoFocus
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="p-ref">Référence</Label>
            <Input
              id="p-ref"
              value={reference}
              onChange={(e) => setReference(e.target.value)}
              placeholder="REF-001"
            />
          </div>
          <div className="flex items-center justify-between gap-3">
            <div>
              <Label className="text-sm font-medium">Contrôle de température</Label>
              <p className="text-xs text-muted-foreground">Activer si produit réfrigéré / surgelé</p>
            </div>
            <Switch checked={hasTempControl} onCheckedChange={setHasTempControl} />
          </div>
          {hasTempControl && (
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="p-min">Temp. min (°C) *</Label>
                <Input
                  id="p-min"
                  type="number"
                  step="0.5"
                  value={minTemp}
                  onChange={(e) => setMinTemp(e.target.value)}
                  placeholder="0"
                  required
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="p-max">Temp. max (°C) *</Label>
                <Input
                  id="p-max"
                  type="number"
                  step="0.5"
                  value={maxTemp}
                  onChange={(e) => setMaxTemp(e.target.value)}
                  placeholder="4"
                  required
                />
              </div>
            </div>
          )}
          <div className="flex gap-2 pt-1">
            <Button type="button" variant="outline" className="flex-1" onClick={onClose} disabled={loading}>
              Annuler
            </Button>
            <Button type="submit" className="flex-1" disabled={!name.trim() || !tempValid || loading}>
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Ajouter
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ── Part 1 — Session opener ───────────────────────────────────────────────────

function SessionOpener({ onSessionOpened }) {
  const { operator } = useOperator()
  const [suppliers, setSuppliers] = useState([])
  const [supplierId, setSupplierId] = useState("")
  const { date: defaultDate, time: defaultTime } = defaultReceivedAt()
  const [recvDate, setRecvDate] = useState(defaultDate)
  const [recvTime, setRecvTime] = useState(defaultTime)
  const [blPhoto, setBlPhoto] = useState(null)
  const [loading, setLoading] = useState(false)
  const [addSupplierOpen, setAddSupplierOpen] = useState(false)
  const fileRef = useRef(null)

  useEffect(() => {
    const token = loadEstablishmentToken()
    if (!token) return
    getSuppliers(token).then((data) => setSuppliers(data.items ?? [])).catch(() => {})
  }, [])

  function handleSupplierCreated(supplier) {
    setSuppliers((prev) => [...prev, supplier].sort((a, b) => a.name.localeCompare(b.name)))
    setSupplierId(supplier.id)
    setAddSupplierOpen(false)
  }

  async function handleStart(e) {
    e.preventDefault()
    if (!supplierId) return
    const token = loadEstablishmentToken()
    if (!token || !operator) return
    setLoading(true)
    try {
      const receivedAt = `${recvDate}T${recvTime}:00`
      const session = await openReceptionSession(
        token,
        { pin: operator.pin, operatorId: operator.id },
        { supplierId, receivedAt, blPhoto },
      )
      onSessionOpened(session)
    } catch (err) {
      toast.error(String(err.message))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto max-w-sm space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Nouvelle réception</h1>
        <p className="text-sm text-muted-foreground">Sélectionnez le fournisseur pour démarrer</p>
      </div>

      <Card>
        <CardContent className="pt-6">
          <form onSubmit={handleStart} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="supplier">Fournisseur</Label>
              <div className="flex gap-2">
                <select
                  id="supplier"
                  className="flex h-10 min-w-0 flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  value={supplierId}
                  onChange={(e) => setSupplierId(e.target.value)}
                  required
                >
                  <option value="">Choisir…</option>
                  {suppliers.map((s) => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  className="shrink-0"
                  onClick={() => setAddSupplierOpen(true)}
                  title="Ajouter un fournisseur"
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
            </div>

            <DateTimePicker
              date={recvDate}
              time={recvTime}
              onDateChange={setRecvDate}
              onTimeChange={setRecvTime}
            />

            <div className="space-y-1.5">
              <Label>Photo du BL (optionnel)</Label>
              <div className="flex items-center gap-2">
                <Button type="button" variant="outline" size="sm" onClick={() => fileRef.current?.click()}>
                  {blPhoto ? blPhoto.name : "Choisir un fichier"}
                </Button>
                {blPhoto && (
                  <button type="button" className="text-muted-foreground hover:text-foreground" onClick={() => setBlPhoto(null)}>
                    <X className="h-4 w-4" />
                  </button>
                )}
              </div>
              <input ref={fileRef} type="file" accept="image/jpeg,image/png" className="hidden"
                onChange={(e) => setBlPhoto(e.target.files?.[0] ?? null)} />
            </div>

            <Button type="submit" className="w-full" disabled={!supplierId || loading}>
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Démarrer la réception
            </Button>
          </form>
        </CardContent>
      </Card>

      <AddSupplierDialog
        open={addSupplierOpen}
        onClose={() => setAddSupplierOpen(false)}
        onCreated={handleSupplierCreated}
      />
    </div>
  )
}

// ── Part 2 — Scan & Go ────────────────────────────────────────────────────────

function ScanAndGo({ session }) {
  const router = useRouter()
  const { operator } = useOperator()

  const [products, setProducts] = useState([])
  const [items, setItems] = useState([])
  const [closing, setClosing] = useState(false)
  const [addProductOpen, setAddProductOpen] = useState(false)

  // Form state
  const [productId, setProductId] = useState("")
  const [lot, setLot] = useState("")
  const [dluo, setDluo] = useState("")
  const [temp, setTemp] = useState("")
  const [submitting, setSubmitting] = useState(false)

  const selectedProduct = products.find((p) => p.id === productId) ?? null
  const outOfRange = isTempOutOfRange(temp, selectedProduct)

  useEffect(() => {
    const token = loadEstablishmentToken()
    if (!token) return
    getProducts(token, { supplierId: session.supplier_id })
      .then((data) => setProducts(data.items ?? []))
      .catch(() => {})
  }, [session.supplier_id])

  function handleProductCreated(product) {
    setProducts((prev) => [...prev, product].sort((a, b) => a.name.localeCompare(b.name)))
    setProductId(product.id)
    setAddProductOpen(false)
  }

  function resetForm() {
    setProductId(""); setLot(""); setDluo(""); setTemp("")
  }

  async function handleAddItem(e) {
    e.preventDefault()
    if (!selectedProduct || !lot || !dluo) return
    const token = loadEstablishmentToken()
    if (!token || !operator) return

    const isCompliant = !outOfRange
    const payload = {
      product_id: productId,
      lot_number: lot,
      dluo,
      measured_temperature:
        selectedProduct.has_temperature_control && temp !== "" ? parseFloat(temp) : null,
      is_compliant: isCompliant,
      ...(selectedProduct.has_temperature_control && {
        product_min_temp: selectedProduct.min_target_temperature,
        product_max_temp: selectedProduct.max_target_temperature,
      }),
    }

    setSubmitting(true)
    try {
      const item = await addReceptionItem(
        token,
        { pin: operator.pin, operatorId: operator.id },
        session.id,
        payload,
      )
      setItems((prev) => [...prev, { ...item, product_name: selectedProduct.name }])
      resetForm()
      if (!isCompliant) toast.warning("Non-conformité créée pour cet article.")
      else toast.success("Article ajouté")
    } catch (err) {
      toast.error(String(err.message))
    } finally {
      setSubmitting(false)
    }
  }

  async function handleClose() {
    const token = loadEstablishmentToken()
    if (!token || !operator) return
    setClosing(true)
    try {
      await closeReceptionSession(token, { pin: operator.pin, operatorId: operator.id }, session.id)
      toast.success("Réception clôturée")
      router.replace("/operator")
    } catch (err) {
      toast.error(String(err.message))
      setClosing(false)
    }
  }

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Scan & Go</h1>
          <p className="text-sm text-muted-foreground">
            {session.received_at
              ? new Date(session.received_at).toLocaleString("fr-FR", {
                  day: "2-digit", month: "short", year: "numeric",
                  hour: "2-digit", minute: "2-digit",
                })
              : "—"}{" "}
            · {items.length} article{items.length !== 1 ? "s" : ""}
          </p>
        </div>
        <Badge variant="outline" className="gap-1.5">
          <span className="h-2 w-2 rounded-full bg-green-500" />
          En cours
        </Badge>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">Ajouter un produit</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleAddItem} className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="product">Produit</Label>
              <div className="flex gap-2">
                <select
                  id="product"
                  className="flex h-10 min-w-0 flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  value={productId}
                  onChange={(e) => { setProductId(e.target.value); setTemp("") }}
                  required
                >
                  <option value="">Choisir…</option>
                  {products.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}{p.reference ? ` — ${p.reference}` : ""}
                    </option>
                  ))}
                </select>
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  className="shrink-0"
                  onClick={() => setAddProductOpen(true)}
                  title="Ajouter un produit"
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="lot">N° de lot</Label>
                <Input id="lot" value={lot} onChange={(e) => setLot(e.target.value)} placeholder="LOT-123" required />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="dluo">DLUO</Label>
                <Input id="dluo" type="date" value={dluo} min={TODAY_ISO}
                  onChange={(e) => setDluo(e.target.value)} required />
              </div>
            </div>

            {selectedProduct?.has_temperature_control && (
              <div className="space-y-1.5">
                <Label htmlFor="temp" className="flex items-center gap-1.5">
                  <Thermometer className="h-3.5 w-3.5" />
                  Température mesurée (°C)
                  <span className="text-xs text-muted-foreground">
                    [{selectedProduct.min_target_temperature} → {selectedProduct.max_target_temperature}]
                  </span>
                </Label>
                <Input
                  id="temp"
                  type="number"
                  step="0.1"
                  value={temp}
                  onChange={(e) => setTemp(e.target.value)}
                  placeholder="ex. 4.2"
                  className={outOfRange ? "border-destructive focus-visible:ring-destructive" : ""}
                  required
                />
                {outOfRange && (
                  <Alert variant="destructive" className="py-2">
                    <AlertTriangle className="h-4 w-4" />
                    <AlertDescription className="text-xs">
                      Température hors normes — une non-conformité sera créée automatiquement.
                    </AlertDescription>
                  </Alert>
                )}
              </div>
            )}

            <Button
              type="submit"
              variant={outOfRange ? "destructive" : "default"}
              className="w-full"
              disabled={submitting}
            >
              {submitting ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <PackageCheck className="mr-2 h-4 w-4" />
              )}
              {outOfRange ? "Ajouter (non-conforme)" : "Ajouter l'article"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {items.length > 0 && (
        <Card>
          <CardContent className="pt-4">
            <ul className="divide-y">
              {items.map((item, idx) => (
                <li key={item.id ?? idx} className="flex items-center gap-3 py-2.5">
                  {item.is_compliant ? (
                    <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500" />
                  ) : (
                    <AlertTriangle className="h-4 w-4 shrink-0 text-destructive" />
                  )}
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{item.product_name}</p>
                    <p className="text-xs text-muted-foreground">
                      Lot {item.lot_number} · {item.dluo}
                      {item.measured_temperature !== null && ` · ${item.measured_temperature}°C`}
                    </p>
                  </div>
                  {!item.is_compliant && (
                    <Badge variant="destructive" className="shrink-0 text-xs">NC</Badge>
                  )}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <Separator />

      <Button className="w-full" size="lg" onClick={handleClose} disabled={closing || items.length === 0}>
        {closing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-5 w-5" />}
        Terminer la livraison
      </Button>

      <AddProductDialog
        open={addProductOpen}
        onClose={() => setAddProductOpen(false)}
        onCreated={handleProductCreated}
        supplierId={session.supplier_id}
      />
    </div>
  )
}

// ── Page root ─────────────────────────────────────────────────────────────────

export default function ReceptionPage() {
  const [session, setSession] = useState(null)
  return session
    ? <ScanAndGo session={session} />
    : <SessionOpener onSessionOpened={setSession} />
}
