import Link from "next/link"
import { ArrowLeft, ShieldCheck, ScrollText } from "lucide-react"
import { requireAdminSession } from "@/lib/auth/session"
import { getAuditSnapshot } from "@/lib/gateway/audit"
import { AuditDashboard } from "@/components/admin/audit-dashboard"

export const dynamic = "force-dynamic"

export default async function AuditPage() {
  // La autorización es del lado del servidor y vuelve a comprobar Keycloak.
  await requireAdminSession()
  let snapshot: Awaited<ReturnType<typeof getAuditSnapshot>> | null = null
  let error = false
  try { snapshot = await getAuditSnapshot() } catch { error = true }
  return (
    <main className="min-h-dvh bg-[#f7f9f6] px-5 pb-16 pt-8 text-stone-900 sm:px-8">
      <div className="mx-auto max-w-7xl space-y-7">
        <header className="flex items-center justify-between gap-3">
          <Link href="/admin" className="inline-flex items-center gap-2 text-sm text-stone-600 hover:text-emerald-800"><ArrowLeft className="size-4" /> Administración</Link>
          <span className="inline-flex items-center gap-2 font-semibold text-emerald-900"><ShieldCheck className="size-5" /> PrivateWay</span>
        </header>
        <div className="flex items-center gap-4">
          <span className="flex size-14 items-center justify-center rounded-2xl bg-emerald-900 text-white"><ScrollText className="size-7" /></span>
          <div><p className="text-xs font-semibold uppercase tracking-wider text-emerald-800">Solo administradores</p><h1 className="mt-1 text-3xl font-semibold">Bitácora y auditoría</h1><p className="mt-2 text-sm text-stone-500">Metadatos verificables; vista cifrada de mensajes originales y seudonimizados, solo para administradores</p></div>
        </div>
        {error || !snapshot ? (
          <section role="alert" className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">
            No se pudo verificar o leer la bitácora. Comprueba que PRIVATEWAY_AUDIT_READ_TOKEN está configurado en .env y que el backend está disponible. Si se alteró un registro, la vista falla sin mostrar resultados parciales.
          </section>
        ) : <AuditDashboard snapshot={snapshot} />}
      </div>
    </main>
  )
}
