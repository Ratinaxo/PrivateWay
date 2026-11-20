"use client"

import { useRouter } from "next/navigation"
import { signOutFederated } from "@/lib/auth/signout"
import { CircleUserRound, Settings, LogOut, LoaderCircle, UsersRound, ScrollText } from "lucide-react"
import { useState } from "react"
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuGroup, DropdownMenuItem,
  DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

export function UserAvatar({ name, size = "sm" }: { name: string; size?: "sm" | "lg" }) {
  const initials = name.trim().split(/\s+/).slice(0, 2).map((part) => part.slice(0, 1).toLocaleUpperCase("es")).join("") || "PW"
  return <span aria-hidden="true" className={`inline-flex shrink-0 items-center justify-center rounded-full bg-emerald-100 font-semibold text-emerald-900 ${size === "lg" ? "size-16 text-xl" : "size-9 text-xs"}`}>{initials}</span>
}

export function ProfileMenu({ name, email, isAdmin = false }: { name: string; email: string | null; isAdmin?: boolean }) {
  const router = useRouter()
  const [busy, setBusy] = useState(false)
  return (
    <DropdownMenu>
      <DropdownMenuTrigger render={<button type="button" aria-label="Abrir menú de perfil" className="flex size-10 items-center justify-center rounded-full border border-stone-200 bg-white hover:bg-stone-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700" />}>
        <UserAvatar name={name} />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        <DropdownMenuGroup><DropdownMenuLabel><div className="flex flex-col gap-1"><span className="truncate text-sm font-medium text-stone-900">{name}</span><span className="truncate text-xs font-normal text-stone-500">{email ?? "Identidad corporativa"}</span></div></DropdownMenuLabel></DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <DropdownMenuItem onClick={() => router.push("/perfil")}><CircleUserRound className="size-4" /> Mi perfil</DropdownMenuItem>
          <DropdownMenuItem onClick={() => router.push("/configuracion")}><Settings className="size-4" /> Configuración</DropdownMenuItem>
          {isAdmin && <DropdownMenuItem onClick={() => router.push("/admin")}><UsersRound className="size-4" /> Administración</DropdownMenuItem>}
          {isAdmin && <DropdownMenuItem onClick={() => router.push("/admin/auditoria")}><ScrollText className="size-4" /> Bitácora y auditoría</DropdownMenuItem>}
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem disabled={busy} variant="destructive" onClick={() => { setBusy(true); void signOutFederated().catch(() => setBusy(false)) }}>
          {busy ? <LoaderCircle className="size-4 animate-spin" /> : <LogOut className="size-4" />}
          {busy ? "Cerrando sesión…" : "Cerrar sesión"}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
