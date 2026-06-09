"use client"

import { useCallback, useEffect, useState } from "react"
import { loadEstablishmentId } from "@/lib/session/establishment"

const DURATION_MS = 2 * 60 * 60 * 1000

function storageKey() {
  const siteId = loadEstablishmentId() ?? "default"
  return `kiosk-cooling-chrono:${siteId}`
}

function readState() {
  if (typeof window === "undefined") return null
  try {
    const raw = localStorage.getItem(storageKey())
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function formatRemaining(ms) {
  const totalSec = Math.max(0, Math.floor(ms / 1000))
  const h = Math.floor(totalSec / 3600)
  const m = Math.floor((totalSec % 3600) / 60)
  const s = totalSec % 60
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`
}

export function useCoolingChrono() {
  const [active, setActive] = useState(null)
  const [now, setNow] = useState(Date.now())

  useEffect(() => {
    setActive(readState())
    const tick = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(tick)
  }, [])

  const start = useCallback((label = "Cellule de refroidissement") => {
    const payload = {
      label,
      started_at: new Date().toISOString(),
      ends_at: new Date(Date.now() + DURATION_MS).toISOString(),
    }
    localStorage.setItem(storageKey(), JSON.stringify(payload))
    setActive(payload)
    return payload
  }, [])

  const stop = useCallback(() => {
    localStorage.removeItem(storageKey())
    setActive(null)
  }, [])

  const remainingMs = active ? new Date(active.ends_at).getTime() - now : 0
  const isRunning = Boolean(active)
  const isOverdue = isRunning && remainingMs <= 0

  return {
    active,
    isRunning,
    isOverdue,
    remainingLabel: isRunning ? formatRemaining(remainingMs) : null,
    start,
    stop,
  }
}
