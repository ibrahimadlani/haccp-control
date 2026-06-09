"use client"

import { useEffect, useState } from "react"
import { getEstablishmentSettings } from "@/lib/api/organisation"
import { loadEstablishmentToken } from "@/lib/session/establishment"

const DEFAULT_FEATURES = {
  timeclock: { enabled: true },
  haccp_temperature: { enabled: true },
  cleaning: { enabled: true },
  receptions: { enabled: true },
  nonconformities: { enabled: true },
}

function isFeatureEnabled(settings, key) {
  const block = settings?.[key]
  if (!block) return true
  return block.enabled !== false
}

export function useEstablishmentFeatures() {
  const [settings, setSettings] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = loadEstablishmentToken()
    if (!token) {
      setLoading(false)
      return
    }
    getEstablishmentSettings(token)
      .then(setSettings)
      .catch(() => setSettings(DEFAULT_FEATURES))
      .finally(() => setLoading(false))
  }, [])

  const merged = settings ?? DEFAULT_FEATURES

  return {
    loading,
    settings: merged,
    timeclockEnabled: merged.timeclock?.enabled !== false,
    temperatureEnabled: isFeatureEnabled(merged, "haccp_temperature"),
    cleaningEnabled: isFeatureEnabled(merged, "cleaning"),
    receptionsEnabled: isFeatureEnabled(merged, "receptions"),
  }
}
