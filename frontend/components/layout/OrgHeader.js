"use client"

import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { Building2, LogOut } from "lucide-react"
import { Button, buttonVariants } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { cn } from "@/lib/utils"
import { clearOrganisationSession, loadOrganisationContext } from "@/lib/session/organisation"

const NAV = [
  { href: "/organisation", label: "Vue d'ensemble" },
  { href: "/organisation/establishments", label: "Établissements" },
]

export function OrgHeader() {
  const router = useRouter()
  const pathname = usePathname()
  const ctx = loadOrganisationContext()
  const orgName = ctx?.nom_entite ?? "Organisation"

  function handleLogout() {
    clearOrganisationSession()
    router.replace("/organisation/login")
  }

  return (
    <header className="border-b bg-background">
      <div className="flex h-14 items-center gap-4 px-6">
        <Building2 className="h-5 w-5 text-primary" />
        <span className="font-semibold">{orgName}</span>
        <Separator orientation="vertical" className="h-5" />
        <nav className="flex gap-1">
          {NAV.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className={cn(
                buttonVariants({ variant: "ghost", size: "sm" }),
                pathname === href && "bg-accent font-medium"
              )}
            >
              {label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto">
          <Button variant="ghost" size="icon" onClick={handleLogout} aria-label="Déconnecter">
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </header>
  )
}
