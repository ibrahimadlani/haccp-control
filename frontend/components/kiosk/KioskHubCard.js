"use client"

import Link from "next/link"
import { cn } from "@/lib/utils"

export function KioskHubCard({ href, emoji, title, accentClass, ringClass, suggested }) {
  return (
    <Link
      href={href}
      className={cn(
        "group flex min-h-[9rem] flex-1 flex-col items-center justify-center rounded-2xl border-2 bg-white px-4 py-6 text-center shadow-md transition-all active:scale-[0.98] sm:min-h-[10rem]",
        ringClass,
        suggested ? "ring-4" : "ring-2",
        "hover:shadow-xl",
      )}
    >
      <span
        className={cn(
          "mb-3 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br text-3xl shadow-inner sm:h-20 sm:w-20 sm:text-4xl",
          accentClass,
        )}
      >
        {emoji}
      </span>
      <h2 className="text-[1.35rem] font-extrabold leading-snug text-slate-900 sm:text-[1.6rem]">
        {title}
      </h2>
      {suggested && (
        <p className="mt-2 text-[1.05rem] font-medium text-slate-500">Étape suggérée maintenant</p>
      )}
    </Link>
  )
}
