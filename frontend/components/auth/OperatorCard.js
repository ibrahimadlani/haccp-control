import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"

const STATUS_DOT = {
  active: "bg-green-500",
  on_break: "bg-yellow-400",
  clocked_out: "bg-gray-300",
}

export function OperatorCard({ operator, onClick, timeclockStatus }) {
  const initials = `${(operator.prenom ?? operator.first_name ?? "?")[0]}${(operator.nom ?? operator.last_name ?? "?")[0]}`.toUpperCase()
  const name = operator.nom_complet ?? `${operator.prenom ?? operator.first_name ?? ""} ${operator.nom ?? operator.last_name ?? ""}`.trim()
  const role = operator.role ?? operator.role_name ?? ""
  const dotColor = STATUS_DOT[timeclockStatus] ?? STATUS_DOT.clocked_out

  return (
    <Card
      className="cursor-pointer transition-colors hover:bg-accent"
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === "Enter" && onClick()}
    >
      <CardContent className="flex flex-col items-center gap-3 p-6">
        <div className="relative">
          <Avatar className="h-14 w-14">
            <AvatarFallback className="text-lg font-semibold">{initials}</AvatarFallback>
          </Avatar>
          {timeclockStatus !== undefined && (
            <span
              className={`absolute bottom-0 right-0 h-3.5 w-3.5 rounded-full border-2 border-background ${dotColor}`}
            />
          )}
        </div>
        <div className="text-center">
          <p className="font-medium">{name}</p>
          {role && (
            <Badge variant="outline" className="mt-1 text-xs">
              {role}
            </Badge>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
