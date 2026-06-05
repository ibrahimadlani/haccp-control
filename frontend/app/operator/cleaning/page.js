"use client"

import { useEffect, useMemo, useReducer, useState } from "react"
import { AlertTriangle, CheckCircle2, Loader2, SprayCan } from "lucide-react"
import { toast } from "sonner"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { KioskBackButton } from "@/components/kiosk/KioskBackButton"
import { KioskProgressBar } from "@/components/kiosk/KioskProgressBar"
import { KIOSK_PHASES } from "@/lib/kiosk/phases"
import { fetchCurrentRoutine, submitBulkCleaning } from "@/lib/api/cleaning"
import { useOperator } from "@/lib/contexts/OperatorContext"
import { loadEstablishmentToken } from "@/lib/session/establishment"
import { cn } from "@/lib/utils"

const SCHEDULE_LABELS = {
  OPENING: "Ouverture",
  CLOSING: "Fermeture",
  WEEKLY: "Hebdomadaire",
  MONTHLY: "Mensuel",
}

function taskReducer(state, action) {
  switch (action.type) {
    case "SET_STATUS":
      return {
        ...state,
        [action.taskId]: {
          ...state[action.taskId],
          status: action.status,
          comment: state[action.taskId]?.comment ?? "",
        },
      }
    case "SET_COMMENT":
      return {
        ...state,
        [action.taskId]: { ...state[action.taskId], comment: action.comment },
      }
    default:
      return state
  }
}

function KioskTaskRow({ task, taskState, dispatch, submitting }) {
  const ts = taskState ?? {}
  const isIssue = ts.status === "ISSUE"
  const isDone = ts.status === "DONE"

  return (
    <div
      className={cn(
        "rounded-2xl border-2 p-4 transition-colors",
        isDone && "border-emerald-400 bg-emerald-50/60",
        isIssue && "border-red-400 bg-red-50/60",
        !isDone && !isIssue && "border-slate-200 bg-white",
      )}
    >
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <p className="text-[1.35rem] font-extrabold text-slate-900">{task.name}</p>
          {task.description && (
            <p className="mt-1 text-[1.05rem] text-slate-600">{task.description}</p>
          )}
          {task.log && (
            <p className="mt-2 text-[1rem] font-medium text-emerald-700">✓ Déjà validé aujourd&apos;hui</p>
          )}
        </div>
        <span className="shrink-0 rounded-full bg-slate-100 px-3 py-1 text-[0.95rem] font-semibold text-slate-600">
          Quotidien
        </span>
      </div>

      {!task.log && (
        <>
          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              disabled={submitting}
              onClick={() => dispatch({ type: "SET_STATUS", taskId: task.task_id, status: "DONE" })}
              className={cn(
                "flex min-h-[4rem] items-center justify-center gap-2 rounded-xl border-2 text-[1.2rem] font-bold transition-all active:scale-[0.98]",
                isDone
                  ? "border-emerald-600 bg-emerald-600 text-white"
                  : "border-emerald-300 bg-white text-emerald-800",
              )}
            >
              <CheckCircle2 className="h-6 w-6" />
              FAIT
            </button>
            <button
              type="button"
              disabled={submitting}
              onClick={() => dispatch({ type: "SET_STATUS", taskId: task.task_id, status: "ISSUE" })}
              className={cn(
                "flex min-h-[4rem] items-center justify-center gap-2 rounded-xl border-2 text-[1.2rem] font-bold transition-all active:scale-[0.98]",
                isIssue
                  ? "border-red-600 bg-red-600 text-white"
                  : "border-red-300 bg-white text-red-800",
              )}
            >
              <AlertTriangle className="h-6 w-6" />
              ANOMALIE
            </button>
          </div>

          {isIssue && (
            <Textarea
              placeholder="Décrivez l'anomalie (obligatoire)…"
              value={ts.comment ?? ""}
              onChange={(e) =>
                dispatch({ type: "SET_COMMENT", taskId: task.task_id, comment: e.target.value })
              }
              className="mt-3 min-h-24 text-[1.1rem]"
              rows={3}
              disabled={submitting}
            />
          )}
        </>
      )}
    </div>
  )
}

