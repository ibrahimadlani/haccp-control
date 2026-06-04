import { apiCall, bearerHeaders, operatorHeaders } from "./client"

export function getNonConformities(token, { status, type, limit = 100 } = {}) {
  const params = new URLSearchParams()
  if (status) params.set("status", status)
  if (type) params.set("type", type)
  params.set("limit", String(limit))
  return apiCall(`/api/v1/nonconformities?${params}`, { headers: bearerHeaders(token) })
}

export function getNonConformityStats(token) {
  return apiCall("/api/v1/nonconformities/stats", { headers: bearerHeaders(token) })
}

export function acknowledgeNonConformity(token, { pin, operatorId }, id) {
  return apiCall(`/api/v1/nonconformities/${id}/acknowledge`, {
    method: "PATCH",
    headers: operatorHeaders(token, pin, operatorId),
  })
}

export function postCorrectiveAction(token, { pin, operatorId }, id, formData) {
  return apiCall(`/api/v1/nonconformities/${id}/corrective-action`, {
    method: "POST",
    headers: operatorHeaders(token, pin, operatorId),
    body: formData,
  })
}

export function closeNonConformity(token, id, closingComment = null) {
  return apiCall(`/api/v1/nonconformities/${id}/close`, {
    method: "PATCH",
    headers: bearerHeaders(token),
    body: JSON.stringify({ closing_comment: closingComment }),
  })
}
