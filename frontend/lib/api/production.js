import { apiCall, bearerHeaders, operatorHeaders } from "./client"

export function createProductionTemperature(token, { pin, operatorId }, body) {
  return apiCall("/api/v1/production-temperature-records", {
    method: "POST",
    headers: operatorHeaders(token, pin, operatorId),
    body: JSON.stringify(body),
  })
}

export function getWitnessSamples(token) {
  return apiCall("/api/v1/witness-samples", {
    headers: bearerHeaders(token),
  })
}

export function createWitnessSample(token, { pin, operatorId }, body) {
  return apiCall("/api/v1/witness-samples", {
    method: "POST",
    headers: operatorHeaders(token, pin, operatorId),
    body: JSON.stringify(body),
  })
}

export function getOilChanges(token) {
  return apiCall("/api/v1/oil-change-records", {
    headers: bearerHeaders(token),
  })
}

export function createOilChange(token, { pin, operatorId }, body) {
  return apiCall("/api/v1/oil-change-records", {
    method: "POST",
    headers: operatorHeaders(token, pin, operatorId),
    body: JSON.stringify(body),
  })
}

export function getOpenedProductLabels(token) {
  return apiCall("/api/v1/opened-product-labels", {
    headers: bearerHeaders(token),
  })
}

export function createOpenedProductLabel(token, { pin, operatorId }, body) {
  return apiCall("/api/v1/opened-product-labels", {
    method: "POST",
    headers: operatorHeaders(token, pin, operatorId),
    body: JSON.stringify(body),
  })
}

export function getDailyMenu(token, { from, to } = {}) {
  const params = new URLSearchParams()
  if (from) params.set("from", from)
  if (to) params.set("to", to)
  const qs = params.toString()
  return apiCall(`/api/v1/daily-menu${qs ? `?${qs}` : ""}`, {
    headers: bearerHeaders(token),
  })
}

export function createDailyMenuItem(token, body) {
  return apiCall("/api/v1/daily-menu/items", {
    method: "POST",
    headers: bearerHeaders(token),
    body: JSON.stringify(body),
  })
}

export function updateDailyMenuItem(token, itemId, body) {
  return apiCall(`/api/v1/daily-menu/items/${itemId}`, {
    method: "PATCH",
    headers: bearerHeaders(token),
    body: JSON.stringify(body),
  })
}

export function deleteDailyMenuItem(token, itemId) {
  return apiCall(`/api/v1/daily-menu/items/${itemId}`, {
    method: "DELETE",
    headers: bearerHeaders(token),
  })
}
