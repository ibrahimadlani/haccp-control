import { ORG_CONTEXT_KEY, ORG_TOKEN_KEY } from "./constants"

export function saveOrganisationSession({ token, organisation }) {
  if (typeof window === "undefined") return
  sessionStorage.setItem(ORG_TOKEN_KEY, token)
  sessionStorage.setItem(ORG_CONTEXT_KEY, JSON.stringify(organisation))
}

export function loadOrganisationToken() {
  if (typeof window === "undefined") return null
  return sessionStorage.getItem(ORG_TOKEN_KEY)
}

export function loadOrganisationContext() {
  if (typeof window === "undefined") return null
  const raw = sessionStorage.getItem(ORG_CONTEXT_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

export function clearOrganisationSession() {
  if (typeof window === "undefined") return
  sessionStorage.removeItem(ORG_TOKEN_KEY)
  sessionStorage.removeItem(ORG_CONTEXT_KEY)
}
