/** Imprimante thermique Bluetooth — Web Bluetooth + repli impression navigateur. */

const PRINTER_KEY = "kiosk-thermal-printer"

export function getSavedPrinter() {
  if (typeof window === "undefined") return null
  try {
    return JSON.parse(localStorage.getItem(PRINTER_KEY) ?? "null")
  } catch {
    return null
  }
}

export function savePrinter(info) {
  localStorage.setItem(PRINTER_KEY, JSON.stringify(info))
}

export async function connectThermalPrinter() {
  if (typeof navigator === "undefined" || !navigator.bluetooth) {
    throw new Error("Bluetooth non disponible sur cet appareil.")
  }
  const device = await navigator.bluetooth.requestDevice({
    acceptAllDevices: true,
    optionalServices: ["000018f0-0000-1000-8000-00805f9b34fb"],
  })
  const info = { id: device.id, name: device.name ?? "Imprimante" }
  savePrinter(info)
  return info
}

function escposLabel({ productName, openedAt, useBy }) {
  const lines = [
    "\x1B\x40",
    "OUVERTURE PRODUIT\n",
    "----------------\n",
    `${productName}\n`,
    `Ouvert : ${openedAt}\n`,
    `DLC sec. : ${useBy}\n`,
    "\n\n\x1D\x56\x00",
  ]
  return new TextEncoder().encode(lines.join(""))
}

export function printLabelFallback({ productName, openedAt, useBy }) {
  const html = `<!DOCTYPE html><html><head><title>Étiquette</title>
<style>body{font-family:monospace;font-size:14pt;padding:8mm;width:58mm}
h1{font-size:16pt;margin:0 0 4mm}p{margin:2mm 0}</style></head><body>
<h1>OUVERTURE</h1>
<p><strong>${productName}</strong></p>
<p>Ouvert : ${openedAt}</p>
<p>DLC sec. : ${useBy}</p>
</body></html>`
  const w = window.open("", "_blank", "width=320,height=400")
  if (!w) throw new Error("Popup bloquée — autorisez les fenêtres contextuelles.")
  w.document.write(html)
  w.document.close()
  w.focus()
  w.print()
}

export async function printOpenedProductLabel({ productName, openedAt, useBy }) {
  const saved = getSavedPrinter()
  if (saved && typeof navigator !== "undefined" && navigator.bluetooth) {
    try {
      const device = await navigator.bluetooth.requestDevice({
        filters: saved.id ? [{ id: saved.id }] : undefined,
        acceptAllDevices: !saved.id,
        optionalServices: ["000018f0-0000-1000-8000-00805f9b34fb"],
      })
      const server = await device.gatt.connect()
      const services = await server.getPrimaryServices()
      for (const service of services) {
        const chars = await service.getCharacteristics()
        for (const ch of chars) {
          if (ch.properties.write || ch.properties.writeWithoutResponse) {
            const data = escposLabel({ productName, openedAt, useBy })
            await ch.writeValue(data)
            server.disconnect()
            return { mode: "bluetooth", printer: device.name }
          }
        }
      }
      server.disconnect()
    } catch {
      // repli ci-dessous
    }
  }
  printLabelFallback({ productName, openedAt, useBy })
  return { mode: "print", printer: saved?.name ?? "Navigateur" }
}
