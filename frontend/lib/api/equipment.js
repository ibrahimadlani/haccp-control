import { apiCall, bearerHeaders, operatorHeaders } from "./client"

export function getEquipments(token, { pin, operatorId } = {}) {
  const headers =
    pin && operatorId
      ? operatorHeaders(token, pin, operatorId)
      : bearerHeaders(token)
  return apiCall("/api/v1/equipments", { headers })
}

export function createEquipment(token, body) {
  return apiCall("/api/v1/equipments", {
    method: "POST",
    headers: bearerHeaders(token),
    body: JSON.stringify(body),
  })
}

export function updateEquipment(token, id, body) {
  return apiCall(`/api/v1/equipments/${id}`, {
    method: "PATCH",
    headers: bearerHeaders(token),
    body: JSON.stringify(body),
  })
}

export function deleteEquipment(token, id, hardDelete = false) {
  return apiCall(`/api/v1/equipments/${id}${hardDelete ? "?hard_delete=true" : ""}`, {
    method: "DELETE",
    headers: bearerHeaders(token),
  })
}

export function getSiteEquipments(token, establishmentId) {
  return apiCall(`/api/v1/establishments/${establishmentId}/equipments`, {
    headers: bearerHeaders(token),
  })
}

export function createSiteEquipment(token, establishmentId, body) {
  return apiCall(`/api/v1/establishments/${establishmentId}/equipments`, {
    method: "POST",
    headers: bearerHeaders(token),
    body: JSON.stringify(body),
  })
}
