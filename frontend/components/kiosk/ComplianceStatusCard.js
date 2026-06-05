"use client"

import { Upload } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export function ComplianceStatusCard({
  emoji,
  title,
  lastDate,
  nextDate,
  isLate,
  onAdd,
  borderClass,
}) {
  return (
    <div
      className={cn(
        "flex min-w-[16rem] flex-1 flex-col rounded-2xl border-2 bg-white p-4 shadow-sm",
        borderClass,
      )}
    >
      <div className="mb-3 flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-2xl" aria-hidden>
            {emoji}
          </span>
          <h3 className="text-[1.1rem] font-bold leading-tight text-slate-900">{title}</h3>
        </div>
        <span
          className={cn(
            "shrink-0 rounded-full px-2.5 py-1 text-[0.85rem] font-bold",
            isLate ? "bg-red-100 text-red-800" : "bg-emerald-100 text-emerald-800",
          )}
        >
          {isLate ? "En retard" : "À jour"}
        </span>
      </div>
      <p className="text-[1rem] text-slate-600">
        Dernier : <span className="font-semibold">{lastDate}</span>
      </p>
      <p className="mt-1 text-[1rem] text-slate-600">
        Prochain : <span className="font-semibold">{nextDate}</span>
      </p>
      <Button
        type="button"
        variant="outline"
        className="mt-4 h-11 w-full text-[1.05rem] font-semibold"
        onClick={onAdd}
      >
        <Upload className="mr-2 h-4 w-4" />
        Ajouter
      </Button>
    </div>
  )
}
