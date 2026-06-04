"use client"

import { Coffee, Loader2, LogIn, LogOut, PlayCircle, Thermometer, X } from "lucide-react"
import { useRouter } from "next/navigation"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { useTimeclock } from "@/lib/contexts/TimeclockContext"
import { useOperator } from "@/lib/contexts/OperatorContext"
import { clearAllDeviceStorage, loadEstablishmentContext } from "@/lib/session/establishment"

const STATUS_DOT = {
  active: "bg-green-500",
  on_break: "bg-yellow-400",
  clocked_out: "bg-gray-300",
}

const REDIRECT_ON_EVENT = {
  CLOCK_OUT: "Départ enregistré — à bientôt !",
  BREAK_START: "Bonne pause !",
}

const ACTIONS_BY_STATUS = {
  clocked_out: [
    { type: "CLOCK_IN", label: "Arrivée", icon: LogIn, variant: "default" },
  ],
  active: [
    { type: "BREAK_START", label: "Pause", icon: Coffee, variant: "outline" },
    { type: "CLOCK_OUT", label: "Partir", icon: LogOut, variant: "ghost" },
  ],
  on_break: [
    { type: "BREAK_END", label: "Reprendre", icon: PlayCircle, variant: "default" },
    { type: "CLOCK_OUT", label: "Partir", icon: LogOut, variant: "ghost" },
  ],
}

export function DeviceHeader() {
  const router = useRouter()
  const { operator, clearOperator } = useOperator()
  const timeclock = useTimeclock()
  const ctx = loadEstablishmentContext()
  const siteName = ctx?.nom_site ?? "Établissement"

  function handleExit() {
    if (operator) {
      // Operateur connecté → retour à la sélection de profil
      clearOperator()
      router.replace("/profiles")
    } else {
      // Page profils (aucun opérateur) → déconnexion établissement
      clearOperator()
      clearAllDeviceStorage()
      router.replace("/login")
    }
  }

  async function handleTimeclockEvent(type) {
    const success = await timeclock.handleEvent(type)
    if (!success) return
    const message = REDIRECT_ON_EVENT[type]
    if (message) {
      toast.success(message)
      clearOperator()
      router.replace("/profiles")
    }
  }

  const operatorName = operator?.name ?? null
  const showTimeclock = timeclock?.enabled && !timeclock?.initializing
  const actions = showTimeclock ? (ACTIONS_BY_STATUS[timeclock.status] ?? []) : []
  const dotColor = STATUS_DOT[timeclock?.status] ?? STATUS_DOT.clocked_out

  return (
    <header className="border-b bg-background">
      <div className="relative flex h-14 items-center gap-3 px-4">
        <Thermometer className="h-5 w-5 text-primary" />
        <span className="font-semibold">HACCP</span>

        <span className="absolute left-1/2 -translate-x-1/2 text-sm font-medium">{siteName}</span>

        <div className="ml-auto flex items-center gap-2">
          {showTimeclock && actions.length > 0 && (
            <div className="flex items-center gap-1">
              {actions.map(({ type, label, icon: Icon, variant }) => (
                <Button
                  key={type}
                  variant={variant}
                  size="sm"
                  className="h-7 gap-1.5 px-2.5 text-xs"
                  onClick={() => handleTimeclockEvent(type)}
                  disabled={timeclock.actionLoading !== null}
                >
                  {timeclock.actionLoading === type ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Icon className="h-3.5 w-3.5" />
                  )}
                  <span className="hidden sm:inline">{label}</span>
                </Button>
              ))}
            </div>
          )}

          {operatorName && (
            <Badge variant="secondary" className="hidden sm:flex items-center gap-1.5">
              {showTimeclock && (
                <span className={`h-2 w-2 rounded-full flex-shrink-0 ${dotColor}`} />
              )}
              {operatorName}
            </Badge>
          )}

          <Button
            variant="ghost"
            size="icon"
            onClick={handleExit}
            aria-label={operator ? "Changer de profil" : "Déconnecter l'établissement"}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </header>
  )
}
