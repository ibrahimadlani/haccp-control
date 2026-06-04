"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"
import { DeviceHeader } from "@/components/layout/DeviceHeader"
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
      <div className="flex min-h-screen flex-col">
        <DeviceHeader />
        <main className="flex-1 p-4 sm:p-6">{children}</main>
      </div>
    </TimeclockProvider>
  )
}
