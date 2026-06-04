"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"
import { OrgHeader } from "@/components/layout/OrgHeader"
import { loadOrganisationToken } from "@/lib/session/organisation"

export default function OrgLayout({ children }) {
  const router = useRouter()

  useEffect(() => {
    if (!loadOrganisationToken()) {
      router.replace("/organisation/login")
    }
  }, [router])

  if (typeof window !== "undefined" && !loadOrganisationToken()) return null

  return (
    <div className="flex min-h-screen flex-col">
      <OrgHeader />
      <main className="flex-1 p-4 sm:p-6">{children}</main>
    </div>
  )
}
