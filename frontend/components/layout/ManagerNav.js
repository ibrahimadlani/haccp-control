"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { BarChart3, Settings2, Users, AlertTriangle, Truck, SprayCan, SlidersHorizontal, ShoppingBasket, ChefHat } from "lucide-react"
import { cn } from "@/lib/utils"
import { buttonVariants } from "@/components/ui/button"

const NAV_ITEMS = [
  { href: "/manager", label: "Tableau de bord", icon: BarChart3 },
  { href: "/manager/equipment", label: "Équipements", icon: Settings2 },
  { href: "/manager/staff", label: "Personnel", icon: Users },
  { href: "/manager/suppliers", label: "Fournisseurs", icon: Truck },
  { href: "/manager/products", label: "Catalogue", icon: ShoppingBasket },
  { href: "/manager/nonconformities", label: "Non-conformités", icon: AlertTriangle },
  { href: "/manager/cleaning", label: "Plan sanitaire", icon: SprayCan },
  { href: "/manager/production", label: "Production", icon: ChefHat },
  { href: "/manager/settings", label: "Paramètres", icon: SlidersHorizontal },
]

export function ManagerNav() {
  const pathname = usePathname()

  return (
    <nav className="flex flex-row gap-1 overflow-x-auto border-b bg-background px-4 py-2 md:flex-col md:border-b-0 md:border-r md:px-2 md:py-4">
      {NAV_ITEMS.map(({ href, label, icon: Icon }) => (
        <Link
          key={href}
          href={href}
          className={cn(
            buttonVariants({ variant: "ghost", size: "sm" }),
            "shrink-0 justify-start gap-2",
            pathname === href && "bg-accent font-medium text-accent-foreground"
          )}
        >
          <Icon className="h-4 w-4" />
          <span className="hidden sm:inline">{label}</span>
        </Link>
      ))}
    </nav>
  )
}
