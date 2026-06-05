"use client"

import { useEffect, useReducer, useState } from "react"
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Loader2,
  SprayCan,
} from "lucide-react"
import { toast } from "sonner"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import { OperatorBackLink } from "@/components/operator/OperatorBackLink"
import { fetchCurrentRoutine, submitBulkCleaning } from "@/lib/api/cleaning"
import { useOperator } from "@/lib/contexts/OperatorContext"
import { loadEstablishmentToken } from "@/lib/session/establishment"

const SCHEDULE_LABELS = {
  OPENING: "Ouverture",
  CLOSING: "Fermeture",
  WEEKLY: "Hebdomadaire",
  MONTHLY: "Mensuel",
}

// ── Per-task state ────────────────────────────────────────────────────────────
// taskStates: { [task_id]: { status: "DONE"|"ISSUE"|null, comment: "" } }

function taskReducer(state, action) {
  switch (action.type) {
    case "SET_STATUS":
      return {
        ...state,
        [action.taskId]: { ...state[action.taskId], status: action.status, comment: state[action.taskId]?.comment ?? "" },
      }
    case "SET_COMMENT":
      return {
        ...state,
        [action.taskId]: { ...state[action.taskId], comment: action.comment },
      }
    case "RESET_ZONE":
      return Object.fromEntries(
        Object.entries(state).filter(([id]) => !action.taskIds.includes(id))
      )
    default:
      return state
  }
}

// ── ZoneCard ──────────────────────────────────────────────────────────────────

