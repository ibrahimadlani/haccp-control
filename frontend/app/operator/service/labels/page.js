"use client"

import { useEffect, useState } from "react"
import { Bluetooth, Loader2, Printer } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { KioskBackButton } from "@/components/kiosk/KioskBackButton"
import { KIOSK_PHASES } from "@/lib/kiosk/phases"
import {
  connectThermalPrinter,
  getSavedPrinter,
  printOpenedProductLabel,
} from "@/lib/kiosk/thermalPrinter"
import { createOpenedProductLabel } from "@/lib/api/production"
import { getProducts } from "@/lib/api/reception"
import { useOperator } from "@/lib/contexts/OperatorContext"
import { loadEstablishmentToken } from "@/lib/session/establishment"
import { cn } from "@/lib/utils"

function addDays(days) {
  const d = new Date()
  d.setDate(d.getDate() + days)
  return d.toISOString().split("T")[0]
}

function formatFr(iso) {
  return new Date(iso).toLocaleDateString("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  })
}

export default function OpenedProductLabelsPage() {
  const { operator } = useOperator()
  const token = loadEstablishmentToken()
  const credentials = operator ? { pin: operator.pin, operatorId: operator.id } : null

  const [products, setProducts] = useState([])
  const [productId, setProductId] = useState("")
  const [printer, setPrinter] = useState(null)
  const [connecting, setConnecting] = useState(false)
  const [printing, setPrinting] = useState(false)

  useEffect(() => {
    setPrinter(getSavedPrinter())
    if (!token) return
    getProducts(token)
      .then((data) => setProducts(data.items ?? []))
      .catch(() => {})
  }, [token])

  const selected = products.find((p) => p.id === productId)
  const productName = selected?.name ?? ""

  async function handleConnect() {
    setConnecting(true)
    try {
      const info = await connectThermalPrinter()
      setPrinter(info)
      toast.success(`Imprimante : ${info.name}`)
    } catch (err) {
      toast.error(String(err.message))
    } finally {
      setConnecting(false)
    }
  }

  async function handlePrint() {
    if (!productName || !token || !credentials) {
      toast.error("Sélectionnez un produit.")
      return
    }
    setPrinting(true)
    const openedAt = new Date()
    const useBy = addDays(3)
    const openedLabel = openedAt.toLocaleString("fr-FR", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    })

    try {
      await createOpenedProductLabel(token, credentials, {
        product_name: productName,
        secondary_use_by: useBy,
        storage_location: "COLD_POSITIVE",
      })

      const result = await printOpenedProductLabel({
        productName,
        openedAt: openedLabel,
        useBy: formatFr(useBy),
      })

      toast.success(
        result.mode === "bluetooth"
          ? `Étiquette imprimée (${result.printer})`
          : "Étiquette envoyée à l'impression",
      )
    } catch (err) {
      toast.error(String(err.message))
    } finally {
      setPrinting(false)
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-lg flex-1 flex-col gap-5">
      <div className="flex items-center justify-between gap-4">
        <KioskBackButton href={KIOSK_PHASES.service.route} />
        <h1 className="text-[1.5rem] font-bold">Ouverture de produit</h1>
      </div>

      <div className="space-y-4 rounded-xl border-2 border-slate-200 bg-white p-5">
        <div className="space-y-2">
          <Label className="text-[1.1rem]">Produit *</Label>
          <select
            className="flex h-12 w-full rounded-lg border px-3 text-[1.1rem]"
            value={productId}
            onChange={(e) => setProductId(e.target.value)}
          >
            <option value="">Sélectionner un produit…</option>
            {products.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-2 rounded-lg border border-slate-100 bg-slate-50 p-4">
          <Label className="text-[1.05rem]">Imprimante thermique</Label>
          <p className="text-[0.95rem] text-slate-600">
            {printer?.name ?? "Aucune imprimante connectée"}
          </p>
          <Button
            type="button"
            variant="outline"
            className="h-12 w-full text-[1.05rem]"
            onClick={handleConnect}
            disabled={connecting}
          >
            {connecting ? (
              <Loader2 className="mr-2 h-5 w-5 animate-spin" />
            ) : (
              <Bluetooth className="mr-2 h-5 w-5" />
            )}
            Connecter l&apos;imprimante Bluetooth
          </Button>
        </div>

        {productName && (
          <div className="rounded-lg border border-dashed border-slate-300 p-4 text-center text-[1rem] text-slate-600">
            <p className="font-bold text-slate-900">{productName}</p>
            <p className="mt-1">DLC secondaire : J+3 ({formatFr(addDays(3))})</p>
          </div>
        )}

        <Button
          className={cn("h-16 w-full text-[1.2rem] font-bold")}
          onClick={handlePrint}
          disabled={printing || !productId}
        >
          {printing ? (
            <Loader2 className="mr-2 h-6 w-6 animate-spin" />
          ) : (
            <Printer className="mr-2 h-6 w-6" />
          )}
          Imprimer l&apos;étiquette d&apos;ouverture
        </Button>
      </div>
    </div>
  )
}
