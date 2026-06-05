"use client"

import Link from "next/link"
import { ArrowLeft } from "lucide-react"

export function OperatorBackLink({ phase = "morning", label = "Ma journée en cuisine" }) {
  return (
    <Link
      href={`/operator?phase=${phase}`}
      className="inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline"
    >
      <ArrowLeft className="h-4 w-4" />
      {label}
    </Link>
  )
}
