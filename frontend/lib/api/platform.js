import { apiCall, platformHeaders } from "./client"

export function createOrganisation(platformKey, body) {
  return apiCall("/api/v1/organisations", {
    method: "POST",
    headers: platformHeaders(platformKey),
    body: JSON.stringify(body),
  })
}
