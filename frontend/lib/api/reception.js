import { apiCall, bearerHeaders, operatorHeaders } from "./client"

// ── Products ──────────────────────────────────────────────────────────────────

export function getProducts(token, { supplierId } = {}) {
  const query = supplierId ? `?supplier_id=${supplierId}` : ""
  return apiCall(`/api/v1/products${query}`, {
    headers: bearerHeaders(token),
  })
}

export function createProduct(token, body) {
  return apiCall("/api/v1/products", {
    method: "POST",
    headers: bearerHeaders(token),
    body: JSON.stringify(body),
  })
}

export function updateProduct(token, productId, body) {
  return apiCall(`/api/v1/products/${productId}`, {
    method: "PATCH",
    headers: bearerHeaders(token),
    body: JSON.stringify(body),
  })
}

export function deleteProduct(token, productId) {
  return apiCall(`/api/v1/products/${productId}`, {
    method: "DELETE",
    headers: bearerHeaders(token),
  })
}

// ── Reception Sessions ────────────────────────────────────────────────────────

/**
 * Open a new reception session.
 * Sends multipart/form-data to support an optional BL photo.
 */
export function openReceptionSession(
  token,
  { pin, operatorId },
  {
    supplierId,
    receivedAt,
    blPhoto,
    labReportPhoto,
    truckConditionOk,
    packagingIntegrityOk,
    cannedGoodsInspectedOk,
  },
) {
  const form = new FormData()
  form.append("supplier_id", supplierId)
  form.append("received_at", receivedAt) // ISO string e.g. "2026-06-03T14:30:00"
  form.append("truck_condition_ok", String(Boolean(truckConditionOk)))
  form.append("packaging_integrity_ok", String(Boolean(packagingIntegrityOk)))
  form.append("canned_goods_inspected_ok", String(Boolean(cannedGoodsInspectedOk)))
  if (blPhoto) form.append("bl_photo", blPhoto)
  if (labReportPhoto) form.append("lab_report_photo", labReportPhoto)

  return apiCall("/api/v1/reception-sessions", {
    method: "POST",
    headers: operatorHeaders(token, pin, operatorId),
    body: form,
  })
}

export function getReceptionSession(token, sessionId) {
  return apiCall(`/api/v1/reception-sessions/${sessionId}`, {
    headers: bearerHeaders(token),
  })
}

/**
 * Add a scanned item to an open session.
 * Passes product_min_temp / product_max_temp for Pydantic schema-level validation.
 */
export function addReceptionItem(token, { pin, operatorId }, sessionId, item) {
  return apiCall(`/api/v1/reception-sessions/${sessionId}/items`, {
    method: "POST",
    headers: operatorHeaders(token, pin, operatorId),
    body: JSON.stringify(item),
  })
}

export function searchReceptionByLot(token, lotNumber) {
  const params = new URLSearchParams({ lot_number: lotNumber })
  return apiCall(`/api/v1/reception-items/search?${params}`, {
    headers: bearerHeaders(token),
  })
}

export function closeReceptionSession(token, { pin, operatorId }, sessionId) {
  return apiCall(`/api/v1/reception-sessions/${sessionId}/close`, {
    method: "PATCH",
    headers: operatorHeaders(token, pin, operatorId),
  })
}
