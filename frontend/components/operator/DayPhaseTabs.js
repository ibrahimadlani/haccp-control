"use client"

import { Moon, Sun, UtensilsCrossed } from "lucide-react"
import { cn } from "@/lib/utils"
import { DAY_PHASES, listDayPhases, isPhaseSuggested } from "@/lib/operator/canteenDay"

const ICONS = {
  [DAY_PHASES.MORNING]: Sun,
  [DAY_PHASES.SERVICE]: UtensilsCrossed,
  [DAY_PHASES.CLOSING]: Moon,
}

export function DayPhaseTabs({ value, onChange }) {
  const phases = listDayPhases()

  return (
    <nav
      className="grid grid-cols-3 gap-2 rounded-xl border bg-muted/30 p-1"
      aria-label="Étapes de la journée en cuisine"
    >
      {phases.map((phase) => {
        const Icon = ICONS[phase.id]
        const active = value === phase.id
        const suggested = isPhaseSuggested(phase.id)

        return (
          <button
            key={phase.id}
            type="button"
            onClick={() => onChange(phase.id)}
            className={cn(
              "relative flex flex-col items-center gap-1 rounded-lg px-2 py-3 text-center transition-colors",
              active
                ? "bg-background shadow-sm ring-1 ring-primary/20"
                : "text-muted-foreground hover:bg-background/60",
            )}
          >
            {suggested && !active && (
              <span className="absolute right-2 top-2 h-2 w-2 rounded-full bg-primary" aria-hidden />
            )}
            <Icon className={cn("h-5 w-5", active && "text-primary")} />
            <span className={cn("text-xs font-semibold leading-tight", active && "text-foreground")}>
              {phase.shortLabel}
            </span>
            <span className="hidden text-[10px] leading-tight text-muted-foreground sm:block">
              {phase.label}
            </span>
          </button>
        )
      })}
    </nav>
  )
}
