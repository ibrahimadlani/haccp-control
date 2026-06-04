"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"
import { ShieldAlert, LogOut } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { usePlatform } from "@/lib/contexts/PlatformContext"

export default function PlatformLayout({ children }) {
  const router = useRouter()
  const { platformKey, clearPlatformKey } = usePlatform()

  useEffect(() => {
    if (!platformKey) router.replace("/platform/login")
  }, [platformKey, router])

  if (!platformKey) return null

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b bg-background">
        <div className="flex h-14 items-center gap-3 px-6">
          <ShieldAlert className="h-5 w-5 text-destructive" />
          <span className="font-semibold text-destructive">Administration plateforme</span>
          <Separator orientation="vertical" className="h-5" />
          <span className="text-sm text-muted-foreground">Accès privilégié — session non persistée</span>
          <Button
            variant="ghost"
            size="icon"
            className="ml-auto"
            onClick={() => { clearPlatformKey(); router.replace("/platform/login") }}
          >
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
      </header>
      <main className="flex-1 p-4 sm:p-6">{children}</main>
    </div>
  )
}
