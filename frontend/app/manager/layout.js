"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { LogOut, Thermometer } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { ManagerNav } from "@/components/layout/ManagerNav"
import { useOperator } from "@/lib/contexts/OperatorContext"
import { loadEstablishmentContext, loadEstablishmentToken } from "@/lib/session/establishment"

export default function ManagerLayout({ children }) {
  const router = useRouter()
  const { operator, clearOperator } = useOperator()
  const [siteName, setSiteName] = useState("")

  useEffect(() => {
    const token = loadEstablishmentToken()
    if (!token) {
      router.replace("/login")
      return
    }
    if (operator && !operator.is_admin) {
      router.replace("/operator")
    }
    setSiteName(loadEstablishmentContext()?.nom_site ?? "Établissement")
  }, [operator, router])

  function handleLogout() {
    clearOperator()
    router.replace("/profiles")
  }

  return (
    <div className="flex min-h-screen flex-col">
      {/* Top bar */}
      <header className="border-b bg-background">
        <div className="flex h-14 items-center gap-3 px-4">
          <Thermometer className="h-5 w-5 text-primary" />
          <span className="font-semibold">HACCP</span>
          <Separator orientation="vertical" className="h-5" />
          <span className="text-sm text-muted-foreground">{siteName}</span>
          <span className="ml-2 hidden text-xs text-muted-foreground sm:inline">— Manager</span>
          <Button variant="ghost" size="icon" className="ml-auto" onClick={handleLogout} aria-label="Déconnecter">
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
      </header>

      {/* Body */}
      <div className="flex flex-1">
        <ManagerNav />
        <main className="flex-1 p-4 sm:p-6">{children}</main>
      </div>
    </div>
  )
}
