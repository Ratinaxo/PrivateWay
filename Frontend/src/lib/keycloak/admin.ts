/**
 * Integración PRIVADA con la API administrativa de Keycloak.
 * Las credenciales del cliente de servicio nunca salen del servidor Next.js.
 */
import "server-only"

const REALM = "privateway"
const USER_ROLE = "privateway-user"
const ADMIN_ROLE = "privateway-admin"
const USER_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

export class IdentityError extends Error {
  constructor(public readonly code: string, public readonly status: number) {
    super(code)
  }
}

export type ManagedUser = {
  id: string
  username: string
  firstName: string
  lastName: string
  email: string
  enabled: boolean
  isAdmin: boolean
}

type KcUser = {
  id: string
  username?: string
  firstName?: string
  lastName?: string
  email?: string
  enabled?: boolean
}
type RealmRole = { id: string; name: string }

function baseUrl(): string {
  const configured = process.env.PRIVATEWAY_KEYCLOAK_INTERNAL_URL || "http://keycloak:8081"
  try {
    const url = new URL(configured)
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.pathname !== '/' || url.search || url.hash) throw new Error()
    return url.origin
  } catch {
    throw new IdentityError("IDENTIDAD_NO_CONFIGURADA", 503)
  }
}

async function adminToken(): Promise<string> {
  const id = process.env.PRIVATEWAY_KEYCLOAK_ADMIN_CLIENT_ID
  const secret = process.env.PRIVATEWAY_KEYCLOAK_ADMIN_CLIENT_SECRET
  if (!id || !secret) throw new IdentityError("IDENTIDAD_NO_CONFIGURADA", 503)
  try {
    const response = await fetch(`${baseUrl()}/realms/${REALM}/protocol/openid-connect/token`, {
      method: "POST",
      body: new URLSearchParams({ grant_type: "client_credentials", client_id: id, client_secret: secret }),
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(10_000),
    })
    if (!response.ok) throw new Error("Token no disponible")
    const data: unknown = await response.json()
    if (!data || typeof data !== "object" || !("access_token" in data) || typeof data.access_token !== "string") throw new Error("Token inválido")
    return data.access_token
  } catch {
    throw new IdentityError("IDENTIDAD_INACCESIBLE", 503)
  }
}

