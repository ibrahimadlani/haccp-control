import { apiCall, bearerHeaders, operatorHeaders } from "./client"

export function postTemperatureRecord(token, { pin, operatorId }, body) {
  return apiCall("/api/v1/temperature-records", {
    method: "POST",
    headers: operatorHeaders(token, pin, operatorId),
    body: JSON.stringify(body),
  })
}

export function postTimeClockEvent(token, { pin, operatorId }, typeEvenement) {
  return apiCall("/api/v1/time-clock-events", {
    method: "POST",
    headers: operatorHeaders(token, pin, operatorId),
    body: JSON.stringify({ type_evenement: typeEvenement }),
  })
}

export function getTimeclockStatuses(token) {
  return apiCall("/api/v1/time-clock-statuses", {
    headers: bearerHeaders(token),
  })
}

export function getMyTimeclockStatus(token, { pin, operatorId }) {
  return apiCall("/api/v1/time-clock-statuses/me", {
    headers: operatorHeaders(token, pin, operatorId),
  })
}
