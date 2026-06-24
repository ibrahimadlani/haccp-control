import { apiCall, bearerHeaders, operatorHeaders } from "./client"

export function postTemperatureRecord(token, { pin, operatorId }, body) {
  return apiCall("/api/v1/temperature-records", {
    method: "POST",
    headers: operatorHeaders(token, pin, operatorId),
    body: JSON.stringify(body),
  })
}

/**
 * Submit multiple HACCP temperature measurements in one atomic call.
 *
 * Used by the daily temperature tour page to flush all readings at once,
 * and by the offline queue to replay buffered measurements after reconnection.
 * The server validates all equipment IDs and timestamps before writing anything.
 *
 * @param {string} token - Establishment JWT
 * @param {{pin: string, operatorId: string}} credentials - Operator auth headers
 * @param {Array<{equipment_id: string, measured_value: string, source: string, measured_at: string|null}>} records
 */
export function postTemperatureRecordsBulk(token, { pin, operatorId }, records) {
  return apiCall("/api/v1/temperature-records/bulk", {
    method: "POST",
    headers: operatorHeaders(token, pin, operatorId),
    body: JSON.stringify({ records }),
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
