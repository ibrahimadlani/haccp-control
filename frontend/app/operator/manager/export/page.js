"use client"

import { useState } from "react"
import { FileDown, Loader2 } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { KioskBackButton } from "@/components/kiosk/KioskBackButton"

export default function ManagerExportPage() {
  const [from, setFrom] = useState(() => {
    const d = new Date()
    d.setDate(d.getDate() - 7)
    return d.toISOString().split("T")[0]
  })
  const [to, setTo] = useState(() => new Date().toISOString().split("T")[0])
  const [loading, setLoading] = useState(false)

  function handleExport() {
    setLoading(true)
    setTimeout(() => {
      setLoading(false)
      toast.success(`Export DDPP demandé du ${from} au ${to} — génération PDF en cours`)
    }, 1200)
  }

  return (
    <div className="flex flex-1 flex-col gap-5">
      <div className="flex items-center justify-between">
        <KioskBackButton href="/operator/manager" label="MANAGER" />
        <h1 className="text-[1.5rem] font-extrabold">Export DDPP</h1>
      </div>

      <div className="space-y-5 rounded-2xl border-2 bg-white p-5">
        <p className="text-[1.15rem] text-slate-600">
          Génération du registre HACCP officiel sur la période sélectionnée.
        </p>

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="from" className="text-[1.1rem]">Du</Label>
            <Input id="from" type="date" value={from} onChange={(e) => setFrom(e.target.value)} className="h-12 text-[1.1rem]" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="to" className="text-[1.1rem]">Au</Label>
            <Input id="to" type="date" value={to} onChange={(e) => setTo(e.target.value)} className="h-12 text-[1.1rem]" />
          </div>
        </div>

        <Button className="h-14 w-full text-[1.25rem]" onClick={handleExport} disabled={loading}>
          {loading ? (
            <Loader2 className="mr-2 h-5 w-5 animate-spin" />
          ) : (
            <FileDown className="mr-2 h-5 w-5" />
          )}
          Générer le registre PDF
        </Button>
      </div>
    </div>
  )
}
