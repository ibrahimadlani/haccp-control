import {
  DEVICE_CONTEXT_KEY,
  DEVICE_ESTABLISHMENT_ID_KEY,
  DEVICE_TOKEN_KEY,
} from "./constants"

function decodeJwtExp(token) {
  try {
    const payload = JSON.parse(atob(token.split(".")[1]))
    return payload.exp ?? null
  } catch {
    return null
  }
}

function isTokenExpired(token) {
  const exp = decodeJwtExp(token)
  if (!exp) return true
  return Date.now() / 1000 >= exp
}

export function saveEstablishmentSession({ token, establishment }) {
  if (typeof window === "undefined") return
  localStorage.setItem(DEVICE_TOKEN_KEY, token)
  localStorage.setItem(DEVICE_CONTEXT_KEY, JSON.stringify(establishment))
}

export function loadEstablishmentToken() {
  if (typeof window === "undefined") return null
  const token = localStorage.getItem(DEVICE_TOKEN_KEY)
  if (!token) return null
  if (isTokenExpired(token)) {
    clearEstablishmentSession()
    return null
  }
  return token
}

export function loadEstablishmentContext() {
  if (typeof window === "undefined") return null
  const raw = localStorage.getItem(DEVICE_CONTEXT_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

export function saveEstablishmentId(id) {
  if (typeof window === "undefined") return
  localStorage.setItem(DEVICE_ESTABLISHMENT_ID_KEY, id)
}

export function loadEstablishmentId() {
  if (typeof window === "undefined") return null
  return localStorage.getItem(DEVICE_ESTABLISHMENT_ID_KEY)
}

export function clearEstablishmentSession() {
  if (typeof window === "undefined") return
  localStorage.removeItem(DEVICE_TOKEN_KEY)
  localStorage.removeItem(DEVICE_CONTEXT_KEY)
}

export function clearAllDeviceStorage() {
  if (typeof window === "undefined") return
  localStorage.removeItem(DEVICE_TOKEN_KEY)
  localStorage.removeItem(DEVICE_CONTEXT_KEY)
  localStorage.removeItem(DEVICE_ESTABLISHMENT_ID_KEY)
}
