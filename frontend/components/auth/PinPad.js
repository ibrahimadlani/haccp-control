"use client"

import { Delete } from "lucide-react"
import { Button } from "@/components/ui/button"

const DIGITS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "", "0", "del"]

export function PinPad({ pin, onDigit, onClear, disabled }) {
  return (
    <div className="space-y-4">
      {/* PIN indicator dots */}
      <div className="flex justify-center gap-3">
        {[0, 1, 2, 3].map((i) => (
          <div
            key={i}
            className={`h-3 w-3 rounded-full border-2 transition-colors ${
              i < pin.length
                ? "border-primary bg-primary"
                : "border-muted-foreground bg-transparent"
            }`}
          />
        ))}
      </div>

      {/* Keypad */}
      <div className="grid grid-cols-3 gap-2">
        {DIGITS.map((digit, idx) => {
          if (digit === "") return <div key={idx} />
          if (digit === "del") {
            return (
              <Button
                key={idx}
                variant="ghost"
                size="lg"
                onClick={onClear}
                disabled={disabled || pin.length === 0}
                className="h-14 text-muted-foreground"
                aria-label="Effacer"
              >
                <Delete className="h-5 w-5" />
              </Button>
            )
          }
          return (
            <Button
              key={idx}
              variant="outline"
              size="lg"
              onClick={() => onDigit(digit)}
              disabled={disabled || pin.length >= 4}
              className="h-14 text-lg font-medium"
            >
              {digit}
            </Button>
          )
        })}
      </div>
    </div>
  )
}
