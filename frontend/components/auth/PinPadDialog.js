"use client"

import { useEffect, useState } from "react"
import { Loader2 } from "lucide-react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { PinPad } from "./PinPad"

export function PinPadDialog({ open, onOpenChange, title, description, onComplete, loading }) {
  const [pin, setPin] = useState("")

  useEffect(() => {
    if (!open) setPin("")
  }, [open])

  function handleDigit(digit) {
    setPin((prev) => {
      const next = prev + digit
      if (next.length === 4) {
        setTimeout(() => onComplete(next), 100)
      }
      return next
    })
  }

  function handleClear() {
    setPin((prev) => prev.slice(0, -1))
  }

  return (
    <Dialog open={open} onOpenChange={loading ? undefined : onOpenChange}>
      <DialogContent className="max-w-xs">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>
        {loading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <PinPad pin={pin} onDigit={handleDigit} onClear={handleClear} disabled={loading} />
        )}
      </DialogContent>
    </Dialog>
  )
}
