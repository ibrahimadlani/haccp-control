import { apiCall, bearerHeaders } from "./client"

export function getOperators(token, { includeInactive = false } = {}) {
  const query = includeInactive ? "?include_inactive=true" : ""
  return apiCall(`/api/v1/operators${query}`, { headers: bearerHeaders(token) })
}

export function createOperator(token, body) {
  return apiCall("/api/v1/operators", {
    method: "POST",
    headers: bearerHeaders(token),
    body: JSON.stringify(body),
  })
}

export function updateOperator(token, operatorId, body) {
  return apiCall(`/api/v1/operators/${operatorId}`, {
    method: "PATCH",
    headers: bearerHeaders(token),
    body: JSON.stringify(body),
  })
}

export function resetOperatorPin(token, operatorId, pinCode) {
  return apiCall(`/api/v1/operators/${operatorId}/reset-pin`, {
    method: "POST",
    headers: bearerHeaders(token),
    body: JSON.stringify({ pin_code: pinCode }),
  })
}

export function deactivateOperator(token, operatorId) {
  return apiCall(`/api/v1/operators/${operatorId}`, {
    method: "DELETE",
    headers: bearerHeaders(token),
  })
}
