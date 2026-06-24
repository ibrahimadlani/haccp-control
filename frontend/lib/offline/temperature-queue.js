/**
 * Offline queue for HACCP temperature records.
 *
 * Stores pending measurements in localStorage so they survive page refreshes
 * and network loss in the cold room.  Records are replayed in FIFO order when
 * the device comes back online via the `window.online` event in the record page.
 *
 * Storage key: "haccp_temperature_queue"
 * Entry shape: { localId, equipment_id, measured_value, source, captured_at }
 *
 * Design notes:
 * - `captured_at` is stamped at the moment of capture, not at flush time.
 *   It is sent to the server as `measured_at`, which validates it against the
 *   8-hour window.  Records captured more than 8 hours before flush will be
 *   rejected by the server with 422.
 * - `localId` is a client-generated UUID used as a stable React key and for
 *   targeted deletion on partial success.
 * - All functions are SSR-safe: they check `typeof window === "undefined"` and
 *   return safe defaults when running in a Node.js/server context.
 */

const QUEUE_KEY = "haccp_temperature_queue"

/**
 * Add a temperature reading to the offline queue.
 *
 * @param {{ equipment_id: string, measured_value: string, source: string }} record
 * @returns {string} The generated localId for this entry.
 */
export function enqueueTemperatureRecord(record) {
  const queue = loadQueue()
  const entry = {
    localId: crypto.randomUUID(),
    equipment_id: record.equipment_id,
    measured_value: record.measured_value,
    source: record.source ?? "MANUEL",
    captured_at: new Date().toISOString(),
  }
  queue.push(entry)
  _saveQueue(queue)
  return entry.localId
}

/**
 * Return all pending entries in FIFO order.
 * Returns an empty array on SSR or if localStorage is unavailable.
 *
 * @returns {Array<{localId: string, equipment_id: string, measured_value: string, source: string, captured_at: string}>}
 */
export function loadQueue() {
  if (typeof window === "undefined") return []
  try {
    const raw = localStorage.getItem(QUEUE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

/**
 * Return the number of pending entries in the queue.
 *
 * @returns {number}
 */
export function queueSize() {
  return loadQueue().length
}

/**
 * Remove a single entry by its localId (used after individual successes).
 *
 * @param {string} localId
 */
export function removeFromQueue(localId) {
  const queue = loadQueue().filter((entry) => entry.localId !== localId)
  _saveQueue(queue)
}

/**
 * Remove all entries from the queue (used after a successful bulk flush).
 */
export function clearQueue() {
  if (typeof window === "undefined") return
  localStorage.removeItem(QUEUE_KEY)
}

/**
 * Build the API payload array from the current queue contents.
 * Maps `captured_at` → `measured_at` to match the server schema.
 *
 * @returns {Array<{equipment_id: string, measured_value: string, source: string, measured_at: string}>}
 */
export function buildFlushPayload() {
  return loadQueue().map((entry) => ({
    equipment_id: entry.equipment_id,
    measured_value: entry.measured_value,
    source: entry.source,
    measured_at: entry.captured_at,
  }))
}

function _saveQueue(queue) {
  if (typeof window === "undefined") return
  try {
    localStorage.setItem(QUEUE_KEY, JSON.stringify(queue))
  } catch {
    // localStorage full or unavailable — silently ignore to avoid crashing the UI.
  }
}
