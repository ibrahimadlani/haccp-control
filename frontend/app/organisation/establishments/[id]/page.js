"use client"

import { useEffect, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { PageHeader } from "@/components/shared/PageHeader"
import { getSiteEquipments } from "@/lib/api/equipment"
import { getSiteUsers } from "@/lib/api/organisation"
import { loadOrganisationToken } from "@/lib/session/organisation"

export default function EstablishmentDetailPage({ params }) {
  const { id } = params
  const [equipments, setEquipments] = useState([])
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = loadOrganisationToken()
    if (!token) return
    setLoading(true)
    Promise.all([getSiteEquipments(token, id), getSiteUsers(token, id)])
      .then(([eq, us]) => {
        setEquipments(eq?.items ?? [])
        setUsers(us?.items ?? [])
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [id])

  return (
    <div className="space-y-6">
      <PageHeader title="Détail établissement" description={`ID : ${id}`} />

      <Tabs defaultValue="equipment">
        <TabsList>
          <TabsTrigger value="equipment">Équipements</TabsTrigger>
          <TabsTrigger value="users">Utilisateurs</TabsTrigger>
        </TabsList>

        <TabsContent value="equipment">
          <div className="rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Nom</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Seuils (°C)</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow><TableCell colSpan={3} className="text-center text-muted-foreground">Chargement…</TableCell></TableRow>
                ) : equipments.map((eq) => (
                  <TableRow key={eq.id}>
                    <TableCell className="font-medium">{eq.name}</TableCell>
                    <TableCell><Badge variant="outline">{eq.equipment_type}</Badge></TableCell>
                    <TableCell className="tabular-nums">{eq.min_target_temperature} / {eq.max_target_temperature}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </TabsContent>

        <TabsContent value="users">
          <div className="rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Nom</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Rôle</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow><TableCell colSpan={3} className="text-center text-muted-foreground">Chargement…</TableCell></TableRow>
                ) : users.map((u) => (
                  <TableRow key={u.utilisateur_id ?? u.id}>
                    <TableCell className="font-medium">{u.prenom} {u.nom}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{u.email}</TableCell>
                    <TableCell><Badge variant="outline">{u.role_name}</Badge></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}