function ZoneCard({ zone, onZoneSubmitted }) {
  const { operator } = useOperator()
  const [open, setOpen] = useState(false)
  const [taskStates, dispatch] = useReducer(taskReducer, {})
  const [submitting, setSubmitting] = useState(false)
  const [done, setDone] = useState(() => zone.tasks.every((t) => t.log !== null))

  // Pre-fill from existing today logs
  useEffect(() => {
    zone.tasks.forEach((task) => {
      if (task.log) {
        dispatch({ type: "SET_STATUS", taskId: task.task_id, status: task.log.status })
        if (task.log.comment) {
          dispatch({ type: "SET_COMMENT", taskId: task.task_id, comment: task.log.comment })
        }
      }
    })
  }, [zone])

  async function submitItems(items) {
    const token = loadEstablishmentToken()
    if (!token || !operator) return false
    setSubmitting(true)
    try {
      await submitBulkCleaning(token, { pin: operator.pin, operatorId: operator.id }, items)
      return true
    } catch (err) {
      toast.error(String(err.message))
      return false
    } finally {
      setSubmitting(false)
    }
  }

  async function handleFastPath() {
    const items = zone.tasks.map((t) => ({ task_id: t.task_id, status: "DONE", comment: null }))
    const ok = await submitItems(items)
    if (ok) {
      toast.success(`Zone "${zone.zone_name}" validée`)
      setDone(true)
      onZoneSubmitted(zone.zone_id)
    }
  }

  async function handleSubmitZone() {
    // Validate: ISSUE tasks must have a comment
    for (const task of zone.tasks) {
      const ts = taskStates[task.task_id]
      if (!ts?.status) {
        toast.error(`Toutes les tâches doivent être renseignées (zone : ${zone.zone_name})`)
        return
      }
      if (ts.status === "ISSUE" && !ts.comment?.trim()) {
        toast.error(`Un commentaire est requis pour les tâches en anomalie`)
        return
      }
    }
    const items = zone.tasks.map((t) => ({
      task_id: t.task_id,
      status: taskStates[t.task_id].status,
      comment: taskStates[t.task_id].comment?.trim() || null,
    }))
    const ok = await submitItems(items)
    if (ok) {
      toast.success(`Zone "${zone.zone_name}" enregistrée`)
      setDone(true)
      onZoneSubmitted(zone.zone_id)
    }
  }

  const allFilled = zone.tasks.every((t) => taskStates[t.task_id]?.status)

  if (done) {
    return (
      <Card className="border-emerald-200 bg-emerald-50/50">
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-emerald-600" />
            <CardTitle className="text-base text-emerald-800">{zone.zone_name}</CardTitle>
            <Badge variant="outline" className="ml-auto border-emerald-300 text-emerald-700 text-xs">
              Validée
            </Badge>
          </div>
        </CardHeader>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <SprayCan className="h-5 w-5 text-primary" />
          <CardTitle className="text-base">{zone.zone_name}</CardTitle>
          <span className="ml-auto text-xs text-muted-foreground">
            {zone.tasks.length} tâche{zone.tasks.length > 1 ? "s" : ""}
          </span>
        </div>
      </CardHeader>

      <CardContent className="space-y-3 pt-0">
        {/* Fast-path */}
        <Button
          className="h-12 w-full gap-2 text-sm font-semibold"
          onClick={handleFastPath}
          disabled={submitting}
        >
          {submitting ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <CheckCircle2 className="h-4 w-4" />
          )}
          Valider toute la zone
        </Button>

        {/* Accordion */}
        <button
          type="button"
          className="flex w-full items-center justify-between text-xs text-muted-foreground hover:text-foreground"
          onClick={() => setOpen((v) => !v)}
        >
          <span>Détail des tâches</span>
          {open ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
        </button>

        {open && (
          <div className="space-y-4 pt-1">
            {zone.tasks.map((task) => {
              const ts = taskStates[task.task_id] ?? {}
              const isIssue = ts.status === "ISSUE"
              const isDone = ts.status === "DONE"
              const hasExistingLog = task.log !== null

              return (
                <div key={task.task_id} className="rounded-lg border p-3 space-y-2">
                  <div>
                    <p className="text-sm font-medium">{task.name}</p>
                    {task.description && (
                      <p className="text-xs text-muted-foreground mt-0.5">{task.description}</p>
                    )}
                    {hasExistingLog && (
                      <Badge variant="outline" className="mt-1 text-xs">
                        Déjà enregistré aujourd'hui
                      </Badge>
                    )}
                  </div>

                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant={isDone ? "default" : "outline"}
                      className={`flex-1 ${isDone ? "bg-emerald-600 hover:bg-emerald-700" : ""}`}
                      onClick={() => dispatch({ type: "SET_STATUS", taskId: task.task_id, status: "DONE" })}
                      disabled={submitting}
                    >
                      <CheckCircle2 className="mr-1.5 h-3.5 w-3.5" />
                      Fait
                    </Button>
                    <Button
                      size="sm"
                      variant={isIssue ? "destructive" : "outline"}
                      className="flex-1"
                      onClick={() => dispatch({ type: "SET_STATUS", taskId: task.task_id, status: "ISSUE" })}
                      disabled={submitting}
                    >
                      <AlertTriangle className="mr-1.5 h-3.5 w-3.5" />
                      Anomalie
                    </Button>
                  </div>

                  {isIssue && (
                    <Textarea
                      placeholder="Décrivez l'anomalie (obligatoire)…"
                      value={ts.comment ?? ""}
                      onChange={(e) =>
                        dispatch({ type: "SET_COMMENT", taskId: task.task_id, comment: e.target.value })
                      }
                      className="text-sm resize-none"
                      rows={2}
                      disabled={submitting}
                    />
                  )}
                </div>
              )
            })}

            <Button
              className="w-full"
              variant="outline"
              onClick={handleSubmitZone}
              disabled={!allFilled || submitting}
            >
              {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Enregistrer la zone
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function CleaningPage() {
  const [routine, setRoutine] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [submittedZones, setSubmittedZones] = useState(new Set())

  useEffect(() => {
    const token = loadEstablishmentToken()
    if (!token) return
    fetchCurrentRoutine(token)
      .then(setRoutine)
      .catch((err) => setError(String(err.message)))
      .finally(() => setLoading(false))
  }, [])

  function handleZoneSubmitted(zoneId) {
    setSubmittedZones((prev) => new Set([...prev, zoneId]))
  }

  const pendingCount = routine
    ? routine.zones.filter((z) => !submittedZones.has(z.zone_id) && !z.tasks.every((t) => t.log)).length
    : 0
  const allDone = routine && pendingCount === 0

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="mx-auto max-w-lg">
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      </div>
    )
  }

  if (!routine) return null

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <OperatorBackLink phase="closing" />
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-semibold">{routine.routine_name}</h1>
          <Badge variant="secondary">{SCHEDULE_LABELS[routine.schedule_type] ?? routine.schedule_type}</Badge>
        </div>
        <p className="text-sm text-muted-foreground">
          {routine.zones.length} zone{routine.zones.length > 1 ? "s" : ""} ·{" "}
          {allDone ? (
            <span className="font-medium text-emerald-600">Toutes les zones validées ✓</span>
          ) : (
            <span>{pendingCount} zone{pendingCount > 1 ? "s" : ""} restante{pendingCount > 1 ? "s" : ""}</span>
          )}
        </p>
      </div>

      {routine.zones.length === 0 ? (
        <Alert>
          <AlertDescription>
            Aucune zone configurée pour cette routine. Contactez votre manager.
          </AlertDescription>
        </Alert>
      ) : (
        <div className="space-y-4">
          {routine.zones.map((zone) => (
            <ZoneCard
              key={zone.zone_id}
              zone={zone}
              onZoneSubmitted={handleZoneSubmitted}
            />
          ))}
        </div>
      )}
    </div>
  )
}
