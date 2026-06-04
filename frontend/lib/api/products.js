import { apiCall, bearerHeaders } from "./client"

export function getProducts(token, { supplierId = null, includeInactive = false } = {}) {
  const params = new URLSearchParams()
  if (supplierId) params.set("supplier_id", supplierId)
  if (includeInactive) params.set("include_inactive", "true")
  const query = params.toString() ? `?${params}` : ""
  return apiCall(`/api/v1/products${query}`, { headers: bearerHeaders(token) })
}

export function getProduct(token, id) {
  return apiCall(`/api/v1/products/${id}`, { headers: bearerHeaders(token) })
}

export function createProduct(token, body) {
  return apiCall("/api/v1/products", {
    method: "POST",
    headers: bearerHeaders(token),
    body: JSON.stringify(body),
  })
}

export function updateProduct(token, id, body) {
  return apiCall(`/api/v1/products/${id}`, {
    method: "PATCH",
    headers: bearerHeaders(token),
    body: JSON.stringify(body),
  })
}

export function deleteProduct(token, id) {
  return apiCall(`/api/v1/products/${id}`, {
    method: "DELETE",
    headers: bearerHeaders(token),
  })
}
