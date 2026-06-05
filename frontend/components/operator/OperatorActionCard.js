"use client"

import { ChevronRight } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"

export function OperatorActionCard({
  icon: Icon,
  title,
  description,
  onClick,
  disabled = false,
  variant = "default",
  badge,
  className,
}) {
  return (
    <Card className={cn(disabled && "opacity-55", className)}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-primary/10">
            <Icon className="h-6 w-6 text-primary" />
          </div>
          {badge ? (
            <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-primary">
              {badge}
            </span>
          ) : null}
        </div>
        <CardTitle className="mt-3 text-lg">{title}</CardTitle>
        <CardDescription className="text-sm leading-relaxed">{description}</CardDescription>
      </CardHeader>
      <CardContent>
        <Button
          className="h-12 w-full text-base"
          variant={variant === "outline" ? "outline" : "default"}
          onClick={onClick}
          disabled={disabled}
        >
          {disabled ? "Indisponible" : "Ouvrir"}
          {!disabled && <ChevronRight className="ml-1 h-4 w-4" />}
        </Button>
      </CardContent>
    </Card>
  )
}
