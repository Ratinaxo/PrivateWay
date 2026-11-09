import Link from "next/link"
import { ArrowLeft, CheckCircle2, Clock3, KeyRound, LockKeyhole, ShieldAlert, ShieldCheck } from "lucide-react"
import { requireSession } from "@/lib/auth/session"
import { SignOutButton } from "@/components/auth/signout-button"

export const dynamic = "force-dynamic"

export default async function ConfiguracionPage() {
  const session = await requireSession()
  return (
    <main className="min-h-dvh bg-[#f7f9f6] text-stone-900"><div className="mx-auto max-w-3xl px-5 pb-16 pt-9 sm:px-9 sm:pt-12">
      <header className="mb-10 flex items-center justify-between gap-4"><Link href="/" className="inline-flex items-center gap-2 text-sm font-medium text-stone-600 hover:text-emerald-900"><ArrowLeft className="size-4" /> Volver al chat</Link><span className="inline-flex items-center gap-2 text-sm font-bold text-emerald-900"><ShieldCheck className="size-5" /> PrivateWay</span></header>
      <p className="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-emerald-800">Cuenta y seguridad</p><h1 className="mb-2 text-3xl font-semibold tracking-tight">Configuración</h1><p className="mb-8 text-sm leading-6 text-stone-500">Estado de la sesión y funcionamiento de este entorno de PrivateWay.</p>
      <section className="overflow-hidden rounded-2xl border border-stone-200 bg-white" aria-label="Estado de seguridad">
        <div className="flex items-start gap-3 border-b border-stone-100 p-5 sm:p-6"><CheckCircle2 className="mt-0.5 size-5 shrink-0 text-emerald-800" /><div><h2 className="text-sm font-semibold">Inicio de sesión corporativo</h2><p className="mt-1 text-sm leading-6 text-stone-500">Identidad verificada mediante el proveedor OIDC configurado.</p></div></div>
        <div className="flex items-start gap-3 border-b border-stone-100 p-5 sm:p-6"><Clock3 className="mt-0.5 size-5 shrink-0 text-stone-500" /><div><h2 className="text-sm font-semibold">Sesión limitada</h2><p className="mt-1 text-sm leading-6 text-stone-500">La sesión de PrivateWay tiene una duración máxima configurada de 8 horas y se puede cerrar manualmente.</p></div></div>
        <div className="flex items-start gap-3 border-b border-stone-100 p-5 sm:p-6"><ShieldAlert className="mt-0.5 size-5 shrink-0 text-amber-700" /><div><h2 className="text-sm font-semibold">Protección de prompts en desarrollo</h2><p className="mt-1 text-sm leading-6 text-stone-500">La sesión no habilita automáticamente la salida de mensajes hacia LLM externos. El gateway conserva su política de bloqueo hasta disponer del pipeline.</p></div></div>
        <div className="flex items-start gap-3 p-5 sm:p-6"><KeyRound className="mt-0.5 size-5 shrink-0 text-stone-500" /><div><h2 className="text-sm font-semibold">Gestión de credenciales</h2><p className="mt-1 text-sm leading-6 text-stone-500">Las contraseñas y los mecanismos MFA son administrados por tu organización; los tokens de proveedores LLM no se muestran al navegador.</p></div></div>
      </section>
      <div className="mt-7 flex flex-wrap items-center justify-between gap-4"><Link href="/perfil" className="inline-flex items-center gap-2 text-sm font-semibold text-emerald-800 hover:underline"><LockKeyhole className="size-4" /> Consultar mi perfil</Link><div className="flex flex-wrap gap-3">{session.user.isAdmin && <Link href="/admin" className="rounded-xl border border-stone-200 px-4 py-2.5 text-sm font-medium text-emerald-800 hover:bg-stone-50">Administración</Link>}<SignOutButton /></div></div>
    </div></main>
  )
}
