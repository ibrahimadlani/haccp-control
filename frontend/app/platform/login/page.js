"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { ShieldAlert } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { usePlatform } from "@/lib/contexts/PlatformContext"

export default function PlatformLoginPage() {
  const router = useRouter()
  const { setPlatformKey } = usePlatform()
  const [key, setKey] = useState("")
  const [error, setError] = useState(null)

  function handleSubmit(e) {
    e.preventDefault()
    if (key.trim().length < 32) {
      setError("La clé doit contenir au moins 32 caractères.")
      return
    }
    setPlatformKey(key.trim())
    router.replace("/platform/organisations")
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/40 p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-full bg-destructive/10">
            <ShieldAlert className="h-6 w-6 text-destructive" />
          </div>
          <CardTitle>Administration plateforme</CardTitle>
          <CardDescription>
            Accès réservé. La clé n'est jamais stockée sur cet appareil.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="platform-key">Clé d'administration</Label>
              <Input
                id="platform-key"
                type="password"
                placeholder="••••••••••••••••••••••••••••••••"
                value={key}
                onChange={(e) => { setKey(e.target.value); setError(null) }}
                autoComplete="off"
                required
              />
            </div>
            {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
            <Button type="submit" className="w-full">Accéder</Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
