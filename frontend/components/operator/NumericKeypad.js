"use client"

import { Delete } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

const KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "-", "0", ".", "del"]

export function NumericKeypad({ value, onChange, disabled, allowNegative = true, allowDecimal = true }) {
  function handleKey(key) {
    if (disabled) return

    if (key === "del") {
      onChange(value.slice(0, -1))
      return
    }

    if (key === "-" && !allowNegative) return
    if (key === "." && !allowDecimal) return
    if (key === "-" && value.includes("-")) return
    if (key === "." && value.includes(".")) return
    if (key === "-" && value.length > 0) return

    onChange(`${value}${key}`)
  }

  return (
    <div className="grid grid-cols-3 gap-2">
      {KEYS.map((key) => {
        if (key === "del") {
          return (
            <Button
              key={key}
              type="button"
              variant="ghost"
              className="col-span-3 h-14 text-base"
              onClick={() => handleKey(key)}
              disabled={disabled || value.length === 0}
              aria-label="Effacer"
            >
              <Delete className="mr-2 h-5 w-5" />
              Effacer
            </Button>
          )
        }

        const hidden =
          (key === "-" && !allowNegative) || (key === "." && !allowDecimal)

        if (hidden) {
          return <div key={key} />
        }

        return (
          <Button
            key={key}
            type="button"
            variant="outline"
            className={cn("h-16 text-2xl font-semibold tabular-nums", key === "-" && "text-lg")}
            onClick={() => handleKey(key)}
            disabled={disabled}
          >
            {key}
          </Button>
        )
      })}
    </div>
  )
}
