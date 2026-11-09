import Link from "next/link"
import { ArrowLeft, ShieldCheck, UsersRound, LockKeyhole } from "lucide-react"
import { requireAdminSession } from "@/lib/auth/session"
import { AdminUsers } from "@/components/admin/admin-users"

export const dynamic = "force-dynamic"

export default async function AdminPage() {
  const session = await requireAdminSession()
  return (
    <main className="min-h-dvh bg-[#f7f9f6] px-5 pb-16 pt-8 text-stone-900 sm:px-8">
      <div className="mx-auto max-w-6xl">
        <header className="mb-9 flex flex-wrap items-center justify-between gap-4">
          <Link href="/" className="inline-flex items-center gap-2 text-sm font-medium text-stone-600 hover:text-emerald-900"><ArrowLeft className="size-4" /> Volver al chat</Link>
          <span className="inline-flex items-center gap-2 text-sm font-bold text-emerald-900"><ShieldCheck className="size-5" /> PrivateWay</span>
        </header>
        <div className="mb-8 flex flex-wrap items-center gap-4">
          <span className="flex size-14 items-center justify-center rounded-2xl bg-emerald-900 text-white"><UsersRound className="size-7" /></span>
          <div><p className="text-xs font-semibold uppercase tracking-[0.16em] text-emerald-800">Acceso restringido</p><h1 className="mt-1 text-3xl font-semibold tracking-tight">Administración de usuarios</h1><p className="mt-2 text-sm text-stone-500">Keycloak · Realm privateway · Administrador: {session.user.name || session.user.id}</p></div>
        </div>
        <div className="mb-7 flex items-start gap-3 rounded-xl border border-stone-200 bg-white p-4 text-sm text-stone-600"><LockKeyhole className="mt-0.5 size-5 shrink-0 text-emerald-800" /><p>Las contraseñas se guardan únicamente en Keycloak. Los cambios de rol y estado se comprueban en el servidor antes de ejecutarse. Esta consola no elimina cuentas ni historiales.</p></div>
        <AdminUsers actingUserId={session.user.id} />
      </div>
    </main>
  )
}
