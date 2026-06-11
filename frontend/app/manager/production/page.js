"use client"

import { useEffect, useState } from "react"
import { Plus } from "lucide-react"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { PageHeader } from "@/components/shared/PageHeader"
import {
  createProductionBatch,
  createProductionStep,
  getProductionBatches,
  getProductionSteps,
} from "@/lib/api/production"
import { getEstablishmentUsers } from "@/lib/api/auth"
import { FoodTypeSelect } from "@/components/production/FoodTypeSelect"
import { STEP_LABELS, foodTypeLabel, foodTypeTarget } from "@/lib/production/constants"
import { loadEstablishmentContext, loadEstablishmentToken } from "@/lib/session/establishment"

const STATUT_LABELS = {
  EN_COURS: "En cours",
  TERMINE: "Terminé",
}

const TODAY = new Date().toISOString().split("T")[0]

export default function ProductionPage() {
  const token = loadEstablishmentToken()
  const establishmentId = loadEstablishmentContext()?.etablissement_id

  const [batches, setBatches] = useState([])
  const [operators, setOperators] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedId, setSelectedId] = useState(null)
  const [steps, setSteps] = useState([])
  const [stepsLoading, setStepsLoading] = useState(false)

  const [batchDialogOpen, setBatchDialogOpen] = useState(false)
  const [nomRecette, setNomRecette] = useState("")
  const [foodType, setFoodType] = useState("AUTRE")
  const [dateProduction, setDateProduction] = useState(TODAY)
  const [savingBatch, setSavingBatch] = useState(false)

  const [stepType, setStepType] = useState("CUISSON_A_COEUR")
  const [temperature, setTemperature] = useState("")
  const [operatorId, setOperatorId] = useState("")
  const [savingStep, setSavingStep] = useState(false)

  function loadBatches() {
    if (!token) return
    setLoading(true)
    getProductionBatches(token)
      .then((res) => setBatches(res?.items ?? []))
      .catch(() => toast.error("Impossible de charger les productions"))
      .finally(() => setLoading(false))
  }

  function loadSteps(batchId) {
    if (!token || !batchId) return
    setStepsLoading(true)
    getProductionSteps(token, batchId)
      .then((res) => setSteps(res?.items ?? []))
      .catch(() => toast.error("Impossible de charger les étapes"))
      .finally(() => setStepsLoading(false))
  }

  useEffect(() => {
    loadBatches()
    if (!token || !establishmentId) return
    getEstablishmentUsers(token, establishmentId)
      .then((res) => {
        const list = Array.isArray(res) ? res : res?.items ?? []
        setOperators(list.filter((u) => u.is_active !== false))
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (selectedId) loadSteps(selectedId)
    else setSteps([])
  }, [selectedId])

  function openBatchDialog() {
    setNomRecette("")
    setFoodType("AUTRE")
    setDateProduction(TODAY)
    setBatchDialogOpen(true)
  }

  async function handleCreateBatch(e) {
    e.preventDefault()
    if (!nomRecette.trim()) return
    setSavingBatch(true)
    try {
      const batch = await createProductionBatch(token, {
        nom_recette: nomRecette.trim(),
        food_type: foodType,
        date_production: dateProduction,
      })
      toast.success("Production créée")
      setBatchDialogOpen(false)
      loadBatches()
      setSelectedId(batch.id)
    } catch (err) {
      toast.error(String(err.message))
    } finally {
      setSavingBatch(false)
    }
  }

  async function handleCreateStep(e) {
    e.preventDefault()
    if (!selectedId || !operatorId || temperature === "") return
    setSavingStep(true)
    try {
      await createProductionStep(token, selectedId, {
        step_type: stepType,
        temperature_mesuree: parseFloat(temperature),
        operator_id: operatorId,
      })
      toast.success("Étape enregistrée")
      setTemperature("")
      loadSteps(selectedId)
    } catch (err) {
      toast.error(String(err.message))
    } finally {
      setSavingStep(false)
    }
  }

  const selectedBatch = batches.find((b) => b.id === selectedId)
  const selectedFoodType = selectedBatch?.food_type ?? "AUTRE"

  return (
    <div className="space-y-6">
      <PageHeader
        title="Production"
        description="Suivez les lots de production et leurs relevés de température."
      >
        <Button onClick={openBatchDialog}>
          <Plus className="mr-2 h-4 w-4" />
          Nouveau lot
        </Button>
      </PageHeader>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Recette</TableHead>
              <TableHead>Type d&apos;aliment</TableHead>
              <TableHead>Date</TableHead>
              <TableHead>Statut</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={4} className="text-muted-foreground">
                  Chargement…
                </TableCell>
              </TableRow>
            ) : batches.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} className="text-muted-foreground">
                  Aucun lot de production
                </TableCell>
              </TableRow>
            ) : (
              batches.map((batch) => (
                <TableRow
                  key={batch.id}
                  className={selectedId === batch.id ? "bg-muted/50" : "cursor-pointer"}
                  onClick={() => setSelectedId(batch.id)}
                >
                  <TableCell className="font-medium">{batch.nom_recette}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{foodTypeLabel(batch.food_type)}</Badge>
                  </TableCell>
                  <TableCell>{batch.date_production}</TableCell>
                  <TableCell>
                    <Badge variant={batch.statut === "EN_COURS" ? "default" : "secondary"}>
                      {STATUT_LABELS[batch.statut] ?? batch.statut}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {selectedBatch && (
        <div className="space-y-4 rounded-lg border p-4">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <h2 className="text-lg font-semibold">{selectedBatch.nom_recette}</h2>
              <p className="text-sm text-muted-foreground">
                Production du {selectedBatch.date_production}
              </p>
            </div>
            <Badge>{foodTypeLabel(selectedFoodType)}</Badge>
          </div>

          {stepType === "CUISSON_A_COEUR" && (
            <p className="text-sm text-muted-foreground">
              Seuil cuisson HACCP pour ce lot :{" "}
              <strong>{foodTypeTarget(selectedFoodType)}°C minimum</strong>
            </p>
          )}

          <form onSubmit={handleCreateStep} className="grid gap-3 sm:grid-cols-4">
            <div className="space-y-1.5">
              <Label>Étape</Label>
              <Select value={stepType} onValueChange={setStepType}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="CUISSON_A_COEUR">Cuisson à cœur</SelectItem>
                  <SelectItem value="REFROIDISSEMENT_DEBUT">Refroidissement — début</SelectItem>
                  <SelectItem value="REFROIDISSEMENT_FIN">Refroidissement — fin</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="temp">Température (°C)</Label>
              <Input
                id="temp"
                type="number"
                step="0.1"
                value={temperature}
                onChange={(e) => setTemperature(e.target.value)}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label>Opérateur</Label>
              <Select value={operatorId} onValueChange={setOperatorId}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Sélectionner" />
                </SelectTrigger>
                <SelectContent>
                  {operators.map((op) => (
                    <SelectItem key={op.id} value={op.id}>
                      {(op.prenom ?? op.first_name ?? "")} {(op.nom ?? op.last_name ?? "")}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-end">
              <Button type="submit" disabled={savingStep || !operatorId}>
                {savingStep ? "Enregistrement…" : "Ajouter l'étape"}
              </Button>
            </div>
          </form>

          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Étape</TableHead>
                  <TableHead>Température</TableHead>
                  <TableHead>Horodatage</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {stepsLoading ? (
                  <TableRow>
                    <TableCell colSpan={3} className="text-muted-foreground">
                      Chargement…
                    </TableCell>
                  </TableRow>
                ) : steps.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={3} className="text-muted-foreground">
                      Aucune étape enregistrée
                    </TableCell>
                  </TableRow>
                ) : (
                  steps.map((step) => (
                    <TableRow key={step.id}>
                      <TableCell>{STEP_LABELS[step.step_type] ?? step.step_type}</TableCell>
                      <TableCell>{step.temperature_mesuree} °C</TableCell>
                      <TableCell>
                        {new Date(step.timestamp).toLocaleString("fr-FR")}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </div>
      )}

      <Dialog open={batchDialogOpen} onOpenChange={setBatchDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Nouveau lot de production</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreateBatch} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="nom-recette">Nom de la recette</Label>
              <Input
                id="nom-recette"
                value={nomRecette}
                onChange={(e) => setNomRecette(e.target.value)}
                placeholder="Ex. Soupe du jour"
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="food-type">Type d&apos;aliment</Label>
              <FoodTypeSelect
                id="food-type"
                value={foodType}
                onChange={setFoodType}
              />
              <p className="text-xs text-muted-foreground">
                Détermine le seuil de cuisson HACCP ({foodTypeTarget(foodType)}°C pour ce type).
              </p>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="date-production">Date de production</Label>
              <Input
                id="date-production"
                type="date"
                value={dateProduction}
                onChange={(e) => setDateProduction(e.target.value)}
                required
              />
            </div>
            <Button type="submit" className="w-full" disabled={savingBatch}>
              {savingBatch ? "Création…" : "Créer"}
            </Button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
