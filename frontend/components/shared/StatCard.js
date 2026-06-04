import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

export function StatCard({ label, value, accent, loading }) {
  return (
    <Card>
      <CardContent className="p-4 text-center">
        <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
          {label}
        </p>
        {loading ? (
          <Skeleton className="mx-auto mt-2 h-7 w-16" />
        ) : (
          <p className={cn("mt-2 text-2xl font-bold", accent)}>{value}</p>
        )}
      </CardContent>
    </Card>
  )
}
