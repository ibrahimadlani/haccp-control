"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { ArrowLeft, Plus } from "lucide-react"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  createProductionBatch,
  createProductionStep,
  getProductionBatches,
  getProductionSteps,
} from "@/lib/api/production"
import { FoodTypeSelect } from "@/components/production/FoodTypeSelect"
import { STEP_LABELS, foodTypeLabel, foodTypeTarget } from "@/lib/production/constants"
import { useOperator } from "@/lib/contexts/OperatorContext"
import { useTimeclock } from "@/lib/contexts/TimeclockContext"
import { loadEstablishmentToken } from "@/lib/session/establishment"

const TODAY = new Date().toISOString().split("T")[0]

export default function OperatorProductionPage() {
  const router = useRouter()
  const { operator } = useOperator()
  const { status, enabled } = useTimeclock()
  const token = loadEstablishmentToken()

  const isActive = !enabled || status === "active"

  const [batches, setBatches] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedId, setSelectedId] = useState(null)
  const [steps, setSteps] = useState([])
  const [nomRecette, setNomRecette] = useState("")
  const [foodType, setFoodType] = useState("AUTRE")
  const [creating, setCreating] = useState(false)
  const [temperature, setTemperature] = useState("")
  const [savingStep, setSavingStep] = useState(false)

  function loadBatches() {
    if (!token) return
    setLoading(true)
    getProductionBatches(token)
      .then((res) => setBatches((res?.items ?? []).filter((b) => b.statut === "EN_COURS")))
      .catch(() => toast.error("Chargement impossible"))
      .finally(() => setLoading(false))
  }

  function loadSteps(batchId) {
    if (!token || !batchId) return
    getProductionSteps(token, batchId)
      .then((res) => setSteps(res?.items ?? []))
      .catch(() => toast.error("Impossible de charger les étapes"))
  }

  useEffect(loadBatches, [])

  useEffect(() => {
    if (selectedId) loadSteps(selectedId)
    else setSteps([])
  }, [selectedId])

  async function handleCreateBatch(e) {
    e.preventDefault()
    if (!nomRecette.trim()) return
    setCreating(true)
    try {
      const batch = await createProductionBatch(token, {
        nom_recette: nomRecette.trim(),
        food_type: foodType,
        date_production: TODAY,
      })
      toast.success("Lot créé")
      setNomRecette("")
      setFoodType("AUTRE")
      loadBatches()
      setSelectedId(batch.id)
    } catch (err) {
      toast.error(String(err.message))
    } finally {
      setCreating(false)
    }
  }

  async function handleAddStep(stepType) {
    if (!selectedId || temperature === "" || !operator?.id) return
    setSavingStep(true)
    try {
      await createProductionStep(token, selectedId, {
        step_type: stepType,
        temperature_mesuree: parseFloat(temperature),
        operator_id: operator.id,
      })
      toast.success(`${STEP_LABELS[stepType]} enregistrée`)
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
    <div className="mx-auto max-w-lg space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => router.push("/operator")}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-2xl font-semibold">Production</h1>
          <p className="text-sm text-muted-foreground">Relevés cuisson et refroidissement</p>
        </div>
      </div>

      {!isActive ? (
        <p className="text-sm text-muted-foreground">
          Pointez votre arrivée pour accéder à cette fonctionnalité.
        </p>
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Nouveau lot</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-1.5">
                <Label htmlFor="op-nom-recette">Nom de la recette</Label>
                <Input
                  id="op-nom-recette"
                  value={nomRecette}
                  onChange={(e) => setNomRecette(e.target.value)}
                  placeholder="Ex. Poulet rôti"
                  required
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="op-food-type">Type d&apos;aliment</Label>
                <FoodTypeSelect
                  id="op-food-type"
                  value={foodType}
                  onChange={setFoodType}
                />
                <p className="text-xs text-muted-foreground">
                  Cuisson à cœur : {foodTypeTarget(foodType)}°C minimum
                </p>
              </div>
              <Button type="button" className="w-full" disabled={creating || !nomRecette.trim()} onClick={handleCreateBatch}>
                <Plus className="mr-2 h-4 w-4" />
                {creating ? "Création…" : "Créer le lot"}
              </Button>
            </CardContent>
          </Card>

          <div className="space-y-2">
            <p className="text-sm font-medium">Lots en cours</p>
            {loading ? (
              <p className="text-sm text-muted-foreground">Chargement…</p>
            ) : batches.length === 0 ? (
              <p className="text-sm text-muted-foreground">Aucun lot en cours</p>
            ) : (
              <div className="grid gap-2">
                {batches.map((batch) => (
                  <Button
                    key={batch.id}
                    variant={selectedId === batch.id ? "default" : "outline"}
                    className="h-auto justify-start py-3"
                    onClick={() => setSelectedId(batch.id)}
                  >
                    <span className="text-left">
                      <span className="block font-medium">{batch.nom_recette}</span>
                      <span className="block text-xs opacity-80">
                        {foodTypeLabel(batch.food_type)} · {batch.date_production}
                      </span>
                    </span>
                  </Button>
                ))}
              </div>
            )}
          </div>

          {selectedBatch && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">{selectedBatch.nom_recette}</CardTitle>
                <Badge variant="secondary" className="w-fit">
                  {foodTypeLabel(selectedFoodType)}
                </Badge>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-sm text-muted-foreground">
                  Seuil cuisson : <strong>{foodTypeTarget(selectedFoodType)}°C</strong>
                </p>
                <div className="space-y-1.5">
                  <Label htmlFor="op-temp">Température mesurée (°C)</Label>
                  <Input
                    id="op-temp"
                    type="number"
                    step="0.1"
                    value={temperature}
                    onChange={(e) => setTemperature(e.target.value)}
                  />
                </div>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                  <Button
                    onClick={() => handleAddStep("CUISSON_A_COEUR")}
                    disabled={savingStep || temperature === ""}
                  >
                    Cuisson
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => handleAddStep("REFROIDISSEMENT_DEBUT")}
                    disabled={savingStep || temperature === ""}
                  >
                    Ref. début
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => handleAddStep("REFROIDISSEMENT_FIN")}
                    disabled={savingStep || temperature === ""}
                  >
                    Ref. fin
                  </Button>
                </div>

                {steps.length > 0 && (
                  <div className="space-y-2 border-t pt-4">
                    <p className="text-sm font-medium">Étapes enregistrées</p>
                    {steps.map((step) => (
                      <div
                        key={step.id}
                        className="flex items-center justify-between text-sm"
                      >
                        <span>{STEP_LABELS[step.step_type] ?? step.step_type}</span>
                        <Badge variant="secondary">{step.temperature_mesuree} °C</Badge>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  )
}
