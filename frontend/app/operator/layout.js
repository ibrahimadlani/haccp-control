"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"
import { KioskFooter } from "@/components/kiosk/KioskFooter"
import { KioskHeader } from "@/components/kiosk/KioskHeader"
import { TimeclockProvider } from "@/lib/contexts/TimeclockContext"
import { useOperator } from "@/lib/contexts/OperatorContext"
import { loadEstablishmentToken } from "@/lib/session/establishment"

export default function OperatorLayout({ children }) {
  const router = useRouter()
  const { operator } = useOperator()

  useEffect(() => {
    if (!loadEstablishmentToken()) {
      router.replace("/login")
      return
    }
    if (!operator) {
      router.replace("/profiles")
    }
  }, [operator, router])

  if (!operator) return null

  return (
    <TimeclockProvider>
      <div className="kiosk-operator flex min-h-screen flex-col bg-slate-100">
        <KioskHeader />
        <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col px-4 pb-28 pt-4 sm:px-6 sm:pt-6">
          {children}
        </main>
        <KioskFooter />
      </div>
    </TimeclockProvider>
  )
}
