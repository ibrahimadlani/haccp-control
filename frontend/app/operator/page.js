"use client"

import { Suspense, useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import {
  Droplets,
  PackageSearch,
  ShieldAlert,
  Snowflake,
  SprayCan,
  Tag,
  Thermometer,
  UtensilsCrossed,
} from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { ColdChainQuickRecord } from "@/components/operator/ColdChainQuickRecord"
import { AllergenBoard } from "@/components/operator/AllergenBoard"
import { CookingQuickRecord } from "@/components/operator/CookingQuickRecord"
import { OilChangeForm } from "@/components/operator/OilChangeForm"
import { OpenedProductLabelForm } from "@/components/operator/OpenedProductLabelForm"
import { WitnessSampleForm } from "@/components/operator/WitnessSampleForm"
import { DayPhaseTabs } from "@/components/operator/DayPhaseTabs"
import { OperatorActionCard } from "@/components/operator/OperatorActionCard"
import { TemperatureRecordModal } from "@/components/haccp/TemperatureRecordModal"
import { useEstablishmentFeatures } from "@/lib/hooks/useEstablishmentFeatures"
import {
  DAY_PHASES,
  getSuggestedDayPhase,
  PHASE_META,
} from "@/lib/operator/canteenDay"
import { useTimeclock } from "@/lib/contexts/TimeclockContext"
import { useOperator } from "@/lib/contexts/OperatorContext"

function PhaseHint({ phase }) {
  const meta = PHASE_META[phase]
  const suggested = getSuggestedDayPhase() === phase

  return (
    <Alert className={suggested ? "border-primary/30 bg-primary/5" : ""}>
      <AlertDescription className="text-sm">
        <span className="font-medium">{meta.subtitle}</span>
        {" — "}
        {meta.hint}
        {suggested ? " · Étape suggérée maintenant" : ""}
      </AlertDescription>
    </Alert>
  )
}

function MorningStep({ isActive, features, onColdOpen, onTempOpen, router }) {
  return (
    <div className="space-y-4">
      <PhaseHint phase={DAY_PHASES.MORNING} />

      {features.temperatureEnabled && (
        <OperatorActionCard
          icon={Snowflake}
          title="Mes frigos & congélateurs"
          description="Relevé matinal de toutes les enceintes froides — pavé numérique grand format, en 2 clics."
          badge="Priorité matin"
          onClick={onColdOpen}
          disabled={!isActive}
        />
      )}

      {features.temperatureEnabled && (
        <OperatorActionCard
          icon={Thermometer}
          title="Autre relevé de température"
          description="Équipement ponctuel hors tournée matinale."
          variant="outline"
          onClick={onTempOpen}
          disabled={!isActive}
        />
      )}

      {features.receptionsEnabled && (
        <OperatorActionCard
          icon={PackageSearch}
          title="Arrivée des marchandises"
          description="Réception fournisseur, température livraison, lot et conformité."
          onClick={() => router.push("/operator/reception")}
          disabled={!isActive}
        />
      )}

    </div>
  )
}

function ServiceStep({
  isActive,
  features,
  onCookingOpen,
  onOilOpen,
  onLabelOpen,
  onAllergenOpen,
}) {
  return (
    <div className="space-y-4">
      <PhaseHint phase={DAY_PHASES.SERVICE} />

      {features.temperatureEnabled && (
        <OperatorActionCard
          icon={Thermometer}
          title="Température des plats (sonde)"
          description="Relevé à cœur en cuisson (≥63°C) et maintien au chaud au self."
          badge="Service"
          onClick={onCookingOpen}
          disabled={!isActive}
        />
      )}

      <OperatorActionCard
        icon={Droplets}
        title="Changement d'huile — friteuses"
        description="Filtration avec témoin polaire ou changement complet d'huile."
        onClick={onOilOpen}
        disabled={!isActive}
      />

      <OperatorActionCard
        icon={Tag}
        title="Ouverture produit & étiquettes DLC"
        description="DLC secondaire après ouverture — frigo positif, négatif ou ambiant."
        onClick={onLabelOpen}
        disabled={!isActive}
      />

      <OperatorActionCard
        icon={ShieldAlert}
        title="Tableau des allergènes"
        description="Consultation des 14 allergènes sur les plats du jour."
        onClick={onAllergenOpen}
        disabled={!isActive}
      />

      {!isActive && (
        <p className="text-center text-sm text-muted-foreground">
          Pointez votre arrivée pour accéder aux actions de service.
        </p>
      )}
    </div>
  )
}

function ClosingStep({ isActive, features, router, onWitnessOpen }) {
  return (
    <div className="space-y-4">
      <PhaseHint phase={DAY_PHASES.CLOSING} />

      {features.cleaningEnabled && (
        <OperatorActionCard
          icon={SprayCan}
          title="Ménage & plan de nettoyage"
          description="Routine de fermeture — sols, surfaces, plonge et zones HACCP."
          badge="Fin de service"
          onClick={() => router.push("/operator/cleaning")}
          disabled={!isActive}
        />
      )}

      {features.temperatureEnabled && (
        <OperatorActionCard
          icon={UtensilsCrossed}
          title="Plats témoins"
          description="Échantillons conservés 5 jours au frais — obligation restauration collective."
          badge="Fin de service"
          onClick={onWitnessOpen}
          disabled={!isActive}
        />
      )}
    </div>
  )
}

function OperatorJourneePage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { operator } = useOperator()
  const { status, enabled: timeclockEnabled } = useTimeclock()
  const features = useEstablishmentFeatures()

  const [phase, setPhase] = useState(DAY_PHASES.MORNING)
  const [coldOpen, setColdOpen] = useState(false)
  const [tempOpen, setTempOpen] = useState(false)
  const [cookingOpen, setCookingOpen] = useState(false)
  const [oilOpen, setOilOpen] = useState(false)
  const [labelOpen, setLabelOpen] = useState(false)
  const [allergenOpen, setAllergenOpen] = useState(false)
  const [witnessOpen, setWitnessOpen] = useState(false)

  const firstName = operator?.name?.split(" ")[0] ?? "Opérateur"
  const isActive = !timeclockEnabled || status === "active"

  useEffect(() => {
    const fromUrl = searchParams.get("phase")
    if (fromUrl && PHASE_META[fromUrl]) {
      setPhase(fromUrl)
      return
    }
    setPhase(getSuggestedDayPhase())
  }, [searchParams])

  function handlePhaseChange(next) {
    setPhase(next)
    router.replace(`/operator?phase=${next}`, { scroll: false })
  }

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-5 pb-4">
      <header className="space-y-1">
        <p className="text-sm font-medium text-primary">smartHACCP · Cantine</p>
        <h1 className="text-2xl font-semibold tracking-tight">Ma journée en cuisine</h1>
        <p className="text-muted-foreground">Bonjour {firstName}</p>
      </header>

      {!isActive && timeclockEnabled && (
        <Alert variant="destructive">
          <AlertDescription>
            Pointez votre arrivée en haut de l&apos;écran pour débloquer les actions terrain.
          </AlertDescription>
        </Alert>
      )}

      <DayPhaseTabs value={phase} onChange={handlePhaseChange} />

      {phase === DAY_PHASES.MORNING && (
        <MorningStep
          isActive={isActive}
          features={features}
          onColdOpen={() => setColdOpen(true)}
          onTempOpen={() => setTempOpen(true)}
          router={router}
        />
      )}

      {phase === DAY_PHASES.SERVICE && (
        <ServiceStep
          isActive={isActive}
          features={features}
          onCookingOpen={() => setCookingOpen(true)}
          onOilOpen={() => setOilOpen(true)}
          onLabelOpen={() => setLabelOpen(true)}
          onAllergenOpen={() => setAllergenOpen(true)}
        />
      )}

      {phase === DAY_PHASES.CLOSING && (
        <ClosingStep
          isActive={isActive}
          features={features}
          router={router}
          onWitnessOpen={() => setWitnessOpen(true)}
        />
      )}

      <ColdChainQuickRecord open={coldOpen} onOpenChange={setColdOpen} />
      <TemperatureRecordModal open={tempOpen} onOpenChange={setTempOpen} />
      <CookingQuickRecord open={cookingOpen} onOpenChange={setCookingOpen} />
      <OilChangeForm open={oilOpen} onOpenChange={setOilOpen} />
      <OpenedProductLabelForm open={labelOpen} onOpenChange={setLabelOpen} />
      <AllergenBoard open={allergenOpen} onOpenChange={setAllergenOpen} />
      <WitnessSampleForm open={witnessOpen} onOpenChange={setWitnessOpen} />
    </div>
  )
}

export default function OperatorPage() {
  return (
    <Suspense
      fallback={
        <div className="flex justify-center py-16 text-sm text-muted-foreground">
          Chargement de votre journée…
        </div>
      }
    >
      <OperatorJourneePage />
    </Suspense>
  )
}
