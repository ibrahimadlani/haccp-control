"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"
import { loadEstablishmentToken } from "@/lib/session/establishment"
import { loadOrganisationToken } from "@/lib/session/organisation"
import { loadEstablishmentId } from "@/lib/session/establishment"

export default function RootPage() {
  const router = useRouter()

  useEffect(() => {
    if (loadOrganisationToken()) {
      router.replace("/organisation")
      return
    }
    if (loadEstablishmentToken()) {
      router.replace("/profiles")
      return
    }
    if (loadEstablishmentId()) {
      router.replace("/login")
      return
    }
    router.replace("/setup")
  }, [router])

  return null
}
