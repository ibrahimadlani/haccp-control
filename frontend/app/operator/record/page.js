"use client"

import { useCallback, useEffect, useReducer, useState } from "react"
import { AlertTriangle, CheckCircle2, Loader2, Thermometer, WifiOff } from "lucide-react"
import { toast } from "sonner"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { getEquipments } from "@/lib/api/equipment"
import { postTemperatureRecordsBulk } from "@/lib/api/haccp"
import { useOperator } from "@/lib/contexts/OperatorContext"
import { loadEstablishmentToken } from "@/lib/session/establishment"
import {
  buildFlushPayload,
  clearQueue,
  enqueueTemperatureRecord,
  loadQueue,
  queueSize,
} from "@/lib/offline/temperature-queue"

const EQUIPMENT_TYPE_LABELS = {
  CHAMBRE_FROIDE_POSITIVE: "Chambre froide positive",
  CHAMBRE_FROIDE_NEGATIVE: "Chambre froide négative",
  REFRIGERATEUR_VIANDE: "Réfrigérateur viande",
  REFRIGERATEUR_POISSON: "Réfrigérateur poisson",
  VITRINE_REFRIGEREE: "Vitrine réfrigérée",
  VITRINE_CHAUFFANTE: "Vitrine chauffante",
  CELLULE_REFROIDISSEMENT: "Cellule de refroidissement",
  CHAUFFE_ASSIETTE_FOUR: "Chauffe-assiette / four",
  CONGELATEUR_CONSERVATEUR: "Congélateur conservateur",
  AUTRE: "Autre équipement",
}

// ── Reducer ───────────────────────────────────────────────────────────────────
// values: { [equipment_id]: string }

function valuesReducer(state, action) {
  switch (action.type) {
    case "SET":
      return { ...state, [action.id]: action.value }
    case "RESET":
      return {}
    default:
      return state
  }
}

// ── EquipmentCard ─────────────────────────────────────────────────────────────

