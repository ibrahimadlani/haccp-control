"use client"

import { useCallback, useEffect, useState } from "react"
import { loadEstablishmentId } from "@/lib/session/establishment"

function storageKey() {
  const siteId = loadEstablishmentId() ?? "default"
  const today = new Date().toISOString().split("T")[0]
  return `kiosk-day-closure:${siteId}:${today}`
}

export function useDayClosure() {
  const [closedAt, setClosedAt] = useState(null)

  useEffect(() => {
    if (typeof window === "undefined") return
    const raw = localStorage.getItem(storageKey())
    setClosedAt(raw ? JSON.parse(raw) : null)
  }, [])

  const closeDay = useCallback((operatorName) => {
    const payload = {
      closed_at: new Date().toISOString(),
      operator_name: operatorName,
    }
    localStorage.setItem(storageKey(), JSON.stringify(payload))
    setClosedAt(payload)
    return payload
  }, [])

  return { closedAt, isClosed: Boolean(closedAt), closeDay }
}
