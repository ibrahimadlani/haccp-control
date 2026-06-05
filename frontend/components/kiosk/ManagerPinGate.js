"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { PinPadDialog } from "@/components/auth/PinPadDialog"
import { getEstablishmentUsers, postOperatorSession } from "@/lib/api/auth"
import {
  loadEstablishmentContext,
  loadEstablishmentToken,
} from "@/lib/session/establishment"
import { MANAGER_ROUTE } from "@/lib/kiosk/phases"

const UNLOCK_KEY = "kiosk-manager-unlock"
const UNLOCK_TTL_MS = 30 * 60 * 1000

function isManagerRole(role = "") {
  return /manager|admin|responsable|gerant|chef/i.test(role)
}

export function isManagerUnlocked() {
  if (typeof window === "undefined") return false
  try {
    const raw = sessionStorage.getItem(UNLOCK_KEY)
    if (!raw) return false
    const { expires_at } = JSON.parse(raw)
    return Date.now() < expires_at
  } catch {
    return false
  }
}

function setManagerUnlocked() {
  sessionStorage.setItem(
    UNLOCK_KEY,
    JSON.stringify({ expires_at: Date.now() + UNLOCK_TTL_MS }),
  )
}

async function verifyManagerPin(pin) {
  const token = loadEstablishmentToken()
  const ctx = loadEstablishmentContext()
  if (!token || !ctx?.etablissement_id) return false

  const users = await getEstablishmentUsers(token, ctx.etablissement_id, "SITE_EMPLOYEE")
  const list = Array.isArray(users) ? users : users?.items ?? []
  const managers = list.filter(
    (u) => u.is_active !== false && isManagerRole(u.role ?? u.role_name ?? ""),
  )

  for (const manager of managers) {
    try {
      await postOperatorSession({ token, pin, operatorId: manager.id })
      return true
    } catch {
      // try next manager PIN match
    }
  }
  return false
}

export function ManagerPinGate({ children }) {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [unlocked, setUnlocked] = useState(false)

  useEffect(() => {
    if (isManagerUnlocked()) {
      setUnlocked(true)
      return
    }
    setOpen(true)
  }, [])

  async function handlePin(pin) {
    setLoading(true)
    const ok = await verifyManagerPin(pin)
    setLoading(false)
    if (ok) {
      setManagerUnlocked()
      setUnlocked(true)
      setOpen(false)
      return
    }
    router.replace("/operator")
  }

  if (!unlocked) {
    return (
      <PinPadDialog
        open={open}
        onOpenChange={(v) => {
          if (!v) router.replace("/operator")
        }}
        title="Espace Manager"
        description="Code PIN responsable requis"
        onComplete={handlePin}
        loading={loading}
      />
    )
  }

  return children
}

export function ManagerAccessButton({ className }) {
  const router = useRouter()

  function handleClick() {
    if (isManagerUnlocked()) {
      router.push(MANAGER_ROUTE)
      return
    }
    router.push(MANAGER_ROUTE)
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      className={className}
    >
      ⚙️ Espace Manager
    </button>
  )
}
