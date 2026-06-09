"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { ComplianceStatusCard } from "@/components/kiosk/ComplianceStatusCard"
import { KioskBackButton } from "@/components/kiosk/KioskBackButton"
import { listComplianceCategories } from "@/lib/kiosk/complianceTracker"

export default function ManagerDocumentsPage() {
  const router = useRouter()
  const [categories, setCategories] = useState([])

  useEffect(() => {
    setCategories(listComplianceCategories())
  }, [])

  function handleAdd(cat) {
    router.push(`/operator/morning/documents?type=${cat.scanType}&category=${cat.id}`)
  }

  return (
    <div className="flex flex-1 flex-col gap-5">
      <div className="flex items-center justify-between gap-4">
        <KioskBackButton href="/operator/manager" label="MANAGER" />
        <div className="text-right">
          <p className="text-[1.1rem] text-violet-700">📁 Coffre-fort</p>
          <h1 className="text-[1.6rem] font-extrabold text-slate-900">Documents HACCP</h1>
        </div>
      </div>

      <section className="space-y-3">
        <h2 className="text-[1.25rem] font-bold text-slate-800">Conformité HACCP</h2>
        <div className="flex gap-4 overflow-x-auto pb-2">
          {categories.map((cat) => (
            <ComplianceStatusCard
              key={cat.id}
              emoji={cat.emoji}
              title={cat.title}
              lastDate={cat.lastLabel}
              nextDate={cat.nextLabel}
              isLate={cat.isLate}
              borderClass={cat.isLate ? "border-red-400" : "border-emerald-400"}
              onAdd={() => handleAdd(cat)}
            />
          ))}
        </div>
      </section>

      <p className="text-[1.05rem] leading-relaxed text-slate-600">
        Dératisation, analyses labo, audits DDPP et BL — comme sur votre ancienne application,
        adapté à la cantine collective. Scannez depuis la tablette ou le matin.
      </p>
    </div>
  )
}
