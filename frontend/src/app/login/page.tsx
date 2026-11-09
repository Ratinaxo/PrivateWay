import { redirect } from "next/navigation"
import { ShieldCheck, LockKeyhole, ServerCog, CircleCheck, ArrowUpRight } from "lucide-react"
import { currentSession } from "@/lib/auth/session"
import { isAuthConfigured } from "@/lib/auth/config"
import { SignInButton } from "@/components/auth/signin-button"

export const dynamic = "force-dynamic"

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  const session = await currentSession()
  if (session?.user?.id) redirect("/")
  const configured = isAuthConfigured()
  const { error } = await searchParams

  return (
    <main className="flex min-h-dvh flex-col bg-[#f7f9f6] text-stone-900 lg:flex-row">
      <section className="relative flex min-h-[290px] flex-col justify-between overflow-hidden bg-emerald-950 px-7 py-8 text-white sm:px-12 lg:min-h-dvh lg:w-[53%] lg:p-16">
        <div className="pointer-events-none absolute -right-32 top-10 size-96 rounded-full border border-white/10" aria-hidden="true" />
        <div className="pointer-events-none absolute -right-10 top-32 size-72 rounded-full border border-white/10" aria-hidden="true" />
        <div className="relative flex items-center gap-3"><span className="flex size-11 items-center justify-center rounded-2xl bg-white/15"><ShieldCheck className="size-6" /></span><span className="text-xl font-bold tracking-tight">PrivateWay</span></div>
        <div className="relative mt-12 max-w-xl lg:mt-0">
          <p className="mb-5 text-xs font-semibold uppercase tracking-[0.24em] text-emerald-200">Tu espacio de trabajo</p>
          <h1 className="text-4xl font-semibold leading-tight tracking-tight sm:text-5xl lg:text-6xl">Conversaciones conectadas. <span className="text-emerald-200">Privacidad primero.</span></h1>
          <p className="mt-6 max-w-md text-sm leading-7 text-emerald-100/80">Un espacio para trabajar con diferentes modelos de lenguaje a través de un único gateway protegido.</p>
        </div>
        <div className="relative mt-9 flex flex-wrap items-center gap-5 text-xs text-emerald-100/80"><span className="inline-flex items-center gap-2"><LockKeyhole className="size-4" /> Acceso mediante OIDC</span><span className="inline-flex items-center gap-2"><CircleCheck className="size-4" /> Protección por defecto</span></div>
      </section>
      <section className="flex flex-1 items-center justify-center px-5 py-12 sm:px-10">
        <div className="w-full max-w-[410px]">
          <div className="mb-9 flex size-14 items-center justify-center rounded-2xl border border-emerald-100 bg-emerald-50 text-emerald-900"><LockKeyhole className="size-6" /></div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-emerald-800">Inicio de sesión seguro</p>
          <h2 className="text-3xl font-semibold tracking-tight">Bienvenido a PrivateWay</h2>
          <p className="mb-8 mt-3 text-sm leading-6 text-stone-500">Accede con la cuenta de tu organización. PrivateWay no almacena contraseñas de usuarios.</p>
          {error && <div role="alert" className="mb-5 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-900">No se pudo completar el inicio de sesión. Comprueba la configuración de identidad o inténtalo nuevamente.</div>}
          {configured ? <SignInButton /> : (
            <div role="status" className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-950">
              <div className="mb-2 flex items-center gap-2 font-semibold"><ServerCog className="size-5" /> Autenticación pendiente de configuración</div>
              <p className="leading-6">Un administrador debe configurar las variables OIDC y el secreto de sesión del frontend antes de habilitar el acceso.</p>
              <p className="mt-3 text-xs text-amber-800">Consulta <code className="font-mono">frontend/README.md</code>. No se habilita ningún usuario de demostración.</p>
            </div>
          )}
          <p className="mt-7 flex items-center gap-2 border-t border-stone-200 pt-6 text-xs leading-5 text-stone-500"><ShieldCheck className="size-4 shrink-0 text-emerald-900" /> Las solicitudes al LLM siguen bloqueadas hasta activar el pipeline de protección.</p>
          <p className="mt-8 text-xs text-stone-400">PrivateWay · Plataforma de acceso privado <ArrowUpRight className="inline size-3" /></p>
        </div>
      </section>
    </main>
  )
}
