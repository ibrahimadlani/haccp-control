"use client"

import { Clock } from "lucide-react"
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export function ComingSoonCard({ title, description }) {
  return (
    <Card className="border-dashed bg-muted/20">
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          <Clock className="h-3.5 w-3.5" />
          Bientôt disponible
        </div>
        <CardTitle className="text-base text-muted-foreground">{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
    </Card>
  )
}
