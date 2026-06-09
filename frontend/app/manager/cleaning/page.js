"use client"

import { useCallback, useEffect, useState } from "react"
import {
  ChevronDown,
  ChevronUp,
  ClipboardList,
  Layers,
  Loader2,
  MapPin,
  Pencil,
  Plus,
  SprayCan,
  Trash2,
  User,
} from "lucide-react"
import { toast } from "sonner"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import {
  createCleaningRoutine,
  createCleaningTask,
  createCleaningZone,
  deleteCleaningRoutine,
  deleteCleaningTask,
  deleteCleaningZone,
  getCleaningRoutineDetail,
  getCleaningRoutines,
  getCleaningZones,
  updateCleaningTask,
} from "@/lib/api/cleaning"
import { getEstablishmentUsers } from "@/lib/api/auth"
import { loadEstablishmentContext, loadEstablishmentToken } from "@/lib/session/establishment"

// ── Constants ─────────────────────────────────────────────────────────────────

const SCHEDULE_LABELS = {
  OPENING: "Avant le repas",
  CLOSING: "Après le repas",
  WEEKLY: "Hebdomadaire",
  MONTHLY: "Mensuel",
}

const SCHEDULE_COLORS = {
  OPENING: "bg-emerald-100 text-emerald-800 border-emerald-200",
  CLOSING: "bg-amber-100 text-amber-800 border-amber-200",
  WEEKLY: "bg-blue-100 text-blue-800 border-blue-200",
  MONTHLY: "bg-purple-100 text-purple-800 border-purple-200",
}

const SCHEDULE_OPTIONS = [
  { value: "OPENING", label: "Avant le repas" },
  { value: "CLOSING", label: "Après le repas" },
  { value: "WEEKLY", label: "Hebdomadaire" },
  { value: "MONTHLY", label: "Mensuel" },
]

// ── Helpers ───────────────────────────────────────────────────────────────────

function token() {
  return loadEstablishmentToken()
}

function operatorLabel(user) {
  if (!user) return ""
  return (
    user.nom_complet ??
    `${user.prenom ?? user.first_name ?? ""} ${user.nom ?? user.last_name ?? ""}`.trim()
  )
}

// ── Dialogs ───────────────────────────────────────────────────────────────────

