"use client"

import { createContext, useCallback, useContext, useMemo, useState } from "react"

const PlatformContext = createContext(null)

export function PlatformProvider({ children }) {
  const [platformKey, setPlatformKeyState] = useState(null)

  const setPlatformKey = useCallback((key) => setPlatformKeyState(key), [])
  const clearPlatformKey = useCallback(() => setPlatformKeyState(null), [])

  const value = useMemo(
    () => ({ platformKey, setPlatformKey, clearPlatformKey }),
    [platformKey, setPlatformKey, clearPlatformKey]
  )

  return <PlatformContext.Provider value={value}>{children}</PlatformContext.Provider>
}

export function usePlatform() {
  const ctx = useContext(PlatformContext)
  if (!ctx) throw new Error("usePlatform must be used inside PlatformProvider")
  return ctx
}
