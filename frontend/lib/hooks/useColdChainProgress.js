"use client"

import { useCallback, useEffect, useState } from "react"
import { filterColdEquipments } from "@/lib/operator/canteenDay"
import { loadEstablishmentId } from "@/lib/session/establishment"

function storageKey() {
  const siteId = loadEstablishmentId() ?? "default"
  const today = new Date().toISOString().split("T")[0]
  return `kiosk-cold-chain:${siteId}:${today}`
}

function readDoneIds() {
  if (typeof window === "undefined") return []
  try {
    const raw = localStorage.getItem(storageKey())
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

export function useColdChainProgress(equipments = []) {
  const coldEquipments = filterColdEquipments(equipments)
  const total = coldEquipments.length
  const [doneIds, setDoneIds] = useState(() => new Set(readDoneIds()))

  useEffect(() => {
    setDoneIds(new Set(readDoneIds()))
  }, [total])

  const markDone = useCallback((equipmentId) => {
    setDoneIds((prev) => {
      const next = new Set(prev).add(equipmentId)
      localStorage.setItem(storageKey(), JSON.stringify([...next]))
      return next
    })
  }, [])

  const done = doneIds.size
  const complete = total > 0 && done >= total
  const badge =
    total === 0
      ? null
      : complete
        ? `${done}/${total} relevés`
        : `${done}/${total} relevés`

  return { doneIds, done, total, complete, badge, markDone, coldEquipments }
}
