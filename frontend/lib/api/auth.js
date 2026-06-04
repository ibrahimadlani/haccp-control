import { apiCall, bearerHeaders, operatorHeaders } from "./client"

export function getEstablishmentMeta(establishmentId) {
  return apiCall(`/api/v1/establishments/${establishmentId}`)
}

export function postEstablishmentSession({ email, password, etablissement_id }) {
  return apiCall("/api/v1/establishment-sessions", {
    method: "POST",
    body: JSON.stringify({ email, password, etablissement_id }),
  })
}

export function postOrganisationSession({ email, password }) {
  return apiCall("/api/v1/organisation-sessions", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  })
}

export function postOperatorSession({ token, pin, operatorId }) {
  return apiCall("/api/v1/operator-sessions", {
    method: "POST",
    headers: operatorHeaders(token, pin, operatorId),
  })
}

export function getEstablishmentUsers(token, establishmentId, role) {
  const query = role ? `?role=${role}` : ""
  return apiCall(`/api/v1/establishments/${establishmentId}/users${query}`, {
    headers: bearerHeaders(token),
  })
}