function NewZoneDialog({ open, onClose, onCreated }) {
  const [name, setName] = useState("")
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    if (!name.trim()) return
    setSaving(true)
    try {
      const zone = await createCleaningZone(token(), { name: name.trim() })
      toast.success(`Zone "${zone.name}" créée`)
      onCreated(zone)
      setName("")
    } catch (err) {
      toast.error(String(err.message))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <MapPin className="h-4 w-4 text-primary" />
            Nouvelle zone
          </DialogTitle>
          <DialogDescription>
            Une zone regroupe les tâches d'un même espace physique.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 pt-1">
          <div className="space-y-1.5">
            <Label htmlFor="zone-name">Nom de la zone *</Label>
            <Input
              id="zone-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="ex. Cuisine chaude"
              autoFocus
              required
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={saving}>
              Annuler
            </Button>
            <Button type="submit" disabled={!name.trim() || saving}>
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Créer la zone
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function NewRoutineDialog({ open, onClose, onCreated }) {
  const [name, setName] = useState("")
  const [scheduleType, setScheduleType] = useState("")
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    if (!name.trim() || !scheduleType) return
    setSaving(true)
    try {
      const routine = await createCleaningRoutine(token(), {
        name: name.trim(),
        schedule_type: scheduleType,
      })
      toast.success(`Routine "${routine.name}" créée`)
      onCreated(routine)
      setName("")
      setScheduleType("")
    } catch (err) {
      toast.error(String(err.message))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ClipboardList className="h-4 w-4 text-primary" />
            Nouvelle routine
          </DialogTitle>
          <DialogDescription>
            Une routine est un programme de nettoyage récurrent (ouverture, fermeture…).
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 pt-1">
          <div className="space-y-1.5">
            <Label htmlFor="r-name">Nom *</Label>
            <Input
              id="r-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="ex. Fermeture Midi"
              autoFocus
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label>Récurrence *</Label>
            <Select value={scheduleType} onValueChange={setScheduleType} required>
              <SelectTrigger>
                <SelectValue placeholder="Choisir…" />
              </SelectTrigger>
              <SelectContent>
                {SCHEDULE_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={saving}>
              Annuler
            </Button>
            <Button type="submit" disabled={!name.trim() || !scheduleType || saving}>
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Créer la routine
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function NewTaskDialog({ open, onClose, onCreated, routineId, zones, operators, preselectedZoneId }) {
  const [zoneId, setZoneId] = useState(preselectedZoneId ?? "")
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [assigneeId, setAssigneeId] = useState("")
  const [saving, setSaving] = useState(false)

  // Sync preselected zone when dialog opens
  useEffect(() => {
    if (open) {
      setZoneId(preselectedZoneId ?? "")
      setAssigneeId("")
    }
  }, [open, preselectedZoneId])

  async function handleSubmit(e) {
    e.preventDefault()
    if (!zoneId || !name.trim()) return
    setSaving(true)
    try {
      const task = await createCleaningTask(token(), routineId, {
        zone_id: zoneId,
        name: name.trim(),
        description: description.trim() || null,
        assigned_operator_id: assigneeId || null,
      })
      toast.success("Tâche ajoutée")
      onCreated(task)
      setName("")
      setDescription("")
    } catch (err) {
      toast.error(String(err.message))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Plus className="h-4 w-4 text-primary" />
            Ajouter une tâche
          </DialogTitle>
          <DialogDescription>
            La tâche sera ajoutée à la zone sélectionnée dans cette routine.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 pt-1">
          <div className="space-y-1.5">
            <Label>Zone *</Label>
            <Select value={zoneId} onValueChange={setZoneId} required>
              <SelectTrigger>
                <SelectValue placeholder="Choisir une zone…" />
              </SelectTrigger>
              <SelectContent>
                {zones.map((z) => (
                  <SelectItem key={z.id} value={z.id}>
                    {z.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="t-name">Nom de la tâche *</Label>
            <Input
              id="t-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="ex. Désinfecter les plans de travail"
              autoFocus
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="t-desc">
              Instructions{" "}
              <span className="text-xs text-muted-foreground">(optionnel)</span>
            </Label>
            <Textarea
              id="t-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Détail du produit à utiliser, durée de contact…"
              rows={3}
              className="resize-none"
            />
          </div>
          <div className="space-y-1.5">
            <Label>Assigné à</Label>
            <Select value={assigneeId || "__none__"} onValueChange={(v) => setAssigneeId(v === "__none__" ? "" : v)}>
              <SelectTrigger>
                <SelectValue placeholder="Toute l'équipe" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">Toute l&apos;équipe</SelectItem>
                {operators.map((op) => (
                  <SelectItem key={op.id} value={op.id}>
                    {operatorLabel(op)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={saving}>
              Annuler
            </Button>
            <Button type="submit" disabled={!zoneId || !name.trim() || saving}>
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Ajouter la tâche
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function EditAssigneeDialog({ open, onClose, task, operators, onSaved }) {
  const [assigneeId, setAssigneeId] = useState("")
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (open && task) setAssigneeId(task.assigned_operator_id ?? "")
  }, [open, task])

  async function handleSubmit(e) {
    e.preventDefault()
    if (!task) return
    setSaving(true)
    try {
      await updateCleaningTask(token(), task.task_id, {
        assigned_operator_id: assigneeId || null,
      })
      toast.success("Assignation mise à jour")
      onSaved()
      onClose()
    } catch (err) {
      toast.error(String(err.message))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <User className="h-4 w-4 text-primary" />
            Assigner la tâche
          </DialogTitle>
          <DialogDescription>{task?.name}</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 pt-1">
          <div className="space-y-1.5">
            <Label>Responsable</Label>
            <Select value={assigneeId || "__none__"} onValueChange={(v) => setAssigneeId(v === "__none__" ? "" : v)}>
              <SelectTrigger>
                <SelectValue placeholder="Toute l'équipe" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">Toute l&apos;équipe</SelectItem>
                {operators.map((op) => (
                  <SelectItem key={op.id} value={op.id}>
                    {operatorLabel(op)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={saving}>
              Annuler
            </Button>
            <Button type="submit" disabled={saving}>
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Enregistrer
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ── ZoneSection (within a routine tab) ───────────────────────────────────────

function ZoneSection({ zoneItem, operators, onAddTask, onDeleteTask, onEditAssignee }) {
  const [expanded, setExpanded] = useState(true)

  return (
    <Card className="overflow-hidden">
      <button
        type="button"
        className="flex w-full items-center gap-3 px-5 py-4 text-left hover:bg-muted/50 transition-colors"
        onClick={() => setExpanded((v) => !v)}
      >
        <MapPin className="h-4 w-4 shrink-0 text-muted-foreground" />
        <span className="flex-1 font-medium">{zoneItem.zone_name}</span>
        <Badge variant="secondary" className="mr-2 tabular-nums">
          {zoneItem.tasks.length} tâche{zoneItem.tasks.length !== 1 ? "s" : ""}
        </Badge>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <span
                role="button"
                className="rounded p-1 hover:bg-accent"
                onClick={(e) => {
                  e.stopPropagation()
                  onAddTask(zoneItem.zone_id)
                }}
              >
                <Plus className="h-4 w-4 text-primary" />
              </span>
            </TooltipTrigger>
            <TooltipContent>Ajouter une tâche</TooltipContent>
          </Tooltip>
        </TooltipProvider>
        {expanded ? (
          <ChevronUp className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        )}
      </button>

      {expanded && (
        <>
          <Separator />
          {zoneItem.tasks.length === 0 ? (
            <div className="px-5 py-4 text-sm text-muted-foreground">
              Aucune tâche — cliquez sur + pour en ajouter.
            </div>
          ) : (
            <ul>
              {zoneItem.tasks.map((task, idx) => (
                <li key={task.task_id}>
                  {idx > 0 && <Separator className="mx-5" />}
                  <div className="flex items-start gap-3 px-5 py-3">
                    <SprayCan className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium leading-snug">{task.name}</p>
                      {task.description && (
                        <p className="mt-0.5 text-xs text-muted-foreground leading-relaxed">
                          {task.description}
                        </p>
                      )}
                      <p className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
                        <User className="h-3 w-3" />
                        {task.assigned_operator_name ?? "Toute l'équipe"}
                      </p>
                    </div>
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 shrink-0 text-muted-foreground"
                            onClick={() => onEditAssignee(task)}
                          >
                            <Pencil className="h-3.5 w-3.5" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>Modifier l&apos;assignation</TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 shrink-0 text-muted-foreground hover:text-destructive"
                            onClick={() => onDeleteTask(task.task_id, task.name)}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>Supprimer la tâche</TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </Card>
  )
}

// ── RoutineTab ────────────────────────────────────────────────────────────────

function RoutineTab({ routine, zones, operators, onRoutineChange }) {
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [newTaskOpen, setNewTaskOpen] = useState(false)
  const [newTaskZoneId, setNewTaskZoneId] = useState(null)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleting, setDeleting] = useState(false)
  const [editAssigneeTask, setEditAssigneeTask] = useState(null)

  const loadDetail = useCallback(async () => {
    setLoading(true)
    try {
      const d = await getCleaningRoutineDetail(token(), routine.id)
      setDetail(d)
    } catch {
      toast.error("Impossible de charger les tâches.")
    } finally {
      setLoading(false)
    }
  }, [routine.id])

  useEffect(() => { loadDetail() }, [loadDetail])

  function handleAddTask(zoneId) {
    setNewTaskZoneId(zoneId)
    setNewTaskOpen(true)
  }

  function handleTaskCreated() {
    setNewTaskOpen(false)
    loadDetail()
  }

  async function handleDeleteTask() {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await deleteCleaningTask(token(), deleteTarget.id)
      toast.success(`Tâche "${deleteTarget.name}" supprimée`)
      setDeleteTarget(null)
      loadDetail()
    } catch (err) {
      toast.error(String(err.message))
    } finally {
      setDeleting(false)
    }
  }

  // Zones that already have tasks in this routine
  const activeZoneIds = new Set(detail?.zones.map((z) => z.zone_id) ?? [])
  // Zones with no tasks yet in this routine
  const availableZones = zones.filter((z) => !activeZoneIds.has(z.id))

  return (
    <div className="space-y-4 pt-2">
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => <Skeleton key={i} className="h-16 rounded-xl" />)}
        </div>
      ) : (
        <>
          {/* Zones with tasks */}
          {detail?.zones.length === 0 && (
            <Card className="border-dashed">
              <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
                <SprayCan className="h-10 w-10 text-muted-foreground/40" />
                <div>
                  <p className="font-medium text-muted-foreground">Aucune tâche configurée</p>
                  <p className="text-sm text-muted-foreground">
                    Ajoutez des zones ci-dessous pour commencer.
                  </p>
                </div>
              </CardContent>
            </Card>
          )}

          {detail?.zones.map((zoneItem) => (
            <ZoneSection
              key={zoneItem.zone_id}
              zoneItem={zoneItem}
              operators={operators}
              onAddTask={handleAddTask}
              onDeleteTask={(id, name) => setDeleteTarget({ id, name })}
              onEditAssignee={setEditAssigneeTask}
            />
          ))}

          {/* Add zones not yet in this routine */}
          {availableZones.length > 0 && (
            <div className="rounded-xl border border-dashed p-4">
              <p className="mb-3 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Ajouter une zone à cette routine
              </p>
              <div className="flex flex-wrap gap-2">
                {availableZones.map((z) => (
                  <Button
                    key={z.id}
                    variant="outline"
                    size="sm"
                    className="gap-1.5 text-xs"
                    onClick={() => handleAddTask(z.id)}
                  >
                    <Plus className="h-3.5 w-3.5" />
                    {z.name}
                  </Button>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      <NewTaskDialog
        open={newTaskOpen}
        onClose={() => setNewTaskOpen(false)}
        onCreated={handleTaskCreated}
        routineId={routine.id}
        zones={zones}
        operators={operators}
        preselectedZoneId={newTaskZoneId}
      />

      <EditAssigneeDialog
        open={!!editAssigneeTask}
        onClose={() => setEditAssigneeTask(null)}
        task={editAssigneeTask}
        operators={operators}
        onSaved={loadDetail}
      />

      <AlertDialog open={!!deleteTarget} onOpenChange={(v) => !v && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer la tâche ?</AlertDialogTitle>
            <AlertDialogDescription>
              <strong>"{deleteTarget?.name}"</strong> sera définitivement retirée de cette
              routine. Les logs existants ne seront pas supprimés.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>Annuler</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteTask}
              disabled={deleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Supprimer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

// ── ZonesTab ──────────────────────────────────────────────────────────────────

function ZonesTab({ zones, onZoneDeleted }) {
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleting, setDeleting] = useState(false)

  async function handleDelete() {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await deleteCleaningZone(token(), deleteTarget.id)
      toast.success(`Zone "${deleteTarget.name}" supprimée`)
      onZoneDeleted(deleteTarget.id)
      setDeleteTarget(null)
    } catch (err) {
      toast.error(String(err.message))
    } finally {
      setDeleting(false)
    }
  }

  if (zones.length === 0) {
    return (
      <Card className="mt-2 border-dashed">
        <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
          <MapPin className="h-10 w-10 text-muted-foreground/40" />
          <div>
            <p className="font-medium text-muted-foreground">Aucune zone configurée</p>
            <p className="text-sm text-muted-foreground">
              Créez vos premières zones (ex. Cuisine chaude, Plonge…).
            </p>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <>
      <div className="mt-2 space-y-2">
        {zones.map((zone) => (
          <Card key={zone.id} className="flex items-center gap-3 px-5 py-3.5">
            <MapPin className="h-4 w-4 shrink-0 text-muted-foreground" />
            <span className="flex-1 text-sm font-medium">{zone.name}</span>
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-muted-foreground hover:text-destructive"
                    onClick={() => setDeleteTarget(zone)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Supprimer la zone</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </Card>
        ))}
      </div>

      <AlertDialog open={!!deleteTarget} onOpenChange={(v) => !v && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer la zone ?</AlertDialogTitle>
            <AlertDialogDescription>
              La zone <strong>"{deleteTarget?.name}"</strong> sera supprimée. Les tâches
              associées dans toutes les routines seront également retirées.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>Annuler</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={deleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Supprimer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function CleaningPlanPage() {
  const [routines, setRoutines] = useState([])
  const [zones, setZones] = useState([])
  const [operators, setOperators] = useState([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState("zones")

  // Dialogs
  const [newZoneOpen, setNewZoneOpen] = useState(false)
  const [newRoutineOpen, setNewRoutineOpen] = useState(false)
  const [deleteRoutineTarget, setDeleteRoutineTarget] = useState(null)
  const [deletingRoutine, setDeletingRoutine] = useState(false)

  useEffect(() => {
    const t = token()
    const ctx = loadEstablishmentContext()
    if (!t) return
    const usersPromise = ctx?.etablissement_id
      ? getEstablishmentUsers(t, ctx.etablissement_id, "SITE_EMPLOYEE").catch(() => [])
      : Promise.resolve([])
    Promise.all([getCleaningRoutines(t), getCleaningZones(t), usersPromise])
      .then(([r, z, usersData]) => {
        setRoutines(r.items ?? [])
        setZones(z.items ?? [])
        const list = Array.isArray(usersData) ? usersData : usersData?.items ?? []
        setOperators(list.filter((u) => u.is_active !== false))
        if ((r.items ?? []).length > 0) setActiveTab(r.items[0].id)
      })
      .catch(() => toast.error("Impossible de charger le plan sanitaire."))
      .finally(() => setLoading(false))
  }, [])

  async function handleDeleteRoutine() {
    if (!deleteRoutineTarget) return
    setDeletingRoutine(true)
    try {
      await deleteCleaningRoutine(token(), deleteRoutineTarget.id)
      toast.success(`Routine "${deleteRoutineTarget.name}" supprimée`)
      const updated = routines.filter((r) => r.id !== deleteRoutineTarget.id)
      setRoutines(updated)
      setActiveTab(updated.length > 0 ? updated[0].id : "zones")
      setDeleteRoutineTarget(null)
    } catch (err) {
      toast.error(String(err.message))
    } finally {
      setDeletingRoutine(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-4 p-1">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-5 w-96" />
        <div className="flex gap-2 pt-2">
          {[1, 2, 3].map((i) => <Skeleton key={i} className="h-9 w-32 rounded-md" />)}
        </div>
        <div className="space-y-3 pt-2">
          {[1, 2, 3].map((i) => <Skeleton key={i} className="h-16 rounded-xl" />)}
        </div>
      </div>
    )
  }

  return (
    <TooltipProvider>
      <div className="space-y-6">
        {/* ── Header ── */}
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold">Plan de Maîtrise Sanitaire</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Configurez les zones, les routines et les tâches de nettoyage & désinfection.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => setNewZoneOpen(true)}>
              <MapPin className="mr-1.5 h-4 w-4" />
              Nouvelle zone
            </Button>
            <Button size="sm" onClick={() => setNewRoutineOpen(true)}>
              <Plus className="mr-1.5 h-4 w-4" />
              Nouvelle routine
            </Button>
          </div>
        </div>

        {/* ── Stats strip ── */}
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: "Zones", value: zones.length, icon: MapPin },
            { label: "Routines", value: routines.length, icon: ClipboardList },
            {
              label: "Tâches totales",
              value: "—",
              icon: SprayCan,
              note: "comptées par routine",
            },
          ].map(({ label, value, icon: Icon, note }) => (
            <Card key={label} className="flex items-center gap-4 px-4 py-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
                <Icon className="h-4 w-4 text-primary" />
              </div>
              <div>
                <p className="text-2xl font-bold leading-none">{value}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">{label}</p>
              </div>
            </Card>
          ))}
        </div>

        {/* ── Main Tabs ── */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <div className="flex items-center gap-2">
            <ScrollArea className="flex-1">
              <TabsList className="inline-flex w-max gap-1">
                <TabsTrigger value="zones" className="gap-1.5">
                  <Layers className="h-3.5 w-3.5" />
                  Zones
                </TabsTrigger>
                {routines.map((r) => (
                  <div key={r.id} className="group relative flex items-center">
                    <TabsTrigger value={r.id} className="gap-1.5 pr-7">
                      <span
                        className={`h-2 w-2 rounded-full border ${SCHEDULE_COLORS[r.schedule_type]}`}
                      />
                      {r.name}
                    </TabsTrigger>
                    <Tooltip>
                      <TooltipTrigger
                        className="absolute right-1 hidden rounded p-0.5 hover:bg-destructive/20 group-hover:inline-flex"
                        onClick={(e) => {
                          e.stopPropagation()
                          setDeleteRoutineTarget(r)
                        }}
                      >
                        <Trash2 className="h-3 w-3 text-muted-foreground hover:text-destructive" />
                      </TooltipTrigger>
                      <TooltipContent>Supprimer la routine</TooltipContent>
                    </Tooltip>
                  </div>
                ))}
              </TabsList>
            </ScrollArea>
          </div>

          {/* Zones tab */}
          <TabsContent value="zones" className="mt-4">
            <div className="mb-3 flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                {zones.length} zone{zones.length !== 1 ? "s" : ""} disponible{zones.length !== 1 ? "s" : ""}
              </p>
              <Button variant="outline" size="sm" onClick={() => setNewZoneOpen(true)}>
                <Plus className="mr-1.5 h-3.5 w-3.5" />
                Ajouter
              </Button>
            </div>
            <ZonesTab
              zones={zones}
              onZoneDeleted={(id) => setZones((prev) => prev.filter((z) => z.id !== id))}
            />
          </TabsContent>

          {/* Routine tabs */}
          {routines.map((r) => (
            <TabsContent key={r.id} value={r.id} className="mt-4">
              <div className="mb-4 flex items-center gap-3">
                <Badge className={`border ${SCHEDULE_COLORS[r.schedule_type]}`}>
                  {SCHEDULE_LABELS[r.schedule_type]}
                </Badge>
                <span className="text-sm text-muted-foreground">{r.name}</span>
              </div>
              <RoutineTab routine={r} zones={zones} operators={operators} onRoutineChange={() => {}} />
            </TabsContent>
          ))}
        </Tabs>
      </div>

      {/* ── Global dialogs ── */}
      <NewZoneDialog
        open={newZoneOpen}
        onClose={() => setNewZoneOpen(false)}
        onCreated={(z) => {
          setZones((prev) => [...prev, z].sort((a, b) => a.name.localeCompare(b.name)))
          setNewZoneOpen(false)
        }}
      />

      <NewRoutineDialog
        open={newRoutineOpen}
        onClose={() => setNewRoutineOpen(false)}
        onCreated={(r) => {
          setRoutines((prev) => [...prev, r])
          setActiveTab(r.id)
          setNewRoutineOpen(false)
        }}
      />

      <AlertDialog
        open={!!deleteRoutineTarget}
        onOpenChange={(v) => !v && setDeleteRoutineTarget(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer la routine ?</AlertDialogTitle>
            <AlertDialogDescription>
              La routine <strong>"{deleteRoutineTarget?.name}"</strong> et toutes ses tâches
              seront définitivement supprimées. Les logs de nettoyage existants seront conservés.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deletingRoutine}>Annuler</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteRoutine}
              disabled={deletingRoutine}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deletingRoutine && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Supprimer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </TooltipProvider>
  )
}
