import { apiCall, bearerHeaders, operatorHeaders } from "./client"

// ── Manager: zones ────────────────────────────────────────────────────────────

export function getCleaningZones(token) {
  return apiCall("/api/v1/cleaning-zones", { headers: bearerHeaders(token) })
}

export function createCleaningZone(token, body) {
  return apiCall("/api/v1/cleaning-zones", {
    method: "POST",
    headers: bearerHeaders(token),
    body: JSON.stringify(body),
  })
}

export function deleteCleaningZone(token, zoneId) {
  return apiCall(`/api/v1/cleaning-zones/${zoneId}`, {
    method: "DELETE",
    headers: bearerHeaders(token),
  })
}

// ── Manager: routines ─────────────────────────────────────────────────────────

export function getCleaningRoutines(token) {
  return apiCall("/api/v1/cleaning-routines", { headers: bearerHeaders(token) })
}

export function createCleaningRoutine(token, body) {
  return apiCall("/api/v1/cleaning-routines", {
    method: "POST",
    headers: bearerHeaders(token),
    body: JSON.stringify(body),
  })
}

export function getCleaningRoutineDetail(token, routineId) {
  return apiCall(`/api/v1/cleaning-routines/${routineId}`, {
    headers: bearerHeaders(token),
  })
}

export function deleteCleaningRoutine(token, routineId) {
  return apiCall(`/api/v1/cleaning-routines/${routineId}`, {
    method: "DELETE",
    headers: bearerHeaders(token),
  })
}

// ── Manager: task templates ───────────────────────────────────────────────────

export function createCleaningTask(token, routineId, body) {
  return apiCall(`/api/v1/cleaning-routines/${routineId}/tasks`, {
    method: "POST",
    headers: bearerHeaders(token),
    body: JSON.stringify(body),
  })
}

export function updateCleaningTask(token, taskId, body) {
  return apiCall(`/api/v1/cleaning-tasks/${taskId}`, {
    method: "PATCH",
    headers: bearerHeaders(token),
    body: JSON.stringify(body),
  })
}

export function deleteCleaningTask(token, taskId) {
  return apiCall(`/api/v1/cleaning-tasks/${taskId}`, {
    method: "DELETE",
    headers: bearerHeaders(token),
  })
}

// ── Operator: current routine + bulk log ──────────────────────────────────────

/**
 * Fetch the active routine for the current time of day.
 * @param {string|null} scheduleType  Optional override: OPENING | CLOSING | WEEKLY | MONTHLY
 */
export function fetchCurrentRoutine(token, scheduleType = null) {
  const query = scheduleType ? `?schedule_type=${scheduleType}` : ""
  return apiCall(`/api/v1/cleaning-routines/current${query}`, {
    headers: bearerHeaders(token),
  })
}

/**
 * Submit multiple cleaning log entries in one atomic request.
 * @param {Array<{task_id, status, comment}>} items
 */
export function submitBulkCleaning(token, { pin, operatorId }, items) {
  return apiCall("/api/v1/cleaning-logs/bulk", {
    method: "POST",
    headers: operatorHeaders(token, pin, operatorId),
    body: JSON.stringify({ items }),
  })
}
