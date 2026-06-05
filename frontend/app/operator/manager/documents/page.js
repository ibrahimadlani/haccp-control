"use client"

import { useRouter } from "next/navigation"
import { KioskActionGrid } from "@/components/kiosk/KioskActionGrid"
import { KioskActionTile } from "@/components/kiosk/KioskActionTile"
import { KioskBackButton } from "@/components/kiosk/KioskBackButton"

const FOLDERS = [
  { emoji: "🐀", title: "Dératisation / nuisibles", hint: "Rapports prestataires" },
  { emoji: "🏛️", title: "Audits DDPP", hint: "Contrôles officiels" },
  { emoji: "🧫", title: "Analyses microbiologiques", hint: "Laboratoires partenaires" },
  { emoji: "📋", title: "Bons de livraison", hint: "Archives photos BL" },
]

export default function ManagerDocumentsPage() {
  const router = useRouter()

  return (
    <div className="flex flex-1 flex-col gap-5">
      <div className="flex items-center justify-between">
        <KioskBackButton href="/operator/manager" label="MANAGER" />
        <h1 className="text-[1.5rem] font-extrabold">Coffre-fort</h1>
      </div>

      <KioskActionGrid>
        {FOLDERS.map((folder) => (
          <KioskActionTile
            key={folder.title}
            emoji={folder.emoji}
            title={folder.title}
            subtitle={folder.hint}
            onClick={() => router.push("/operator/morning/documents")}
          />
        ))}
      </KioskActionGrid>

      <p className="text-center text-[1.05rem] text-slate-500">
        Les documents scannés depuis la tablette sont stockés sur MinIO/S3.
      </p>
    </div>
  )
}
