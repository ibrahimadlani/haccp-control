"use client"

import { createContext, useCallback, useContext, useEffect, useState } from "react"
import { toast } from "sonner"
import { getMyTimeclockStatus, postTimeClockEvent } from "@/lib/api/haccp"
import { getEstablishmentSettings } from "@/lib/api/organisation"
import { useOperator } from "@/lib/contexts/OperatorContext"
import { loadEstablishmentToken } from "@/lib/session/establishment"

const TimeclockContext = createContext(null)

const STATUS_AFTER_EVENT = {
  CLOCK_IN: "active",
  BREAK_END: "active",
  BREAK_START: "on_break",
  CLOCK_OUT: "clocked_out",
}

export function TimeclockProvider({ children }) {
  const { operator } = useOperator()
  const [status, setStatus] = useState(null)
  const [actionLoading, setActionLoading] = useState(null)
  const [initializing, setInitializing] = useState(true)
  const [enabled, setEnabled] = useState(true)

  useEffect(() => {
    const token = loadEstablishmentToken()
    if (!token || !operator) {
      setInitializing(false)
      return
    }
    setInitializing(true)
    Promise.all([
      getMyTimeclockStatus(token, { pin: operator.pin, operatorId: operator.id }),
      getEstablishmentSettings(token).catch(() => null),
    ])
      .then(([statusData, settingsData]) => {
        setStatus(statusData.status)
        setEnabled(settingsData?.timeclock?.enabled ?? true)
      })
      .catch(() => {})
      .finally(() => setInitializing(false))
  }, [operator])

  const handleEvent = useCallback(
    async (type) => {
      const token = loadEstablishmentToken()
      if (!token || !operator || actionLoading) return false
      setActionLoading(type)
      try {
        await postTimeClockEvent(token, { pin: operator.pin, operatorId: operator.id }, type)
        setStatus(STATUS_AFTER_EVENT[type])
        return true
      } catch (err) {
        toast.error(String(err.message))
        return false
      } finally {
        setActionLoading(null)
      }
    },
    [operator, actionLoading],
  )

  return (
    <TimeclockContext.Provider value={{ status, actionLoading, initializing, enabled, handleEvent }}>
      {children}
    </TimeclockContext.Provider>
  )
}

export function useTimeclock() {
  return useContext(TimeclockContext)
}
