"use client"

import { useEffect, useMemo, useState } from "react"
import { useSearchParams } from "next/navigation"
import { CheckCircle2, Loader2, User } from "lucide-react"
import { toast } from "sonner"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { KioskBackButton } from "@/components/kiosk/KioskBackButton"
import { KioskProgressBar } from "@/components/kiosk/KioskProgressBar"
import {
  backRouteForSchedule,
  CLEANING_SCHEDULES,
  parseScheduleParam,
} from "@/lib/kiosk/cleaningSchedule"
import { fetchCurrentRoutine, submitBulkCleaning } from "@/lib/api/cleaning"
import { useOperator } from "@/lib/contexts/OperatorContext"
import { loadEstablishmentToken } from "@/lib/session/establishment"
import { cn } from "@/lib/utils"

function CleaningTaskCard({ task, operatorId, onDone, submittingId, issueTask, onIssueSubmit }) {
  const isDone = Boolean(task.log)
  const isMine =
    !task.assigned_operator_id || task.assigned_operator_id === operatorId
  const isSubmitting = submittingId === task.task_id

  if (isDone) {
    return (
      <div className="flex items-center gap-3 rounded-lg border border-emerald-200 bg-emerald-50/80 px-4 py-3">
        <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-600" />
        <div className="min-w-0 flex-1">
          <p className="font-semibold text-slate-900">{task.name}</p>
          <p className="text-[0.95rem] text-emerald-800">Effectué aujourd&apos;hui</p>
        </div>
      </div>
    )
  }

  if (issueTask?.task_id === task.task_id) {
    return (
      <div className="rounded-lg border-2 border-red-300 bg-red-50 p-4">
        <p className="mb-2 font-semibold text-red-900">{task.name} — anomalie</p>
        <Textarea
          value={issueTask.comment}
          onChange={(e) => onIssueSubmit({ ...issueTask, comment: e.target.value })}
          placeholder="Décrivez le problème…"
          className="mb-3 min-h-20 text-[1rem]"
        />
        <div className="flex gap-2">
          <Button
            variant="outline"
            className="flex-1"
            onClick={() => onIssueSubmit(null)}
            disabled={isSubmitting}
          >
            Annuler
          </Button>
          <Button
            variant="destructive"
            className="flex-1"
            onClick={() => onDone(task.task_id, "ISSUE", issueTask.comment)}
            disabled={isSubmitting || !issueTask.comment?.trim()}
          >
            Enregistrer
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div
      className={cn(
        "rounded-lg border px-4 py-3",
        isMine ? "border-slate-200 bg-white" : "border-slate-100 bg-slate-50/80",
      )}
    >
      <div className="mb-2 flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="text-[1.1rem] font-semibold text-slate-900">{task.name}</p>
          {task.description && (
            <p className="mt-1 text-[0.95rem] leading-relaxed text-slate-600">{task.description}</p>
          )}
        </div>
        {task.assigned_operator_name && (
          <span className="inline-flex items-center gap-1 rounded-full bg-violet-100 px-2.5 py-1 text-[0.85rem] font-medium text-violet-900">
            <User className="h-3.5 w-3.5" />
            {task.assigned_operator_name}
          </span>
        )}
      </div>

      {!isMine && (
        <p className="mb-2 text-[0.9rem] text-slate-500">Tâche assignée à un autre collègue</p>
      )}

      <div className="flex gap-2">
        <Button
          className="h-11 flex-1 text-[1rem] font-semibold"
          onClick={() => onDone(task.task_id, "DONE")}
          disabled={isSubmitting}
        >
          {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : "Fait"}
        </Button>
        <Button
          variant="outline"
          className="h-11 flex-1 text-[1rem] font-semibold text-red-700"
          onClick={() => onIssueSubmit({ task_id: task.task_id, comment: "" })}
          disabled={isSubmitting}
        >
          Anomalie
        </Button>
      </div>
    </div>
  )
}

export default function CleaningPage() {
  const searchParams = useSearchParams()
  const { operator } = useOperator()
  const initialSchedule = parseScheduleParam(searchParams.get("schedule"))
  const [schedule, setSchedule] = useState(initialSchedule)
  const [filter, setFilter] = useState("mine")
  const [routine, setRoutine] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [submittingId, setSubmittingId] = useState(null)
  const [issueTask, setIssueTask] = useState(null)

  useEffect(() => {
    const token = loadEstablishmentToken()
    if (!token) return
    setLoading(true)
    setError(null)
    fetchCurrentRoutine(token, schedule)
      .then(setRoutine)
      .catch((err) => setError(String(err.message)))
      .finally(() => setLoading(false))
  }, [schedule])

  const visibleZones = useMemo(() => {
    if (!routine?.zones) return []
    if (filter !== "mine" || !operator?.id) return routine.zones
    return routine.zones
      .map((zone) => ({
        ...zone,
        tasks: zone.tasks.filter(
          (t) => !t.assigned_operator_id || t.assigned_operator_id === operator.id,
        ),
      }))
      .filter((z) => z.tasks.length > 0)
  }, [routine, filter, operator?.id])

  const { totalTasks, doneTasks } = useMemo(() => {
    let total = 0
    let done = 0
    for (const zone of visibleZones) {
      for (const task of zone.tasks) {
        total += 1
        if (task.log) done += 1
      }
    }
    return { totalTasks: total, doneTasks: done }
  }, [visibleZones])

  async function handleTaskDone(taskId, status, comment = null) {
    const token = loadEstablishmentToken()
    if (!token || !operator) return
    setSubmittingId(taskId)
    try {
      await submitBulkCleaning(token, { pin: operator.pin, operatorId: operator.id }, [
        { task_id: taskId, status, comment: comment?.trim() || null },
      ])
      toast.success(status === "DONE" ? "Tâche validée" : "Anomalie enregistrée")
      setIssueTask(null)
      const refreshed = await fetchCurrentRoutine(token, schedule)
      setRoutine(refreshed)
    } catch (err) {
      toast.error(String(err.message))
    } finally {
      setSubmittingId(null)
    }
  }

  const activeSchedule = CLEANING_SCHEDULES.find((s) => s.value === schedule)

  return (
    <div className="flex flex-1 flex-col gap-4">
      <div className="flex items-center justify-between gap-4">
        <KioskBackButton href={backRouteForSchedule(schedule)} />
        <div className="text-right">
          <p className="text-[0.95rem] font-semibold uppercase tracking-wide text-violet-700">
            Hygiène
          </p>
          <h1 className="text-[1.5rem] font-bold text-slate-900">Plan de nettoyage</h1>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {CLEANING_SCHEDULES.map((s) => (
          <button
            key={s.value}
            type="button"
            onClick={() => setSchedule(s.value)}
            className={cn(
              "rounded-lg border-2 px-3 py-2 text-left text-[0.95rem] font-semibold",
              schedule === s.value
                ? "border-violet-500 bg-violet-50 text-violet-900"
                : "border-slate-200 bg-white text-slate-700",
            )}
          >
            {s.label}
          </button>
        ))}
      </div>

      {activeSchedule && (
        <p className="text-[1rem] text-slate-600">{activeSchedule.hint}</p>
      )}

      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => setFilter("mine")}
          className={cn(
            "rounded-full px-4 py-1.5 text-[0.95rem] font-semibold",
            filter === "mine" ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-700",
          )}
        >
          Mes tâches
        </button>
        <button
          type="button"
          onClick={() => setFilter("all")}
          className={cn(
            "rounded-full px-4 py-1.5 text-[0.95rem] font-semibold",
            filter === "all" ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-700",
          )}
        >
          Toutes
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : error ? (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : (
        <>
          <KioskProgressBar done={doneTasks} total={totalTasks} />

          {visibleZones.length === 0 ? (
            <p className="py-8 text-center text-[1.05rem] text-slate-600">
              {filter === "mine"
                ? "Aucune tâche ne vous est assignée pour ce créneau."
                : "Aucune tâche configurée pour ce créneau."}
            </p>
          ) : (
            <div className="space-y-5">
              {visibleZones.map((zone) => (
                <section key={zone.zone_id}>
                  <h2 className="mb-2 border-b border-slate-200 pb-1 text-[1.05rem] font-bold uppercase tracking-wide text-slate-700">
                    {zone.zone_name}
                  </h2>
                  <div className="space-y-2">
                    {zone.tasks.map((task) => (
                      <CleaningTaskCard
                        key={task.task_id}
                        task={task}
                        operatorId={operator?.id}
                        submittingId={submittingId}
                        issueTask={issueTask}
                        onIssueSubmit={setIssueTask}
                        onDone={handleTaskDone}
                      />
                    ))}
                  </div>
                </section>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
