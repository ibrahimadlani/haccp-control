/** Dates ISO (lun–dim) de la semaine contenant la date donnée. */

export function getWeekDates(anchor = new Date()) {
  const d = new Date(anchor)
  const day = d.getDay()
  const diff = day === 0 ? -6 : 1 - day
  d.setHours(12, 0, 0, 0)
  d.setDate(d.getDate() + diff)
  return Array.from({ length: 7 }, (_, i) => {
    const x = new Date(d)
    x.setDate(d.getDate() + i)
    return x.toISOString().split("T")[0]
  })
}

export function formatDayLabel(isoDate) {
  const d = new Date(`${isoDate}T12:00:00`)
  return d.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "short" })
}

export function isToday(isoDate) {
  return isoDate === new Date().toISOString().split("T")[0]
}
