import { getServerSession } from "next-auth"
import { redirect } from "next/navigation"
import { authOptions, isAuthConfigured } from "./config"
import { readAccountPrivileges } from "@/lib/keycloak/admin"

/**
 * En cada solicitud se comprueba en Keycloak si la cuenta sigue habilitada
 * y si mantiene el rol administrador. El JWT del navegador NO autoriza acciones.
 * Si Keycloak no responde, el BFF falla cerrado.
 */
export async function currentSession() {
  if (!isAuthConfigured()) return null
  const session = await getServerSession(authOptions)
  if (!session?.user?.id) return null
  try {
    const privileges = await readAccountPrivileges(session.user.id)
    if (!privileges.enabled) return null
    session.user.isAdmin = privileges.isAdmin
    return session
  } catch {
    return null
  }
}

export async function requireSession() {
  const session = await currentSession()
  if (!session?.user?.id) redirect("/login")
  return session
}

export async function requireAdminSession() {
  const session = await requireSession()
  if (!session.user.isAdmin) redirect("/")
  return session
}
