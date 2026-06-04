"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { Loader2, Thermometer } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { postEstablishmentSession, getEstablishmentMeta } from "@/lib/api/auth"
import {
  loadEstablishmentId,
  loadEstablishmentToken,
  saveEstablishmentSession,
} from "@/lib/session/establishment"

export default function LoginPage() {
  const router = useRouter()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [siteName, setSiteName] = useState("")

  useEffect(() => {
    if (loadEstablishmentToken()) {
      router.replace("/profiles")
      return
    }
    const id = loadEstablishmentId()
    if (!id) {
      router.replace("/setup")
      return
    }
    getEstablishmentMeta(id)
      .then((d) => setSiteName(d.nom_site ?? ""))
      .catch(() => {})
  }, [router])

  async function handleSubmit(e) {
    e.preventDefault()
    const etablissement_id = loadEstablishmentId()
    if (!etablissement_id) {
      router.replace("/setup")
      return
    }
    setLoading(true)
    setError(null)
    try {
      const data = await postEstablishmentSession({ email, password, etablissement_id })
      saveEstablishmentSession({
        token: data.access_token,
        establishment: data.establishment,
      })
      router.replace("/profiles")
    } catch (err) {
      setError(err.status === 401 ? "Identifiants incorrects." : String(err.message))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/40 p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
            <Thermometer className="h-6 w-6 text-primary" />
          </div>
          <CardTitle>Connexion manager</CardTitle>
          <CardDescription>
            {siteName ? `Établissement : ${siteName}` : "Authentification requise"}
          </CardDescription>
        </CardHeader>

        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                placeholder="manager@restaurant.fr"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={loading}
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Mot de passe</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={loading}
                required
              />
            </div>

            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <Button type="submit" className="w-full" disabled={loading}>
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Se connecter
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
