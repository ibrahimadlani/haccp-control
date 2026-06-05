"use client"

import { useRef, useState } from "react"
import { Camera, Loader2 } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { KioskPhaseShell } from "@/components/kiosk/KioskPhaseShell"
import { uploadEstablishmentDocument } from "@/lib/api/documents"
import { KIOSK_PHASES } from "@/lib/kiosk/phases"
import { useOperator } from "@/lib/contexts/OperatorContext"
import { loadEstablishmentToken } from "@/lib/session/establishment"

const DOC_TYPES = [
  { value: "BL", label: "Bon de livraison (BL)" },
  { value: "LAB_REPORT", label: "Fiche microbiologique" },
]

export default function DocumentScanPage() {
  const { operator } = useOperator()
  const [docType, setDocType] = useState("BL")
  const [file, setFile] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const fileRef = useRef(null)

  async function handleUpload() {
    const token = loadEstablishmentToken()
    if (!token || !operator || !file) return
    setSubmitting(true)
    try {
      const result = await uploadEstablishmentDocument(
        token,
        { pin: operator.pin, operatorId: operator.id },
        { documentType: docType, photo: file },
      )
      toast.success(`Document enregistré${result.url ? "" : ""}`)
      setFile(null)
    } catch (err) {
      toast.error(String(err.message))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <KioskPhaseShell
      phaseId="morning"
      title="Scanner un document"
      backHref={KIOSK_PHASES.morning.route}
    >
      <div className="mx-auto max-w-lg space-y-6 rounded-2xl border-2 border-slate-200 bg-white p-6">
        <div className="space-y-3">
          <Label className="text-[1.2rem]">Type de document</Label>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {DOC_TYPES.map((type) => (
              <button
                key={type.value}
                type="button"
                onClick={() => setDocType(type.value)}
                className={`min-h-[3.5rem] rounded-xl border-2 px-4 text-[1.1rem] font-semibold ${
                  docType === type.value
                    ? "border-sky-500 bg-sky-50 text-sky-900"
                    : "border-slate-200 bg-white"
                }`}
              >
                {type.label}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-3">
          <Label className="text-[1.2rem]">Photo</Label>
          <Button
            type="button"
            variant="outline"
            className="h-24 w-full text-[1.15rem]"
            onClick={() => fileRef.current?.click()}
          >
            <Camera className="mr-2 h-6 w-6" />
            {file ? file.name : "Ouvrir la caméra / galerie"}
          </Button>
          <input
            ref={fileRef}
            type="file"
            accept="image/jpeg,image/png"
            capture="environment"
            className="hidden"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </div>

        <Button
          className="h-14 w-full text-[1.25rem]"
          disabled={!file || submitting}
          onClick={handleUpload}
        >
          {submitting && <Loader2 className="mr-2 h-5 w-5 animate-spin" />}
          Enregistrer sur le coffre-fort
        </Button>
      </div>
    </KioskPhaseShell>
  )
}
