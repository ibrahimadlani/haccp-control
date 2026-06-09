"use client"

import { useCallback, useEffect, useState } from "react"
import { getNonConformityStats } from "@/lib/api/nonconformities"
import { loadEstablishmentToken } from "@/lib/session/establishment"

export function useSafetyStatus(pollMs = 60_000) {
  const [openCount, setOpenCount] = useState(0)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    const token = loadEstablishmentToken()
    if (!token) {
      setOpenCount(0)
      setLoading(false)
      return
    }
    try {
      const stats = await getNonConformityStats(token)
      const open = (stats?.total_open ?? 0) + (stats?.total_in_progress ?? 0)
      setOpenCount(open)
    } catch {
      setOpenCount(0)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, pollMs)
    return () => clearInterval(id)
  }, [refresh, pollMs])

  return {
    openCount,
    loading,
    isSafe: openCount === 0,
    refresh,
  }
}