function EquipmentCard({ equipment, value, onChange, disabled }) {
  const { min_target_temperature, max_target_temperature } = equipment
  const parsed = parseFloat(value)
  const inRange =
    value !== "" &&
    !isNaN(parsed) &&
    parsed >= parseFloat(min_target_temperature) &&
    parsed <= parseFloat(max_target_temperature)
  const outOfRange = value !== "" && !isNaN(parsed) && !inRange

  return (
    <Card className={outOfRange ? "border-destructive/60" : ""}>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <div>
            <CardTitle className="text-base">{equipment.name}</CardTitle>
            <p className="text-xs text-muted-foreground mt-0.5">
              {EQUIPMENT_TYPE_LABELS[equipment.equipment_type] ?? equipment.equipment_type}
            </p>
          </div>
          <Badge variant="outline" className="shrink-0 text-xs tabular-nums">
            {min_target_temperature}°C → {max_target_temperature}°C
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="flex items-center gap-3">
          <Label htmlFor={`temp-${equipment.id}`} className="sr-only">
            Température relevée
          </Label>
          <div className="relative flex-1">
            <Input
              id={`temp-${equipment.id}`}
              type="number"
              step="0.1"
              placeholder="— °C"
              value={value}
              onChange={(e) => onChange(equipment.id, e.target.value)}
              disabled={disabled}
              className={
                outOfRange
                  ? "border-destructive text-destructive focus-visible:ring-destructive"
                  : inRange
                    ? "border-emerald-500 focus-visible:ring-emerald-500"
                    : ""
              }
            />
          </div>
          {inRange && <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-600" />}
          {outOfRange && <AlertTriangle className="h-5 w-5 shrink-0 text-destructive" />}
        </div>
        {outOfRange && (
          <p className="mt-1.5 text-xs text-destructive">
            Hors seuil — une non-conformité sera ouverte automatiquement.
          </p>
        )}
      </CardContent>
    </Card>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function TemperatureRecordPage() {
  const { operator } = useOperator()
  const [equipments, setEquipments] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [values, dispatch] = useReducer(valuesReducer, {})
  const [submitting, setSubmitting] = useState(false)
  const [ncResults, setNcResults] = useState(null)
  const [pendingCount, setPendingCount] = useState(0)
  const [flushing, setFlushing] = useState(false)

  // Load equipment list on mount
  useEffect(() => {
    const token = loadEstablishmentToken()
    if (!token || !operator) return
    getEquipments(token, { pin: operator.pin, operatorId: operator.id })
      .then((data) => setEquipments(data.items.filter((e) => e.is_active)))
      .catch((err) => setLoadError(String(err.message)))
      .finally(() => setLoading(false))
    setPendingCount(queueSize())
  }, [operator])

  // Flush the offline queue via the bulk endpoint
  const flushQueue = useCallback(async () => {
    const token = loadEstablishmentToken()
    if (!token || !operator) return
    const records = buildFlushPayload()
    if (records.length === 0) return
    setFlushing(true)
    try {
      await postTemperatureRecordsBulk(token, { pin: operator.pin, operatorId: operator.id }, records)
      clearQueue()
      setPendingCount(0)
      toast.success(`${records.length} relevé${records.length > 1 ? "s" : ""} synchronisé${records.length > 1 ? "s" : ""}`)
    } catch (err) {
      toast.error(`Échec de la synchronisation : ${err.message}`)
    } finally {
      setFlushing(false)
    }
  }, [operator])

  // Auto-flush when the device comes back online
  useEffect(() => {
    window.addEventListener("online", flushQueue)
    return () => window.removeEventListener("online", flushQueue)
  }, [flushQueue])

  async function handleSubmit() {
    if (!operator || !equipments) return
    const filledEntries = equipments.filter((e) => values[e.id]?.trim())
    if (filledEntries.length === 0) {
      toast.warning("Saisissez au moins une mesure avant d'enregistrer.")
      return
    }

    const records = filledEntries.map((e) => ({
      equipment_id: e.id,
      measured_value: parseFloat(values[e.id]),
      source: "MANUEL",
    }))

    if (!navigator.onLine) {
      records.forEach((r) => enqueueTemperatureRecord(r))
      setPendingCount(queueSize())
      toast.warning(
        `Hors ligne — ${records.length} relevé${records.length > 1 ? "s" : ""} sauvegardé${records.length > 1 ? "s" : ""} localement.`
      )
      dispatch({ type: "RESET" })
      return
    }

    const token = loadEstablishmentToken()
    if (!token) return

    setSubmitting(true)
    setNcResults(null)
    try {
      const result = await postTemperatureRecordsBulk(
        token,
        { pin: operator.pin, operatorId: operator.id },
        records
      )
      dispatch({ type: "RESET" })
      if (result.nonconformity_count > 0) {
        setNcResults(result.created.filter((r) => !r.is_conforme))
        toast.error(
          `${result.nonconformity_count} non-conformité${result.nonconformity_count > 1 ? "s" : ""} détectée${result.nonconformity_count > 1 ? "s" : ""} — action corrective requise.`
        )
      } else {
        toast.success(`${result.count} relevé${result.count > 1 ? "s" : ""} enregistré${result.count > 1 ? "s" : ""} avec succès.`)
      }
    } catch (err) {
      toast.error(String(err.message))
    } finally {
      setSubmitting(false)
    }
  }

  const filledCount = equipments ? equipments.filter((e) => values[e.id]?.trim()).length : 0

  if (loading) {
    return (
      <div className="mx-auto max-w-lg space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-64" />
        {[...Array(3)].map((_, i) => (
          <Skeleton key={i} className="h-28 w-full" />
        ))}
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="mx-auto max-w-lg">
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{loadError}</AlertDescription>
        </Alert>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-lg space-y-6">
      {/* Header */}
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <Thermometer className="h-5 w-5 text-primary" />
          <h1 className="text-2xl font-semibold">Relevés de température</h1>
        </div>
        <p className="text-sm text-muted-foreground">
          {equipments?.length ?? 0} équipement{equipments?.length !== 1 ? "s" : ""} à contrôler
        </p>
      </div>

      {/* Offline queue badge */}
      {pendingCount > 0 && (
        <Alert>
          <WifiOff className="h-4 w-4" />
          <AlertTitle>Relevés en attente de synchronisation</AlertTitle>
          <AlertDescription className="flex items-center justify-between gap-4">
            <span>
              {pendingCount} relevé{pendingCount > 1 ? "s" : ""} stocké{pendingCount > 1 ? "s" : ""} localement.
            </span>
            <Button size="sm" variant="outline" onClick={flushQueue} disabled={flushing}>
              {flushing ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : null}
              Synchroniser
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {/* NC results from the last submit */}
      {ncResults && ncResults.length > 0 && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Actions correctives requises ({ncResults.length})</AlertTitle>
          <AlertDescription>
            <ul className="mt-2 space-y-1 text-sm">
              {ncResults.map((r) => {
                const eq = equipments?.find((e) => e.id === r.equipment_id)
                return (
                  <li key={r.id} className="flex items-center gap-2">
                    <span className="font-medium">{eq?.name ?? r.equipment_id}</span>
                    <span className="tabular-nums">— {r.measured_value}°C</span>
                    <Badge variant="destructive" className="ml-auto text-xs">
                      NC #{r.nonconformity_id?.slice(0, 8)}
                    </Badge>
                  </li>
                )
              })}
            </ul>
          </AlertDescription>
        </Alert>
      )}

      {/* Equipment cards */}
      {equipments?.length === 0 ? (
        <Alert>
          <AlertDescription>
            Aucun équipement configuré. Contactez votre manager.
          </AlertDescription>
        </Alert>
      ) : (
        <div className="space-y-4">
          {equipments?.map((equipment) => (
            <EquipmentCard
              key={equipment.id}
              equipment={equipment}
              value={values[equipment.id] ?? ""}
              onChange={(id, val) => dispatch({ type: "SET", id, value: val })}
              disabled={submitting}
            />
          ))}
        </div>
      )}

      {/* Submit */}
      {equipments?.length > 0 && (
        <Button
          className="w-full"
          size="lg"
          onClick={handleSubmit}
          disabled={submitting || filledCount === 0}
        >
          {submitting ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <CheckCircle2 className="mr-2 h-4 w-4" />
          )}
          Enregistrer la tournée
          {filledCount > 0 && (
            <Badge variant="secondary" className="ml-2">
              {filledCount}
            </Badge>
          )}
        </Button>
      )}
    </div>
  )
}
