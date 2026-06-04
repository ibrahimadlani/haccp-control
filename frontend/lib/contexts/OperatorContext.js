"use client"

import { createContext, useCallback, useContext, useMemo, useState } from "react"

const OperatorContext = createContext(null)

export function OperatorProvider({ children }) {
  const [operator, setOperatorState] = useState(null)

  const setOperator = useCallback((data) => setOperatorState(data), [])
  const clearOperator = useCallback(() => setOperatorState(null), [])

  const value = useMemo(
    () => ({ operator, setOperator, clearOperator }),
    [operator, setOperator, clearOperator]
  )

  return <OperatorContext.Provider value={value}>{children}</OperatorContext.Provider>
}

export function useOperator() {
  const ctx = useContext(OperatorContext)
  if (!ctx) throw new Error("useOperator must be used inside OperatorProvider")
  return ctx
}
