"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Loader2, Thermometer } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { getEstablishmentMeta } from "@/lib/api/auth"
import { saveEstablishmentId } from "@/lib/session/establishment"

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export default function SetupPage() {
  const router = useRouter()
  const [id, setId] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [preview, setPreview] = useState(null)

  async function handleValidate(e) {
    e.preventDefault()
    const trimmed = id.trim()
    if (!UUID_RE.test(trimmed)) {
      setError("Identifiant invalide — format UUID attendu.")
      return
    }
    setLoading(true)
    setError(null)
    try {
      const data = await getEstablishmentMeta(trimmed)
      setPreview(data)
    } catch {
      setError("Établissement introuvable. Vérifiez l'identifiant.")
    } finally {
      setLoading(false)
    }
  }

  function handleConfirm() {
    saveEstablishmentId(id.trim())
    router.push("/login")
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/40 p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
            <Thermometer className="h-6 w-6 text-primary" />
          </div>
          <CardTitle>Configuration tablette</CardTitle>
          <CardDescription>
            Saisissez l'identifiant de l'établissement pour configurer cet appareil.
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-4">
          <form onSubmit={handleValidate} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="establishment-id">Identifiant établissement</Label>
              <Input
                id="establishment-id"
                placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                value={id}
                onChange={(e) => {
                  setId(e.target.value)
                  setPreview(null)
                  setError(null)
                }}
                disabled={loading}
                className="font-mono text-sm"
              />
            </div>

            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {preview ? (
              <div className="rounded-lg border bg-accent/50 p-4">
                <p className="text-sm text-muted-foreground">Établissement trouvé</p>
                <p className="mt-1 font-semibold">{preview.nom_site}</p>
                <p className="text-sm text-muted-foreground">{preview.timezone}</p>
              </div>
            ) : (
              <Button type="submit" className="w-full" disabled={loading || !id.trim()}>
                {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Valider
              </Button>
            )}
          </form>

          {preview && (
            <Button className="w-full" onClick={handleConfirm}>
              Configurer cet appareil
            </Button>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