function KioskZoneBlock({ zone, onZoneSubmitted }) {
  const { operator } = useOperator()
  const [taskStates, dispatch] = useReducer(taskReducer, {})
  const [submitting, setSubmitting] = useState(false)
  const allLogged = zone.tasks.every((t) => t.log !== null)

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
      toast.success(`Zone « ${zone.zone_name} » validée`)
      onZoneSubmitted(zone.zone_id)
    }
  }

  async function handleSubmitZone() {
    for (const task of zone.tasks) {
      if (task.log) continue
      const ts = taskStates[task.task_id]
      if (!ts?.status) {
        toast.error(`Toutes les tâches doivent être renseignées (${zone.zone_name})`)
        return
      }
      if (ts.status === "ISSUE" && !ts.comment?.trim()) {
        toast.error("Commentaire obligatoire pour une anomalie")
        return
      }
    }
    const items = zone.tasks
      .filter((t) => !t.log)
      .map((t) => ({
        task_id: t.task_id,
        status: taskStates[t.task_id].status,
        comment: taskStates[t.task_id].comment?.trim() || null,
      }))
    if (items.length === 0) return
    const ok = await submitItems(items)
    if (ok) {
      toast.success(`Zone « ${zone.zone_name} » enregistrée`)
      onZoneSubmitted(zone.zone_id)
    }
  }

  const pendingTasks = zone.tasks.filter((t) => !t.log)
  const allFilled = pendingTasks.every((t) => taskStates[t.task_id]?.status)

  return (
    <section className="space-y-4 rounded-2xl border-2 border-slate-200 bg-slate-50/50 p-4">
      <div className="flex items-center gap-3">
        <SprayCan className="h-7 w-7 text-violet-600" />
        <h2 className="text-[1.4rem] font-extrabold text-slate-900">{zone.zone_name}</h2>
        {allLogged && (
          <span className="ml-auto rounded-full bg-emerald-100 px-3 py-1 text-[1rem] font-bold text-emerald-800">
            Validée
          </span>
        )}
      </div>

      <div className="space-y-3">
        {zone.tasks.map((task) => (
          <KioskTaskRow
            key={task.task_id}
            task={task}
            taskState={taskStates[task.task_id]}
            dispatch={dispatch}
            submitting={submitting}
          />
        ))}
      </div>

      {!allLogged && (
        <div className="grid gap-3 sm:grid-cols-2">
          <Button
            className="h-14 text-[1.2rem] font-bold"
            onClick={handleFastPath}
            disabled={submitting}
          >
            {submitting ? <Loader2 className="h-5 w-5 animate-spin" /> : "✓ Tout valider"}
          </Button>
          {pendingTasks.length > 0 && (
            <Button
              variant="outline"
              className="h-14 text-[1.2rem] font-bold"
              onClick={handleSubmitZone}
              disabled={!allFilled || submitting}
            >
              Enregistrer le détail
            </Button>
          )}
        </div>
      )}
    </section>
  )
}

export default function CleaningPage() {
  const [routine, setRoutine] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    const token = loadEstablishmentToken()
    if (!token) return
    setLoading(true)
    fetchCurrentRoutine(token)
      .then(setRoutine)
      .catch((err) => setError(String(err.message)))
      .finally(() => setLoading(false))
  }, [refreshKey])

  function handleZoneSubmitted() {
    setRefreshKey((k) => k + 1)
  }

  const { totalTasks, doneTasks } = useMemo(() => {
    if (!routine) return { totalTasks: 0, doneTasks: 0 }
    let total = 0
    let done = 0
    for (const zone of routine.zones) {
      for (const task of zone.tasks) {
        total += 1
        if (task.log) done += 1
      }
    }
    return { totalTasks: total, doneTasks: done }
  }, [routine])

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-1 flex-col gap-4">
        <KioskBackButton href={KIOSK_PHASES.closing.route} />
        <Alert variant="destructive">
          <AlertDescription className="text-[1.1rem]">{error}</AlertDescription>
        </Alert>
      </div>
    )
  }

  if (!routine) return null

  return (
    <div className="flex flex-1 flex-col gap-5">
      <div className="flex items-center justify-between gap-4">
        <KioskBackButton href={KIOSK_PHASES.closing.route} />
        <div className="text-right">
          <p className="text-[1.1rem] text-violet-700">🧹 Nettoyage</p>
          <h1 className="text-[1.6rem] font-extrabold">{routine.routine_name}</h1>
        </div>
      </div>

      <KioskProgressBar done={doneTasks} total={totalTasks} />

      {routine.zones.length === 0 ? (
        <Alert>
          <AlertDescription className="text-[1.1rem]">
            Aucune zone configurée. Contactez votre gestionnaire.
          </AlertDescription>
        </Alert>
      ) : (
        <div className="space-y-5">
          {routine.zones.map((zone) => (
            <KioskZoneBlock
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
