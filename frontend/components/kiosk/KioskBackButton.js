"use client"

import Link from "next/link"
import { HUB_ROUTE } from "@/lib/kiosk/phases"

export function KioskBackButton({ href = HUB_ROUTE, label = "RETOUR" }) {
  return (
    <Link
      href={href}
      className="inline-flex min-h-[3.5rem] items-center gap-2 rounded-xl border-2 border-slate-300 bg-white px-5 text-[1.35rem] font-extrabold uppercase tracking-wide text-slate-800 shadow-sm transition-colors hover:border-slate-400 hover:bg-slate-50 active:scale-[0.98]"
    >
      <span aria-hidden>⬅️</span>
      {label}
    </Link>
  )
}
