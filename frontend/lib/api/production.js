import { apiCall, bearerHeaders } from "./client"

export function getProductionBatches(token) {
  return apiCall("/api/v1/production-batches", { headers: bearerHeaders(token) })
}

export function createProductionBatch(token, body) {
  return apiCall("/api/v1/production-batches", {
    method: "POST",
    headers: bearerHeaders(token),
    body: JSON.stringify(body),
  })
}

export function getProductionSteps(token, batchId) {
  return apiCall(`/api/v1/production-batches/${batchId}/steps`, {
    headers: bearerHeaders(token),
  })
}

export function createProductionStep(token, batchId, body) {
  return apiCall(`/api/v1/production-batches/${batchId}/steps`, {
    method: "POST",
    headers: bearerHeaders(token),
    body: JSON.stringify(body),
  })
}
