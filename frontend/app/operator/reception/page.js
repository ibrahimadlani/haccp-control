"use client"

import { useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { Camera, Check, Loader2, Plus, Thermometer } from "lucide-react"
import { toast } from "sonner"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { KioskBackButton } from "@/components/kiosk/KioskBackButton"
import { KIOSK_PHASES } from "@/lib/kiosk/phases"
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
import { cn } from "@/lib/utils"

const COMPLIANCE_CHECKS = [
  {
    key: "tempOk",
    label: "Température conforme",
    hint: "Température entre -18 °C et +7 °C",
  },
  {
    key: "packagingOk",
    label: "Emballage conforme",
    hint: "Emballage intact, non ouvert, non mouillé",
  },
  {
    key: "labelOk",
    label: "Étiquette présente",
    hint: "Étiquette lisible et complète",
  },
  {
    key: "dluoOk",
    label: "DLUO vérifiée",
    hint: "Date limite d'utilisation optimale vérifiée",
  },
]

function isGlobalTempOk(value) {
  if (value === "" || value == null) return false
  const t = parseFloat(value)
  if (Number.isNaN(t)) return false
  return t >= -18 && t <= 7
}

function ComplianceCheckRow({ item, checked, onChange }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className={cn(
        "flex w-full items-start gap-3 rounded-xl border-2 px-4 py-3 text-left transition-colors",
        checked ? "border-emerald-500 bg-emerald-50" : "border-slate-200 bg-white",
      )}
    >
      <span
        className={cn(
          "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded border-2",
          checked ? "border-emerald-600 bg-emerald-600 text-white" : "border-slate-300 bg-white",
        )}
      >
        {checked && <Check className="h-4 w-4" />}
      </span>
      <span>
        <span className="block text-[1.15rem] font-semibold text-slate-900">{item.label}</span>
        <span className="mt-0.5 block text-[1rem] text-slate-500">{item.hint}</span>
      </span>
    </button>
  )
}

