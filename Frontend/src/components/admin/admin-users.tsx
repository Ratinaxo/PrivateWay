"use client"

import { useCallback, useEffect, useState } from "react"
import type { FormEvent } from "react"
import { CirclePlus, KeyRound, LoaderCircle, RefreshCw, Search, Shield, ShieldOff, UserRoundCheck, UserRoundX } from "lucide-react"
import type { ManagedUser } from "@/lib/keycloak/admin"

type NewAccount = { username: string; firstName: string; lastName: string; email: string; password: string }
const EMPTY: NewAccount = { username: "", firstName: "", lastName: "", email: "", password: "" }

const ERROR_MESSAGES: Record<string, string> = {
  CUENTA_DUPLICADA: "La cuenta o el correo ya existe en Keycloak.",
  NO_AUTENTICADO: "La sesión expiró. Vuelve a iniciar sesión.",
  NO_AUTORIZADO: "Tu cuenta ya no tiene permisos de administrador.",
  CUENTA_DE_SERVICIO_PROTEGIDA: "Las cuentas técnicas de Keycloak no se administran desde esta consola.",
  RETIRAR_ROL_ADMIN_ANTES: "Retira primero el rol de administrador para deshabilitar esta cuenta.",
  NO_PUEDE_DESHABILITARSE: "No puedes deshabilitar tu propia cuenta.",
  NO_PUEDE_RETIRARSE_ADMIN: "No puedes quitarte a ti mismo el rol administrador.",
  ULTIMO_ADMINISTRADOR: "Debe existir al menos un administrador activo.",
  DATOS_INVALIDOS: "Revisa el formulario. La contraseña necesita al menos 12 caracteres.",
  IDENTIDAD_INACCESIBLE: "Keycloak no está disponible. Inténtalo nuevamente.",
  IDENTIDAD_PERMISOS_INSUFICIENTES: "El servicio de administración no dispone de permisos suficientes.",
  CAMBIO_PERSONAL_EN_KEYCLOAK: "Cambia tu propia contraseña desde la cuenta de Keycloak.",
}

function apiError(code: string) { return ERROR_MESSAGES[code] || "No se completó la operación. Comprueba los logs de Keycloak." }

async function parseReply(response: Response) {
  if (response.ok) return
  let code = "OPERACION_IDENTIDAD_FALLIDA"
  try {
    const data = await response.json() as { error?: { code?: string } }
    if (typeof data.error?.code === "string") code = data.error.code
  } catch { /* nunca revelar respuestas internas */ }
  throw new Error(apiError(code))
}

const inputStyle = "w-full rounded-xl border border-stone-200 bg-white px-3 py-2.5 text-sm text-stone-900 outline-offset-2 focus:outline-emerald-800"
const smallButton = "inline-flex items-center justify-center gap-1.5 rounded-lg border border-stone-200 bg-white px-3 py-2 text-xs font-medium text-stone-700 hover:bg-stone-50 disabled:cursor-not-allowed disabled:opacity-50"

