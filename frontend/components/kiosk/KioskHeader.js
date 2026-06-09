"use client"

import { Coffee, Loader2, LogIn, LogOut, PlayCircle, UserRound } from "lucide-react"
import { useRouter } from "next/navigation"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { useTimeclock } from "@/lib/contexts/TimeclockContext"
import { useOperator } from "@/lib/contexts/OperatorContext"
import { loadEstablishmentContext } from "@/lib/session/establishment"

const STATUS_DOT = {
  active: "bg-emerald-400",
  on_break: "bg-amber-400",
  clocked_out: "bg-slate-500",
}

const REDIRECT_ON_EVENT = {
  CLOCK_OUT: "Départ enregistré — à bientôt !",
  BREAK_START: "Bonne pause !",
}

const ACTIONS_BY_STATUS = {
  clocked_out: [{ type: "CLOCK_IN", label: "Arrivée", icon: LogIn }],
  active: [
    { type: "BREAK_START", label: "Pause", icon: Coffee },
    { type: "CLOCK_OUT", label: "Partir", icon: LogOut },
  ],
  on_break: [
    { type: "BREAK_END", label: "Reprendre", icon: PlayCircle },
    { type: "CLOCK_OUT", label: "Partir", icon: LogOut },
  ],
}

export function KioskHeader() {
  const router = useRouter()
  const { operator, clearOperator } = useOperator()
  const timeclock = useTimeclock()
  const ctx = loadEstablishmentContext()
  const siteName = ctx?.nom_site ?? "Établissement"

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

  function handleSwitchUser() {
    clearOperator()
    router.replace("/profiles")
  }

  const showTimeclock = timeclock?.enabled && !timeclock?.initializing
  const actions = showTimeclock ? (ACTIONS_BY_STATUS[timeclock.status] ?? []) : []
  const dotColor = STATUS_DOT[timeclock?.status] ?? STATUS_DOT.clocked_out

  return (
    <header className="kiosk-header shrink-0 border-b border-slate-700 bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 text-white shadow-lg">
      <div className="flex min-h-[4.5rem] items-center gap-3 px-4 py-3 sm:px-6">
        <div className="min-w-0 flex-1">
          <p className="text-[1.2rem] font-bold leading-tight tracking-tight sm:text-[1.35rem]">
            {siteName}
          </p>
          <p className="text-sm text-slate-300">smartHACCP · Tablette cuisine</p>
        </div>

        <div className="flex items-center gap-2 sm:gap-3">
          {showTimeclock && actions.length > 0 && (
            <div className="hidden items-center gap-1.5 sm:flex">
              {actions.map(({ type, label, icon: Icon }) => (
                <Button
                  key={type}
                  type="button"
                  variant="secondary"
                  size="sm"
                  className="h-10 gap-1.5 border-slate-600 bg-slate-700 px-3 text-[1rem] text-white hover:bg-slate-600"
                  onClick={() => handleTimeclockEvent(type)}
                  disabled={timeclock.actionLoading !== null}
                >
                  {timeclock.actionLoading === type ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Icon className="h-4 w-4" />
                  )}
                  {label}
                </Button>
              ))}
            </div>
          )}

          {operator?.name && (
            <div className="flex max-w-[10rem] items-center gap-2 rounded-xl border border-slate-600 bg-slate-800/80 px-3 py-2 sm:max-w-none">
              {showTimeclock && (
                <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${dotColor}`} />
              )}
              <UserRound className="h-5 w-5 shrink-0 text-slate-300" />
              <span className="truncate text-[1.1rem] font-semibold">{operator.name}</span>
            </div>
          )}

          <Button
            type="button"
            variant="secondary"
            className="h-11 min-w-[7rem] border-slate-500 bg-slate-700 text-[1.05rem] font-semibold text-white hover:bg-slate-600"
            onClick={handleSwitchUser}
          >
            Changer PIN
          </Button>
        </div>
      </div>
    </header>
  )
}
