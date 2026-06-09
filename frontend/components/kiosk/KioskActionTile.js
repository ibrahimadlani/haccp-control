"use client"

import Link from "next/link"
import { cn } from "@/lib/utils"

export function KioskActionTile({
  icon: Icon,
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
      {Icon ? (
        <Icon className="h-10 w-10 text-slate-700 sm:h-11 sm:w-11" strokeWidth={1.5} aria-hidden />
      ) : emoji ? (
        <span className="text-3xl leading-none sm:text-4xl" aria-hidden>
          {emoji}
        </span>
      ) : null}
      <div className="mt-3 space-y-1">
        <p className="text-[1.2rem] font-bold leading-tight text-slate-900 sm:text-[1.3rem]">{title}</p>
        {subtitle && (
          <p className="text-[1rem] leading-snug text-slate-600">{subtitle}</p>
        )}
      </div>
      {badge && (
        <span className="mt-3 inline-block rounded-full bg-slate-800 px-3 py-1 text-[0.95rem] font-semibold text-white">
          {badge}
        </span>
      )}
    </>
  )

  const baseClass = cn(
    "flex min-h-[8rem] flex-col items-center justify-center rounded-xl border-2 p-4 text-center transition-all sm:min-h-[8.5rem]",
    variant === "danger" && "border-red-300 bg-red-50",
    variant === "success" && "border-emerald-300 bg-emerald-50",
    disabled
      ? "cursor-not-allowed border-slate-200 bg-slate-50 opacity-50"
      : "border-slate-200 bg-white hover:border-slate-400 hover:shadow-sm active:scale-[0.99]",
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