export default function ReceptionPage() {
  const router = useRouter()
  const { operator } = useOperator()
  const fileRef = useRef(null)

  const [suppliers, setSuppliers] = useState([])
  const [products, setProducts] = useState([])
  const [supplierId, setSupplierId] = useState("")
  const [productId, setProductId] = useState("")
  const [lot, setLot] = useState("")
  const [dluo, setDluo] = useState("")
  const [temp, setTemp] = useState("")
  const [blPhoto, setBlPhoto] = useState(null)
  const [checks, setChecks] = useState({
    tempOk: false,
    packagingOk: false,
    labelOk: false,
    dluoOk: false,
  })
  const [submitting, setSubmitting] = useState(false)
  const [reserveDialogOpen, setReserveDialogOpen] = useState(false)

  const allChecksDone = Object.values(checks).every(Boolean)

  useEffect(() => {
    const token = loadEstablishmentToken()
    if (!token) return
    getSuppliers(token)
      .then((data) => setSuppliers(data.items ?? []))
      .catch(() => {})
  }, [])

  useEffect(() => {
    const token = loadEstablishmentToken()
    if (!token || !supplierId) {
      setProducts([])
      setProductId("")
      return
    }
    getProducts(token, { supplierId })
      .then((data) => setProducts(data.items ?? []))
      .catch(() => {})
  }, [supplierId])

  function updateCheck(key, value) {
    setChecks((prev) => ({ ...prev, [key]: value }))
  }

  function validateRequired() {
    if (!supplierId) {
      toast.error("Sélectionnez un fournisseur.")
      return false
    }
    if (!productId) {
      toast.error("Sélectionnez un produit.")
      return false
    }
    if (!temp.trim()) {
      toast.error("Saisissez la température de réception.")
      return false
    }
    return true
  }

  function handleConfirmClick() {
    if (!validateRequired()) return
    if (!allChecksDone) {
      setReserveDialogOpen(true)
      return
    }
    submitReception({ withReserve: false })
  }

  async function submitReception({ withReserve }) {
    const token = loadEstablishmentToken()
    if (!token || !operator) return

    const isCompliant = !withReserve && allChecksDone && isGlobalTempOk(temp)

    setSubmitting(true)
    try {
      const receivedAt = new Date().toISOString()
      const session = await openReceptionSession(
        token,
        { pin: operator.pin, operatorId: operator.id },
        {
          supplierId,
          receivedAt,
          blPhoto,
          truckConditionOk: withReserve ? false : checks.tempOk,
          packagingIntegrityOk: withReserve ? false : checks.packagingOk,
          cannedGoodsInspectedOk: withReserve ? false : checks.labelOk,
        },
      )

      const today = new Date().toISOString().split("T")[0]
      await addReceptionItem(
        token,
        { pin: operator.pin, operatorId: operator.id },
        session.id,
        {
          product_id: productId,
          lot_number: lot.trim() || "SANS_LOT",
          dluo: dluo || today,
          measured_temperature: parseFloat(temp),
          is_compliant: isCompliant,
        },
      )

      await closeReceptionSession(token, { pin: operator.pin, operatorId: operator.id }, session.id)

      if (withReserve || !isCompliant) {
        toast.warning("Réception enregistrée avec réserve — non-conformité créée.")
      } else {
        toast.success("Réception enregistrée.")
      }
      router.replace(KIOSK_PHASES.morning.route)
    } catch (err) {
      toast.error(String(err.message))
    } finally {
      setSubmitting(false)
      setReserveDialogOpen(false)
    }
  }

  async function quickAddSupplier() {
    const name = window.prompt("Nom du fournisseur")
    if (!name?.trim()) return
    const token = loadEstablishmentToken()
    if (!token) return
    try {
      const supplier = await createSupplier(token, { name: name.trim(), country: "France" })
      setSuppliers((prev) => [...prev, supplier].sort((a, b) => a.name.localeCompare(b.name)))
      setSupplierId(supplier.id)
      toast.success("Fournisseur ajouté")
    } catch (err) {
      toast.error(String(err.message))
    }
  }

  async function quickAddProduct() {
    const name = window.prompt("Nom du produit")
    if (!name?.trim() || !supplierId) return
    const token = loadEstablishmentToken()
    if (!token) return
    try {
      const product = await createProduct(token, {
        name: name.trim(),
        supplier_id: supplierId,
        has_temperature_control: true,
        min_target_temperature: -18,
        max_target_temperature: 7,
      })
      setProducts((prev) => [...prev, product].sort((a, b) => a.name.localeCompare(b.name)))
      setProductId(product.id)
      toast.success("Produit ajouté")
    } catch (err) {
      toast.error(String(err.message))
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-xl flex-1 flex-col gap-5">
      <div className="flex items-center justify-between gap-4">
        <KioskBackButton href={KIOSK_PHASES.morning.route} />
        <h1 className="text-[1.5rem] font-bold text-slate-900">Nouvelle réception</h1>
      </div>

      <div className="space-y-4 rounded-xl border-2 border-slate-200 bg-white p-5">
        <div className="space-y-2">
          <Label className="text-[1.1rem]">
            Fournisseur <span className="text-red-600">*</span>
          </Label>
          <div className="flex gap-2">
            <select
              className="flex h-12 min-w-0 flex-1 rounded-lg border border-input bg-background px-3 text-[1.1rem]"
              value={supplierId}
              onChange={(e) => setSupplierId(e.target.value)}
            >
              <option value="">Sélectionner…</option>
              {suppliers.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
            <Button type="button" variant="outline" size="icon" className="h-12 w-12 shrink-0" onClick={quickAddSupplier}>
              <Plus className="h-5 w-5" />
            </Button>
          </div>
        </div>

        <div className="space-y-2">
          <Label className="text-[1.1rem]">
            Produit <span className="text-red-600">*</span>
          </Label>
          <div className="flex gap-2">
            <select
              className="flex h-12 min-w-0 flex-1 rounded-lg border border-input bg-background px-3 text-[1.1rem]"
              value={productId}
              onChange={(e) => setProductId(e.target.value)}
              disabled={!supplierId}
            >
              <option value="">Sélectionner…</option>
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            <Button
              type="button"
              variant="outline"
              size="icon"
              className="h-12 w-12 shrink-0"
              onClick={quickAddProduct}
              disabled={!supplierId}
            >
              <Plus className="h-5 w-5" />
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-2">
            <Label className="text-[1.1rem]">N° de lot</Label>
            <Input
              className="h-12 text-[1.1rem]"
              value={lot}
              onChange={(e) => setLot(e.target.value)}
              placeholder="Optionnel"
            />
          </div>
          <div className="space-y-2">
            <Label className="text-[1.1rem]">DLUO</Label>
            <Input
              type="date"
              className="h-12 text-[1.1rem]"
              value={dluo}
              onChange={(e) => setDluo(e.target.value)}
            />
          </div>
        </div>

        <div className="space-y-2">
          <Label className="flex items-center gap-2 text-[1.1rem]">
            <Thermometer className="h-5 w-5" />
            Température (°C) <span className="text-red-600">*</span>
          </Label>
          <Input
            type="number"
            step="0.1"
            className="h-12 text-[1.25rem] font-semibold tabular-nums"
            value={temp}
            onChange={(e) => setTemp(e.target.value)}
            placeholder="ex. 3.5"
          />
        </div>

        <div className="space-y-2">
          <Label className="text-[1.1rem]">Bon de livraison</Label>
          <Button
            type="button"
            variant="outline"
            className="h-14 w-full text-[1.1rem]"
            onClick={() => fileRef.current?.click()}
          >
            <Camera className="mr-2 h-5 w-5" />
            {blPhoto ? blPhoto.name : "Photographier le bon de livraison"}
          </Button>
          <input
            ref={fileRef}
            type="file"
            accept="image/jpeg,image/png"
            capture="environment"
            className="hidden"
            onChange={(e) => setBlPhoto(e.target.files?.[0] ?? null)}
          />
        </div>

        <div className="space-y-2 border-t border-slate-100 pt-4">
          <p className="text-[1.15rem] font-bold text-slate-900">Check-list de conformité</p>
          <div className="space-y-2">
            {COMPLIANCE_CHECKS.map((item) => (
              <ComplianceCheckRow
                key={item.key}
                item={item}
                checked={checks[item.key]}
                onChange={(v) => updateCheck(item.key, v)}
              />
            ))}
          </div>
        </div>

        <Button
          className="h-14 w-full text-[1.2rem] font-semibold"
          onClick={handleConfirmClick}
          disabled={submitting}
        >
          {submitting && <Loader2 className="mr-2 h-5 w-5 animate-spin" />}
          Enregistrer la réception
        </Button>
      </div>

      <AlertDialog open={reserveDialogOpen} onOpenChange={setReserveDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="text-[1.25rem]">Check-list incomplète</AlertDialogTitle>
            <AlertDialogDescription className="text-[1.05rem] leading-relaxed">
              Tous les points de conformité ne sont pas validés. Que souhaitez-vous faire ?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="flex-col gap-2 sm:flex-col">
            <AlertDialogCancel
              className="h-12 w-full text-[1.1rem]"
              onClick={() => toast.info("Réception refusée — aucun enregistrement.")}
            >
              Refuser la réception
            </AlertDialogCancel>
            <AlertDialogAction
              className="h-12 w-full bg-amber-600 text-[1.1rem] hover:bg-amber-700"
              onClick={() => submitReception({ withReserve: true })}
            >
              Accepter avec réserve
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
