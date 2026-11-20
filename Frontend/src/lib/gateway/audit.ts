/** Solo servidor. La clave de auditoría nunca se envía al navegador. */
import "server-only"

export interface AuditRecord {
  fecha_utc?: string
  evento?: string
  fase?: string
  alias?: string
  proveedor?: string
  accion?: string
  motivo?: string
  transmision?: string
  mensaje_actual?: string
  historial?: string
  usuario?: string
  usuario_id?: string
  vista_disponible?: string
  evento_consultado?: string
}

export interface AuditSnapshot {
  integridad: "verificada"
  total: number
  registros: AuditRecord[]
}

const CAMPOS = ["fecha_utc", "evento", "fase", "alias", "proveedor", "accion", "motivo", "transmision", "mensaje_actual", "historial", "usuario", "usuario_id", "vista_disponible", "evento_consultado"] as const

export async function getAuditSnapshot(): Promise<AuditSnapshot> {
  const baseUrl = process.env.GATEWAY_INTERNAL_URL
  const token = process.env.GATEWAY_AUDIT_READ_TOKEN
  if (!baseUrl || !token) throw new Error("AUDITORIA_NO_CONFIGURADA")
  let url: URL
  try {
    const base = new URL(baseUrl)
    if (!["http:", "https:"].includes(base.protocol) || base.username || base.password || base.search || base.hash) throw new Error()
    url = new URL("/api/v1/audit/events?limit=200", base)
    if (url.origin !== base.origin) throw new Error()
  } catch {
    throw new Error("AUDITORIA_NO_CONFIGURADA")
  }
  let response: Response
  try {
    response = await fetch(url, {
      headers: {Authorization: `Bearer ${token}`},
      method: "GET", cache: "no-store", redirect: "manual", signal: AbortSignal.timeout(10_000),
    })
  } catch {
    throw new Error("AUDITORIA_NO_DISPONIBLE")
  }
  if (!response.ok || !response.headers.get("content-type")?.includes("application/json")) {
    throw new Error("AUDITORIA_NO_DISPONIBLE")
  }
  try {
    const body: unknown = await response.json()
    if (!body || typeof body !== "object" ||
        !("integridad" in body) || body.integridad !== "verificada" ||
        !("total" in body) || typeof body.total !== "number" || !Number.isSafeInteger(body.total) || body.total < 0 ||
        !("registros" in body) || !Array.isArray(body.registros) || body.registros.length > 200 ||
        !body.registros.every((registro: unknown) =>
          registro && typeof registro === "object" && !Array.isArray(registro) &&
          Object.keys(registro).every((key) => CAMPOS.includes(key as typeof CAMPOS[number]) &&
            typeof (registro as Record<string, unknown>)[key] === "string" &&
            ((registro as Record<string, string>)[key].length <= 120)))) {
      throw new Error()
    }
    return body as AuditSnapshot
  } catch {
    throw new Error("AUDITORIA_NO_DISPONIBLE")
  }
}


export interface AuditPreview {
  evento: string
  usuario: string
  mensajes: {indice: number; role: string; antes: string; despues: string | null}[]
  respuesta: {antes: string; despues: string} | null
}

export async function getAuditPreview(evento: string, auditorId: string, auditorName: string): Promise<AuditPreview | null> {
  if (!/^evt_[a-f0-9]{32}$/.test(evento)) throw new Error("EVENTO_INVALIDO")
  const base = process.env.GATEWAY_INTERNAL_URL
  const token = process.env.GATEWAY_AUDIT_READ_TOKEN
  if (!base || !token) throw new Error("AUDITORIA_NO_CONFIGURADA")
  const root = new URL(base)
  if (!["http:", "https:"].includes(root.protocol) || root.username || root.password || root.search || root.hash) throw new Error("AUDITORIA_NO_CONFIGURADA")
  const url = new URL(`/api/v1/audit/events/${evento}/preview`, root)
  if (url.origin !== root.origin) throw new Error("AUDITORIA_NO_CONFIGURADA")
  const response = await fetch(url, {
    method: "GET", cache: "no-store", redirect: "manual", signal: AbortSignal.timeout(10_000),
    headers: {Authorization: `Bearer ${token}`, "X-PrivateWay-Auditor-Id": auditorId,
      "X-PrivateWay-Auditor-Name": encodeURIComponent(auditorName.slice(0, 100))},
  })
  if (response.status === 404) return null
  if (!response.ok || !response.headers.get("content-type")?.includes("application/json")) throw new Error("AUDITORIA_NO_DISPONIBLE")
  const value: unknown = await response.json()
  if (!value || typeof value !== "object" || Array.isArray(value) ||
      !("evento" in value) || value.evento !== evento ||
      !("usuario" in value) || typeof value.usuario !== "string" || value.usuario.length > 120 ||
      !("mensajes" in value) || !Array.isArray(value.mensajes) || value.mensajes.length > 30 ||
      !value.mensajes.every((m: unknown) => m && typeof m === "object" &&
        "indice" in m && typeof m.indice === "number" &&
        "role" in m && typeof m.role === "string" &&
        "antes" in m && typeof m.antes === "string" && m.antes.length <= 20_000 &&
        "despues" in m && (m.despues === null || (typeof m.despues === "string" && m.despues.length <= 20_000))) ||
      !("respuesta" in value) || (value.respuesta !== null &&
        (typeof value.respuesta !== "object" || !value.respuesta ||
         !("antes" in value.respuesta) || typeof value.respuesta.antes !== "string" ||
         !("despues" in value.respuesta) || typeof value.respuesta.despues !== "string"))) {
    throw new Error("AUDITORIA_RESPUESTA_INVALIDA")
  }
  return value as AuditPreview
}