export function AdminUsers({ actingUserId }: { actingUserId: string }) {
  const [users, setUsers] = useState<ManagedUser[]>([])
  const [search, setSearch] = useState("")
  const [appliedSearch, setAppliedSearch] = useState("")
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState("")
  const [message, setMessage] = useState("")
  const [form, setForm] = useState<NewAccount>(EMPTY)
  const [resetId, setResetId] = useState<string | null>(null)
  const [resetPassword, setResetPassword] = useState("")

  const refresh = useCallback(async (query: string) => {
    setLoading(true)
    setError("")
    try {
      const response = await fetch(`/api/admin/usuarios?search=${encodeURIComponent(query)}`, { cache: "no-store", credentials: "same-origin" })
      await parseReply(response)
      const data = await response.json() as { users: ManagedUser[] }
      setUsers(data.users)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudieron cargar las cuentas.")
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { void refresh(appliedSearch) }, [refresh, appliedSearch])

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy("new"); setError(""); setMessage("")
    try {
      const response = await fetch("/api/admin/usuarios", {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify(form),
      })
      await parseReply(response)
      setForm(EMPTY)
      setMessage("Cuenta creada. La contraseña ingresada es temporal y deberá cambiarse al iniciar sesión.")
      await refresh(appliedSearch)
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Error al crear la cuenta.") }
    finally { setBusy(null) }
  }

  async function act(user: ManagedUser, action: string, value: boolean | string) {
    if (action === "set-enabled" && value === false && !window.confirm(`¿Deshabilitar a ${user.username}? Perderá el acceso en su próxima solicitud.`)) return
    if (action === "set-admin" && !window.confirm(`${value ? "Conceder" : "Retirar"} permisos de administración a ${user.username}?`)) return
    setBusy(user.id); setError(""); setMessage("")
    try {
      const response = await fetch(`/api/admin/usuarios/${user.id}`, {
        method: "PATCH", credentials: "same-origin",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action, value }),
      })
      await parseReply(response)
      setMessage("Los cambios se guardaron correctamente en Keycloak.")
      setResetId(null); setResetPassword("")
      await refresh(appliedSearch)
    } catch (cause) { setError(cause instanceof Error ? cause.message : "No se pudo modificar la cuenta.") }
    finally { setBusy(null) }
  }

  return (
    <div className="grid gap-7 lg:grid-cols-[minmax(0,1.65fr)_minmax(310px,1fr)]">
      {(error || message) && <div className="lg:col-span-2">
        {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-900">{error}</p>}
        {message && <p role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-950">{message}</p>}
      </div>}
      <section className="min-w-0 rounded-2xl border border-stone-200 bg-white p-5 shadow-sm sm:p-6" aria-label="Cuentas de usuario">
        <div className="mb-5 flex flex-wrap items-center justify-between gap-2"><div><h2 className="text-lg font-semibold">Cuentas registradas</h2><p className="mt-1 text-xs text-stone-500">Se muestran hasta 100 resultados. Usa la búsqueda para filtrar.</p></div><button type="button" onClick={() => void refresh(appliedSearch)} className={smallButton} disabled={loading || busy !== null}><RefreshCw className="size-4" /> Actualizar</button></div>
        <form className="mb-5 flex gap-2" onSubmit={(event) => { event.preventDefault(); setAppliedSearch(search.trim()) }}>
          <input aria-label="Buscar por usuario o correo" value={search} onChange={(event) => setSearch(event.target.value)} maxLength={80} placeholder="Buscar nombre o correo" className={inputStyle} />
          <button type="submit" className="inline-flex items-center gap-2 rounded-xl bg-emerald-900 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-800"><Search className="size-4" /> Buscar</button>
        </form>
        {loading ? <p role="status" className="flex items-center gap-2 py-7 text-sm text-stone-500"><LoaderCircle className="size-4 animate-spin" /> Consultando Keycloak…</p> : users.length === 0 ? <p className="py-8 text-center text-sm text-stone-500">No hay usuarios que coincidan con la búsqueda.</p> : (
          <div className="space-y-3">{users.map((user) => (
            <article key={user.id} className="rounded-xl border border-stone-200 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><p className="font-semibold text-stone-900">{user.username} {user.id === actingUserId && <span className="ml-1 text-xs font-normal text-stone-500">(tu cuenta)</span>}</p><p className="mt-0.5 break-all text-xs text-stone-500">{user.email || "Sin correo"}</p><p className="mt-1 text-xs text-stone-600">{[user.firstName, user.lastName].filter(Boolean).join(" ")}</p></div><div className="flex flex-wrap gap-1.5"><span className={`rounded-full px-2 py-1 text-[11px] font-medium ${user.enabled ? "bg-emerald-50 text-emerald-800" : "bg-stone-100 text-stone-600"}`}>{user.enabled ? "Activo" : "Inactivo"}</span>{user.isAdmin && <span className="rounded-full bg-sky-50 px-2 py-1 text-[11px] font-medium text-sky-900">Administrador</span>}</div></div>
              <div className="mt-4 flex flex-wrap gap-2">
                <button type="button" className={smallButton} disabled={busy !== null || user.id === actingUserId || (user.enabled && user.isAdmin)} onClick={() => void act(user, "set-enabled", !user.enabled)}>{user.enabled ? <UserRoundX className="size-4" /> : <UserRoundCheck className="size-4" />}{user.enabled ? "Deshabilitar" : "Habilitar"}</button>
                <button type="button" className={smallButton} disabled={busy !== null || user.id === actingUserId || (!user.enabled && !user.isAdmin)} onClick={() => void act(user, "set-admin", !user.isAdmin)}>{user.isAdmin ? <ShieldOff className="size-4" /> : <Shield className="size-4" />}{user.isAdmin ? "Retirar admin" : "Hacer admin"}</button>
                <button type="button" className={smallButton} disabled={busy !== null || user.id === actingUserId} onClick={() => { setResetId(resetId === user.id ? null : user.id); setResetPassword("") }}><KeyRound className="size-4" /> Contraseña temporal</button>
              </div>
              {resetId === user.id && <form className="mt-4 flex flex-col gap-2 border-t border-stone-100 pt-4" onSubmit={(event) => { event.preventDefault(); void act(user, "reset-password", resetPassword) }}><label htmlFor={`reset-${user.id}`} className="text-xs font-medium">Nueva contraseña temporal (mínimo 12 caracteres)</label><input id={`reset-${user.id}`} type="password" autoComplete="new-password" minLength={12} maxLength={128} required value={resetPassword} onChange={(event) => setResetPassword(event.target.value)} className={inputStyle} /><button type="submit" disabled={busy !== null} className="self-start rounded-lg bg-stone-900 px-3 py-2 text-xs font-medium text-white disabled:opacity-50">Guardar contraseña temporal</button></form>}
            </article>
          ))}</div>
        )}
      </section>

      <section className="h-fit rounded-2xl border border-stone-200 bg-white p-5 shadow-sm sm:p-6" aria-labelledby="crear-cuenta">
        <h2 id="crear-cuenta" className="mb-1 flex items-center gap-2 text-lg font-semibold"><CirclePlus className="size-5 text-emerald-800" /> Crear usuario</h2>
        <p className="mb-6 text-xs leading-5 text-stone-500">Las nuevas cuentas se crean con rol de usuario y deben modificar su contraseña en el primer acceso.</p>
        <form onSubmit={(event) => void create(event)} className="space-y-4">
          <label className="block space-y-1.5 text-xs font-medium">Nombre de usuario<input className={inputStyle} required minLength={3} maxLength={64} pattern="[a-zA-Z][a-zA-Z0-9._-]{2,63}" autoComplete="off" value={form.username} onChange={(event) => setForm({ ...form, username: event.target.value })} /></label>
          <label className="block space-y-1.5 text-xs font-medium">Nombre<input className={inputStyle} maxLength={80} value={form.firstName} onChange={(event) => setForm({ ...form, firstName: event.target.value })} /></label>
          <label className="block space-y-1.5 text-xs font-medium">Apellido<input className={inputStyle} maxLength={80} value={form.lastName} onChange={(event) => setForm({ ...form, lastName: event.target.value })} /></label>
          <label className="block space-y-1.5 text-xs font-medium">Correo electrónico<input className={inputStyle} type="email" required maxLength={254} autoComplete="off" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} /></label>
          <label className="block space-y-1.5 text-xs font-medium">Contraseña temporal<input className={inputStyle} type="password" required minLength={12} maxLength={128} autoComplete="new-password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} /></label>
          <button type="submit" disabled={busy !== null} className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-emerald-900 px-4 py-3 text-sm font-semibold text-white hover:bg-emerald-800 disabled:opacity-60">{busy === "new" ? <LoaderCircle className="size-4 animate-spin" /> : <CirclePlus className="size-4" />}{busy === "new" ? "Creando usuario…" : "Crear cuenta"}</button>
        </form>
      </section>
    </div>
  )
}
