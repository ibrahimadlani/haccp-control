import { apiCall, bearerHeaders } from "./client"

export function getSuppliers(token, { includeInactive = false, status } = {}) {
  const params = new URLSearchParams()
  if (includeInactive) params.set("include_inactive", "true")
  if (status) params.set("status", status)
  const query = params.toString() ? `?${params}` : ""
  return apiCall(`/api/v1/suppliers${query}`, { headers: bearerHeaders(token) })
}

export function getSupplier(token, id) {
  return apiCall(`/api/v1/suppliers/${id}`, { headers: bearerHeaders(token) })
}

export function createSupplier(token, body) {
  return apiCall("/api/v1/suppliers", {
    method: "POST",
    headers: bearerHeaders(token),
    body: JSON.stringify(body),
  })
}

export function updateSupplier(token, id, body) {
  return apiCall(`/api/v1/suppliers/${id}`, {
    method: "PATCH",
    headers: bearerHeaders(token),
    body: JSON.stringify(body),
  })
}

export function deleteSupplier(token, id) {
  return apiCall(`/api/v1/suppliers/${id}`, {
    method: "DELETE",
    headers: bearerHeaders(token),
  })
}
