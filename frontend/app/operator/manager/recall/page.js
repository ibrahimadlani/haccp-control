"use client"

import { useState } from "react"
import { Loader2, Search } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { KioskBackButton } from "@/components/kiosk/KioskBackButton"
import { searchReceptionByLot } from "@/lib/api/reception"
import { loadEstablishmentToken } from "@/lib/session/establishment"

export default function RecallPlanPage() {
  const [lot, setLot] = useState("")
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)

  async function handleSearch(e) {
    e.preventDefault()
    const token = loadEstablishmentToken()
    if (!token || !lot.trim()) return
    setLoading(true)
    try {
      const data = await searchReceptionByLot(token, lot.trim())
      setResults(data)
      if (!data.length) toast.message("Aucun lot trouvé dans l'historique réception")
    } catch (err) {
      toast.error(String(err.message))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-1 flex-col gap-5">
      <div className="flex items-center justify-between">
        <KioskBackButton href="/operator/manager" label="MANAGER" />
        <h1 className="text-[1.5rem] font-extrabold">Plan de rappel</h1>
      </div>

      <form onSubmit={handleSearch} className="space-y-4 rounded-2xl border-2 bg-white p-5">
        <Label htmlFor="lot" className="text-[1.2rem]">
          Numéro de lot
        </Label>
        <div className="flex gap-2">
          <Input
            id="lot"
            value={lot}
            onChange={(e) => setLot(e.target.value)}
            placeholder="ex. VIA24-0610"
            className="h-12 text-[1.15rem]"
            required
          />
          <Button type="submit" className="h-12 px-6 text-[1.1rem]" disabled={loading}>
            {loading ? <Loader2 className="h-5 w-5 animate-spin" /> : <Search className="h-5 w-5" />}
          </Button>
        </div>
      </form>

      {results.length > 0 && (
        <ul className="divide-y rounded-2xl border-2 bg-white">
          {results.map((row) => (
            <li key={row.item_id} className="space-y-1 px-4 py-4">
              <p className="text-[1.2rem] font-bold">{row.product_name ?? "Produit"}</p>
              <p className="text-[1.05rem] text-slate-600">
                Lot {row.lot_number} · DLUO {row.dluo} ·{" "}
                {new Date(row.received_at).toLocaleDateString("fr-FR")}
              </p>
              <p className={`text-[1.05rem] font-semibold ${row.is_compliant ? "text-emerald-700" : "text-red-700"}`}>
                {row.is_compliant ? "Conforme à réception" : "Non-conforme à réception"}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
