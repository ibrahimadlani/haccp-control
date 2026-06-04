"use client"

import { useEffect, useRef, useState } from "react"
import { AlertTriangle, CheckCircle2, Loader2, Upload } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import { getEquipments } from "@/lib/api/equipment"
import { postTemperatureRecord } from "@/lib/api/haccp"
import { acknowledgeNonConformity, postCorrectiveAction } from "@/lib/api/nonconformities"
import { useOperator } from "@/lib/contexts/OperatorContext"
import { loadEstablishmentToken } from "@/lib/session/establishment"

export function TemperatureRecordModal({ open, onOpenChange }) {
  const { operator } = useOperator()
  const token = loadEstablishmentToken()
  const credentials = operator ? { pin: operator.pin, operatorId: operator.id } : null

  const [slide, setSlide] = useState(0)

  // Slide 1
  const [equipments, setEquipments] = useState([])
  const [loadingEq, setLoadingEq] = useState(false)
  const [selectedId, setSelectedId] = useState("")
  const [temperature, setTemperature] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [recordError, setRecordError] = useState(null)

  // Slide 2
  const [pendingNcId, setPendingNcId] = useState(null)
  const [ncContext, setNcContext] = useState(null)
  const [description, setDescription] = useState("")
  const [photo, setPhoto] = useState(null)
  const [ncLoading, setNcLoading] = useState(false)
  const [ncError, setNcError] = useState(null)
  const photoRef = useRef()

  useEffect(() => {
    if (!open || !token || !credentials) return
    setLoadingEq(true)
    getEquipments(token, credentials)
      .then((d) => {
        const items = d?.items ?? d ?? []
        setEquipments(items)
        // Don't pre-select — user must explicitly pick their equipment
        setSelectedId("")
      })
      .catch(() => {})
      .finally(() => setLoadingEq(false))
  }, [open])

  useEffect(() => {
    if (!open) {
      setSlide(0)
      setSelectedId("")
      setTemperature("")
      setRecordError(null)
      setDescription("")
      setPhoto(null)
      setNcError(null)
      setPendingNcId(null)
      setNcContext(null)
    }
  }, [open])

  const selectedEquipment = equipments.find((e) => e.id === selectedId) ?? null

  async function handleRecord() {
    if (!selectedId || !temperature.trim() || !token || !credentials) return
    setSubmitting(true)
    setRecordError(null)
    try {
      const result = await postTemperatureRecord(token, credentials, {
        equipment_id: selectedId,
        measured_value: temperature,
        source: "MANUEL",
      })
      if (result.is_conforme) {
        toast.success("Relevé conforme enregistré ✓")
        onOpenChange(false)
      } else {
        const measured = Number(result.measured_value)
        const max = Number(result.temperature_max_cible)
        const min = Number(result.temperature_min_cible)
        const deviation = (measured > max ? measured - max : min - measured).toFixed(2)
        setPendingNcId(result.nonconformity_id)
        setNcContext({
          equipment: selectedEquipment?.name ?? "—",
          value: result.measured_value,
          min: result.temperature_min_cible,
          max: result.temperature_max_cible,
          deviation,
        })
        setSlide(1)
      }
    } catch (err) {
      setRecordError(String(err.message))
    } finally {
      setSubmitting(false)
    }
  }

  async function handleCorrectiveAction() {
    if (!description.trim()) { setNcError("La description est obligatoire."); return }
    if (!token || !credentials || !pendingNcId) return
    setNcLoading(true)
    setNcError(null)
    try {
      await acknowledgeNonConformity(token, credentials, pendingNcId)
      const formData = new FormData()
      formData.append("description", description)
      if (photo) formData.append("photo", photo)
      await postCorrectiveAction(token, credentials, pendingNcId, formData)
      toast.success("Action corrective enregistrée")
      onOpenChange(false)
    } catch (err) {
      setNcError(String(err.message))
    } finally {
      setNcLoading(false)
    }
  }

  const isBlocked = submitting || ncLoading

  return (
    <Dialog open={open} onOpenChange={isBlocked ? undefined : onOpenChange}>
      <DialogContent className="w-full max-w-lg gap-0 overflow-hidden p-0 sm:max-w-lg">
        <DialogTitle className="sr-only">
          {slide === 0 ? "Relevé de température" : "Action corrective"}
        </DialogTitle>

        {/* Slide track */}
        <div
          className="flex transition-transform duration-300 ease-in-out"
          style={{ transform: `translateX(-${slide * 50}%)`, width: "200%" }}
        >

          {/* ── SLIDE 1 — Formulaire relevé ── */}
          <div className="flex w-1/2 flex-col gap-6 p-6">

            <h2 className="text-xl font-semibold">Relevé de température</h2>

            {/* Equipment selector — native select for reliable display */}
            <div className="space-y-2">
              <Label htmlFor="eq-select" className="text-sm font-medium">
                Équipement
              </Label>
              {loadingEq ? (
                <Skeleton className="h-12 w-full rounded-md" />
              ) : (
                <select
                  id="eq-select"
                  value={selectedId}
                  onChange={(e) => setSelectedId(e.target.value)}
                  disabled={submitting}
                  className="h-12 w-full rounded-md border border-input bg-background px-3 text-sm shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <option value="" disabled>Choisir un équipement…</option>
                  {equipments.map((eq) => (
                    <option key={eq.id} value={eq.id}>
                      {eq.name}
                    </option>
                  ))}
                </select>
              )}
            </div>

            {/* Min / max thresholds */}
            {selectedEquipment ? (
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-lg border bg-muted/40 p-3 text-center">
                  <p className="text-xs uppercase tracking-wider text-muted-foreground">Seuil min</p>
                  <p className="mt-1 text-2xl font-bold tabular-nums">
                    {selectedEquipment.min_target_temperature}°C
                  </p>
                </div>
                <div className="rounded-lg border bg-muted/40 p-3 text-center">
                  <p className="text-xs uppercase tracking-wider text-muted-foreground">Seuil max</p>
                  <p className="mt-1 text-2xl font-bold tabular-nums">
                    {selectedEquipment.max_target_temperature}°C
                  </p>
                </div>
              </div>
            ) : (
              <div className="rounded-lg border border-dashed p-4 text-center text-sm text-muted-foreground">
                Sélectionnez un équipement pour voir les seuils
              </div>
            )}

            {/* Temperature input */}
            <div className="space-y-2">
              <Label htmlFor="temp-input" className="text-sm font-medium">
                Température mesurée (°C)
              </Label>
              <input
                id="temp-input"
                type="number"
                step="0.01"
                inputMode="decimal"
                placeholder="Ex : 3.80"
                value={temperature}
                onChange={(e) => { setTemperature(e.target.value); setRecordError(null) }}
                disabled={submitting || !selectedId}
                className="h-14 w-full rounded-md border border-input bg-background px-4 text-2xl font-semibold tabular-nums shadow-sm transition-colors placeholder:text-muted-foreground/50 focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
              />
              {recordError && <p className="text-sm text-destructive">{recordError}</p>}
            </div>

            {/* Submit */}
            <Button
              size="lg"
              className="w-full"
              onClick={handleRecord}
              disabled={submitting || !selectedId || !temperature.trim()}
            >
              {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Enregistrer le relevé
            </Button>
          </div>

          {/* ── SLIDE 2 — Action corrective ── */}
          <div className="flex w-1/2 flex-col gap-5 p-6">

            {/* Alert header */}
            <div className="flex items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-destructive/10">
                <AlertTriangle className="h-4 w-4 text-destructive" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="font-semibold text-destructive">Relevé hors seuil</p>
                <p className="truncate text-sm text-muted-foreground">{ncContext?.equipment}</p>
              </div>
            </div>

            {/* Measured vs thresholds */}
            {ncContext && (
              <div className="grid grid-cols-3 divide-x overflow-hidden rounded-lg border text-center text-sm">
                <div className="py-3">
                  <p className="text-xs uppercase tracking-wider text-muted-foreground">Mesure</p>
                  <p className="mt-1 text-lg font-bold tabular-nums text-destructive">
                    {ncContext.value}°C
                  </p>
                </div>
                <div className="py-3">
                  <p className="text-xs uppercase tracking-wider text-muted-foreground">Min</p>
                  <p className="mt-1 text-lg font-semibold tabular-nums">{ncContext.min}°C</p>
                </div>
                <div className="py-3">
                  <p className="text-xs uppercase tracking-wider text-muted-foreground">Max</p>
                  <p className="mt-1 text-lg font-semibold tabular-nums">{ncContext.max}°C</p>
                </div>
              </div>
            )}

            {/* Description */}
            <div className="space-y-2">
              <Label htmlFor="nc-desc" className="text-sm font-medium">
                Action corrective réalisée <span className="text-destructive">*</span>
              </Label>
              <Textarea
                id="nc-desc"
                placeholder="Ex : produits isolés et étiquetés, maintenance prévenue, température vérifiée à 14h30…"
                value={description}
                onChange={(e) => { setDescription(e.target.value); setNcError(null) }}
                disabled={ncLoading}
                rows={4}
                className="resize-none"
              />
              {ncError && <p className="text-sm text-destructive">{ncError}</p>}
            </div>

            {/* Photo */}
            <div className="space-y-2">
              <Label className="text-sm font-medium">Photo de preuve (facultative)</Label>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => photoRef.current?.click()}
                  disabled={ncLoading}
                  className="h-9"
                >
                  <Upload className="mr-2 h-3.5 w-3.5" />
                  {photo ? photo.name : "Choisir une image"}
                </Button>
                {photo && (
                  <Button type="button" variant="ghost" size="sm" onClick={() => setPhoto(null)} disabled={ncLoading}>
                    Retirer
                  </Button>
                )}
              </div>
              <input
                ref={photoRef}
                type="file"
                accept="image/jpeg,image/png"
                className="hidden"
                onChange={(e) => setPhoto(e.target.files?.[0] ?? null)}
              />
            </div>

            {/* Submit */}
            <Button
              size="lg"
              className="w-full"
              onClick={handleCorrectiveAction}
              disabled={ncLoading || !description.trim()}
            >
              {ncLoading
                ? <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                : <CheckCircle2 className="mr-2 h-4 w-4" />
              }
              Valider l'action corrective
            </Button>

            {/* Skip */}
            <Button
              variant="ghost"
              className="w-full text-muted-foreground"
              onClick={() => {
                toast.warning("Non-conformité en attente — un manager devra la traiter.")
                onOpenChange(false)
              }}
              disabled={ncLoading}
            >
              Passer pour l'instant
            </Button>
          </div>

        </div>
      </DialogContent>
    </Dialog>
  )
}
