const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001"

export class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail))
    this.status = status
    this.detail = detail
  }
}

export async function apiCall(path, options = {}) {
  const { body, headers = {}, ...rest } = options
  const isFormData = typeof FormData !== "undefined" && body instanceof FormData

  let response
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      ...rest,
      body,
      headers: {
        ...(!isFormData && body ? { "Content-Type": "application/json" } : {}),
        ...headers,
      },
    })
  } catch {
    throw new ApiError(
      0,
      "Impossible de joindre le serveur. Vérifiez que l'API est démarrée et à jour.",
    )
  }

  const contentType = response.headers.get("content-type") ?? ""
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text()

  if (!response.ok) {
    const detail =
      typeof payload === "object" && payload !== null ? (payload.detail ?? payload) : payload
    throw new ApiError(response.status, detail)
  }

  return payload
}

export function bearerHeaders(token) {
  return { Authorization: `Bearer ${token}` }
}

export function operatorHeaders(token, pin, operatorId) {
  return {
    Authorization: `Bearer ${token}`,
    "X-Device-Pin": pin,
    "X-Operator-Id": String(operatorId),
  }
}

export function platformHeaders(key) {
  return { "X-Platform-Admin-Key": key }
}
