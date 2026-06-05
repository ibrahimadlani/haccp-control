/** Suivi local des échéances documentaires (cantine — inspiré ancienne app resto). */

import { loadEstablishmentId } from "@/lib/session/establishment"

const CATEGORIES = {
  DERATISATION: {
    id: "DERATISATION",
    emoji: "🐀",
    title: "Dératisation / Anti-nuisibles",
    intervalMonths: 6,
    scanType: "DERATISATION",
  },
  MICROBIO: {
    id: "MICROBIO",
    emoji: "🧫",
    title: "Contrôles microbiologiques",
    intervalMonths: 6,
    scanType: "LAB_REPORT",
  },
  AUDIT: {
    id: "AUDIT",
    emoji: "🏛️",
    title: "Audits de conformité",
    intervalMonths: 6,
    scanType: "AUDIT",
  },
  BL: {
    id: "BL",
    emoji: "📋",
    title: "Bons de livraison",
    intervalMonths: 1,
    scanType: "BL",
  },
}

function key() {
  return `kiosk-compliance:${loadEstablishmentId() ?? "default"}`
}

function readAll() {
  if (typeof window === "undefined") return {}
  try {
    return JSON.parse(localStorage.getItem(key()) ?? "{}")
  } catch {
    return {}
  }
}

function writeAll(data) {
  localStorage.setItem(key(), JSON.stringify(data))
}

function addMonths(date, months) {
  const d = new Date(date)
  d.setMonth(d.getMonth() + months)
  return d
}

function fmt(date) {
  return date.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric" })
}

export function listComplianceCategories() {
  const stored = readAll()
  const today = new Date()

  return Object.values(CATEGORIES).map((cat) => {
    const lastIso = stored[cat.id]?.last_upload
    const lastDate = lastIso ? new Date(lastIso) : addMonths(today, -7)
    const nextDate = addMonths(lastDate, cat.intervalMonths)
    const isLate = today > nextDate

    return {
      ...cat,
      lastLabel: fmt(lastDate),
      nextLabel: fmt(nextDate),
      isLate,
    }
  })
}

export function recordComplianceUpload(categoryId) {
  const stored = readAll()
  stored[categoryId] = { last_upload: new Date().toISOString() }
  writeAll(stored)
}

export function mapScanTypeToCategory(documentType) {
  const upper = (documentType ?? "").toUpperCase()
  if (upper.includes("LAB") || upper.includes("MICRO")) return "MICROBIO"
  if (upper.includes("AUDIT") || upper.includes("DDPP")) return "AUDIT"
  if (upper.includes("BL") || upper.includes("LIVRAISON")) return "BL"
  if (upper.includes("DERAT") || upper.includes("NUISIBLE")) return "DERATISATION"
  return "BL"
}
