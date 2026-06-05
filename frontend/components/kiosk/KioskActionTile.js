"use client"

import Link from "next/link"
import { cn } from "@/lib/utils"

export function KioskActionTile({
  emoji,
  title,
  subtitle,
  badge,
  onClick,
  href,
  disabled = false,
  variant = "default",
  className,
}) {
  const content = (
    <>
      <span className="text-4xl leading-none sm:text-5xl" aria-hidden>
        {emoji}
      </span>
      <div className="mt-3 space-y-1">
        <p className="text-[1.25rem] font-extrabold leading-tight sm:text-[1.4rem]">{title}</p>
        {subtitle && (
          <p className="text-[1.05rem] leading-snug text-slate-600">{subtitle}</p>
        )}
      </div>
      {badge && (
        <span className="mt-3 inline-block rounded-full bg-slate-900 px-3 py-1 text-[1rem] font-bold text-white">
          {badge}
        </span>
      )}
    </>
  )

  const baseClass = cn(
    "flex min-h-[8.5rem] flex-col items-center justify-center rounded-2xl border-2 p-4 text-center shadow-sm transition-all sm:min-h-[9.5rem]",
    variant === "danger" && "border-red-300 bg-red-50",
    variant === "success" && "border-emerald-300 bg-emerald-50",
    disabled
      ? "cursor-not-allowed border-slate-200 bg-slate-100 opacity-60"
      : "border-slate-200 bg-white hover:border-slate-400 hover:shadow-md active:scale-[0.98]",
    className,
  )

  if (href && !disabled) {
    return (
      <Link href={href} className={baseClass}>
        {content}
      </Link>
    )
  }

  return (
    <button type="button" className={baseClass} onClick={onClick} disabled={disabled}>
      {content}
    </button>
  )
}
