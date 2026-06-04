import { apiCall, bearerHeaders } from "./client"

export function getOrganisationOverview(token, organisationId) {
  return apiCall(`/api/v1/organisations/${organisationId}/overview`, {
    headers: bearerHeaders(token),
  })
}

export function getOrganisationSubscriptions(token, organisationId) {
  return apiCall(`/api/v1/organisations/${organisationId}/subscriptions`, {
    headers: bearerHeaders(token),
  })
}

export function createEstablishment(token, organisationId, body) {
  return apiCall(`/api/v1/organisations/${organisationId}/establishments`, {
    method: "POST",
    headers: bearerHeaders(token),
    body: JSON.stringify(body),
  })
}

export function deleteEstablishment(token, establishmentId) {
  return apiCall(`/api/v1/establishments/${establishmentId}`, {
    method: "DELETE",
    headers: bearerHeaders(token),
  })
}

export function getSiteUsers(token, establishmentId) {
  return apiCall(`/api/v1/establishments/${establishmentId}/users/assigned`, {
    headers: bearerHeaders(token),
  })
}

export function getEstablishmentSettings(token) {
  return apiCall("/api/v1/establishment-settings", {
    headers: bearerHeaders(token),
  })
}

export function updateEstablishmentSettings(token, data) {
  return apiCall("/api/v1/establishment-settings", {
    method: "PATCH",
    headers: bearerHeaders(token),
    body: JSON.stringify(data),
  })
}
