import { Badge } from "@/components/ui/badge"

const STATUS_MAP = {
  // Non-conformity
  OPEN: { label: "Ouverte", variant: "destructive" },
  IN_PROGRESS: { label: "En cours", variant: "default" },
  RESOLVED: { label: "Résolue", variant: "secondary" },
  CLOSED: { label: "Clôturée", variant: "outline" },
  // Subscription
  ACTIVE: { label: "Actif", variant: "default" },
  TRIALING: { label: "Essai", variant: "secondary" },
  PAST_DUE: { label: "Impayé", variant: "destructive" },
  CANCELED: { label: "Annulé", variant: "outline" },
  // Supplier approval
  pending: { label: "En attente", variant: "secondary" },
  approved: { label: "Agréé", variant: "default" },
  rejected: { label: "Refusé", variant: "destructive" },
  occasional: { label: "Occasionnel", variant: "outline" },
}

export function StatusBadge({ status }) {
  const { label, variant } = STATUS_MAP[status] ?? { label: status, variant: "outline" }
  return <Badge variant={variant}>{label}</Badge>
}