async function adminFetch(token: string, endpoint: string, method = "GET", body?: unknown): Promise<Response> {
  if (!endpoint.startsWith("/") || endpoint.startsWith("//")) throw new IdentityError("RUTA_INVALIDA", 500)
  let response: Response
  try {
    response = await fetch(`${baseUrl()}/admin/realms/${REALM}${endpoint}`, {
      method,
      headers: { Authorization: `Bearer ${token}`, ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(10_000),
    })
  } catch {
    throw new IdentityError("IDENTIDAD_INACCESIBLE", 503)
  }
  if (response.status === 404) throw new IdentityError("USUARIO_NO_ENCONTRADO", 404)
  if (response.status === 409) throw new IdentityError("CUENTA_DUPLICADA", 409)
  if (response.status === 403 || response.status === 401) throw new IdentityError("IDENTIDAD_PERMISOS_INSUFICIENTES", 503)
  if (!response.ok) throw new IdentityError("OPERACION_IDENTIDAD_FALLIDA", 502)
  return response
}

async function adminJson<T>(token: string, path: string): Promise<T> {
  return await (await adminFetch(token, path)).json() as T
}

function requireId(id: string): string {
  if (!USER_ID.test(id)) throw new IdentityError("IDENTIFICADOR_INVALIDO", 422)
  return id
}

async function userWithToken(token: string, id: string): Promise<KcUser> {
  return adminJson<KcUser>(token, `/users/${requireId(id)}`)
}

async function rolesForUser(token: string, id: string): Promise<RealmRole[]> {
  return adminJson<RealmRole[]>(token, `/users/${requireId(id)}/role-mappings/realm`)
}

/** Revalidación autoritativa: no confiar en roles ni estado guardados en JWT. */
export async function readAccountPrivileges(id: string): Promise<{ enabled: boolean; isAdmin: boolean }> {
  const token = await adminToken()
  const user = await userWithToken(token, id)
  if (user.enabled !== true) return { enabled: false, isAdmin: false }
  const roles = await rolesForUser(token, id)
  const isAdmin = roles.some((role) => role.name === ADMIN_ROLE)
  // La cuenta debe disponer explícitamente del rol usuario o administrador.
  // Estar habilitado en el realm por sí solo no da acceso a PrivateWay.
  return { enabled: isAdmin || roles.some((role) => role.name === USER_ROLE), isAdmin }
}

export async function listManagedUsers(search = ""): Promise<ManagedUser[]> {
  const token = await adminToken()
  const params = new URLSearchParams({ first: "0", max: "100" })
  if (search.trim()) params.set("search", search.trim().slice(0, 80))
  const [users, adminUsers] = await Promise.all([
    adminJson<KcUser[]>(token, `/users?${params}`),
    adminJson<KcUser[]>(token, `/roles/${ADMIN_ROLE}/users?first=0&max=500`),
  ])
  const admins = new Set(adminUsers.map((user) => user.id))
  return users.filter((user) => !user.username?.startsWith("service-account-")).map((user) => ({
    id: user.id,
    username: user.username || "",
    firstName: user.firstName || "",
    lastName: user.lastName || "",
    email: user.email || "",
    enabled: user.enabled === true,
    isAdmin: admins.has(user.id),
  }))
}

const USERNAME = /^[a-zA-Z][a-zA-Z0-9._-]{2,63}$/
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
function passwordIsValid(password: unknown): password is string {
  return typeof password === "string" && password.length >= 12 && password.length <= 128 && !/\p{Cc}/u.test(password)
}

export async function createManagedUser(data: unknown): Promise<void> {
  if (!data || typeof data !== "object") throw new IdentityError("DATOS_INVALIDOS", 422)
  const obj = data as Record<string, unknown>
  const username = typeof obj.username === "string" ? obj.username.trim() : ""
  const firstName = typeof obj.firstName === "string" ? obj.firstName.trim() : ""
  const lastName = typeof obj.lastName === "string" ? obj.lastName.trim() : ""
  const email = typeof obj.email === "string" ? obj.email.trim() : ""
  if (!USERNAME.test(username) || username.startsWith("service-account-") || firstName.length > 80 || lastName.length > 80 || !EMAIL.test(email) || email.length > 254 || !passwordIsValid(obj.password)) {
    throw new IdentityError("DATOS_INVALIDOS", 422)
  }
  const token = await adminToken()
  // Crear deshabilitado para impedir que una asignación parcial genere acceso.
  const creation = await adminFetch(token, "/users", "POST", {
    username, firstName, lastName, email, enabled: false, emailVerified: false,
    credentials: [{ type: "password", value: obj.password, temporary: true }],
    requiredActions: ["UPDATE_PASSWORD"],
  })
  const location = creation.headers.get("location") || ""
  const match = location.match(/\/([0-9a-f-]{36})$/i)
  if (!match || !USER_ID.test(match[1])) throw new IdentityError("USUARIO_CREADO_SIN_IDENTIFICADOR", 502)
  const id = match[1]
  const role = await adminJson<RealmRole>(token, `/roles/${USER_ROLE}`)
  await adminFetch(token, `/users/${id}/role-mappings/realm`, "POST", [role])
  await adminFetch(token, `/users/${id}`, "PUT", { enabled: true })
}

async function isCurrentLastAdmin(token: string, id: string): Promise<boolean> {
  const members = await adminJson<KcUser[]>(token, `/roles/${ADMIN_ROLE}/users?first=0&max=500`)
  const enabled = await Promise.all(members.map(async (member) => {
    const user = await userWithToken(token, member.id)
    return user.enabled === true ? user.id : null
  }))
  return enabled.filter(Boolean).length <= 1 && enabled.includes(id)
}

export async function updateManagedUser(id: string, action: unknown, value: unknown, actingUserId: string): Promise<void> {
  requireId(id)
  requireId(actingUserId)
  const token = await adminToken()
  const target = await userWithToken(token, id)
  if (target.username?.startsWith("service-account-")) throw new IdentityError("CUENTA_DE_SERVICIO_PROTEGIDA", 403)
  if (action === "set-enabled") {
    if (typeof value !== "boolean") throw new IdentityError("DATOS_INVALIDOS", 422)
    if (!value && id === actingUserId) throw new IdentityError("NO_PUEDE_DESHABILITARSE", 403)
    if (!value && (await rolesForUser(token, id)).some((role) => role.name === ADMIN_ROLE)) {
      throw new IdentityError("RETIRAR_ROL_ADMIN_ANTES", 409)
    }
    await adminFetch(token, `/users/${id}`, "PUT", { enabled: value })
    return
  }
  if (action === "set-admin") {
    if (typeof value !== "boolean") throw new IdentityError("DATOS_INVALIDOS", 422)
    if (!value && id === actingUserId) throw new IdentityError("NO_PUEDE_RETIRARSE_ADMIN", 403)
    if (value && target.enabled !== true) throw new IdentityError("USUARIO_DESHABILITADO", 409)
    const roles = await rolesForUser(token, id)
    const alreadyAdmin = roles.some((role) => role.name === ADMIN_ROLE)
    if (alreadyAdmin === value) return
    if (!value && await isCurrentLastAdmin(token, id)) throw new IdentityError("ULTIMO_ADMINISTRADOR", 409)
    const role = await adminJson<RealmRole>(token, `/roles/${ADMIN_ROLE}`)
    await adminFetch(token, `/users/${id}/role-mappings/realm`, value ? "POST" : "DELETE", [role])
    return
  }
  if (action === "reset-password") {
    if (id === actingUserId) throw new IdentityError("CAMBIO_PERSONAL_EN_KEYCLOAK", 403)
    if (!passwordIsValid(value)) throw new IdentityError("DATOS_INVALIDOS", 422)
    await adminFetch(token, `/users/${id}/reset-password`, "PUT", { type: "password", value, temporary: true })
    return
  }
  throw new IdentityError("ACCION_NO_ADMITIDA", 422)
}
