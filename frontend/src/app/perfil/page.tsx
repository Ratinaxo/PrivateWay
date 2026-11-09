import Link from "next/link"
import { ArrowLeft, BadgeCheck, CircleUserRound, Fingerprint, LockKeyhole, Mail, ShieldCheck } from "lucide-react"
import { requireSession } from "@/lib/auth/session"
import { UserAvatar } from "@/components/profile-menu"
import { SignOutButton } from "@/components/auth/signout-button"

export const dynamic = "force-dynamic"

export default async function PerfilPage() {
  const session = await requireSession()
  const name = session.user.name || "Usuario"
  const identityAccountUrl = process.env.PRIVATEWAY_OIDC_ISSUER?.replace(/\/+$/, "") + "/account/"
  return (
    <main className="min-h-dvh bg-[#f7f9f6] text-stone-900">
      <div className="mx-auto max-w-4xl px-5 pb-16 pt-9 sm:px-9 sm:pt-12">
        <header className="mb-10 flex flex-wrap items-center justify-between gap-4">
          <Link href="/" className="inline-flex items-center gap-2 text-sm font-medium text-stone-600 hover:text-emerald-900"><ArrowLeft className="size-4" /> Volver a conversaciones</Link>
          <span className="inline-flex items-center gap-2 text-sm font-bold text-emerald-900"><ShieldCheck className="size-5" /> PrivateWay</span>
        </header>
        <div className="mb-8"><p className="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-emerald-800">Cuenta</p><h1 className="text-3xl font-semibold tracking-tight">Mi perfil</h1><p className="mt-2 text-sm text-stone-500">Información obtenida de tu proveedor de identidad corporativa.</p></div>
        <section className="overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-sm" aria-labelledby="perfil-usuario">
          <div className="flex flex-wrap items-center gap-5 border-b border-stone-100 p-6 sm:p-8"><UserAvatar name={name} size="lg" /><div className="min-w-0 flex-1"><h2 id="perfil-usuario" className="break-words text-xl font-semibold">{name}</h2><p className="mt-1 break-all text-sm text-stone-500">{session.user.email || "Sin correo proporcionado"}</p><p className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-900"><BadgeCheck className="size-3.5" /> Sesión OIDC activa</p></div></div>
          <dl className="grid gap-6 p-6 sm:grid-cols-2 sm:p-8">
            <div><dt className="flex items-center gap-2 text-xs font-medium text-stone-500"><CircleUserRound className="size-4" /> Nombre de cuenta</dt><dd className="mt-2 break-words text-sm font-semibold">{name}</dd></div>
            <div><dt className="flex items-center gap-2 text-xs font-medium text-stone-500"><Mail className="size-4" /> Correo informado por el proveedor</dt><dd className="mt-2 break-all text-sm font-semibold">{session.user.email || "No disponible"}</dd></div>
            <div><dt className="flex items-center gap-2 text-xs font-medium text-stone-500"><Fingerprint className="size-4" /> Identificador OIDC</dt><dd className="mt-2 break-all font-mono text-xs text-stone-700">{session.user.id}</dd></div>
            <div><dt className="flex items-center gap-2 text-xs font-medium text-stone-500"><LockKeyhole className="size-4" /> Autenticación</dt><dd className="mt-2 text-sm font-semibold">Proveedor corporativo (OIDC)</dd></div>
          </dl>
        </section>
        <div className="mt-6 grid gap-5 sm:grid-cols-[1fr_auto] sm:items-center"><p className="text-sm leading-6 text-stone-500">Tu nombre, correo y credenciales se administran en tu proveedor de identidad. PrivateWay no permite cambiar tu contraseña desde aquí.</p><div className="flex flex-wrap gap-3"><a href={identityAccountUrl} target="_blank" rel="noopener noreferrer" className="inline-flex items-center rounded-xl border border-stone-200 px-4 py-2.5 text-sm font-medium text-emerald-800 hover:bg-stone-50">Gestionar mi cuenta en Keycloak</a>{session.user.isAdmin && <Link href="/admin" className="inline-flex items-center rounded-xl border border-stone-200 px-4 py-2.5 text-sm font-medium text-emerald-800 hover:bg-stone-50">Administración</Link>}<SignOutButton /></div></div>
      </div>
    </main>
  )
}
