/**
 * Puente de mensajes: navegador -> Next.js -> gateway FastAPI.
 * Exige sesión OIDC; el backend ejecuta su pipeline configurado.
 * NUNCA incorpora credenciales de proveedores en la respuesta al navegador.
 */
import { NextResponse } from "next/server"
import { currentSession } from "@/lib/auth/session"
import { isAuthConfigured } from "@/lib/auth/config"
import { GatewayBridgeError, sendProtectedChat } from "@/lib/gateway/server"
import type { GatewayChatRequest, GatewayMessage } from "@/lib/gateway/contracts"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

const MAX_BODY_BYTES = 256_000
const ALIAS = /^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$/
const OIDC_SUB = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const ROLES = new Set(["user", "assistant"])
const ERROR_HEADERS = { "Cache-Control": "no-store" }

function failure(code: string, status: number) {
  return NextResponse.json(
    { error: { type: "gateway_error", code } },
    { status, headers: ERROR_HEADERS },
  )
}

function isObject(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value)
}

function parseRequest(value: unknown): GatewayChatRequest | null {
  if (!isObject(value) || Object.keys(value).some((key) => !["model", "messages", "stream", "temperature", "max_tokens"].includes(key))) return null
  if (typeof value.model !== "string" || !ALIAS.test(value.model)) return null
  if (!Array.isArray(value.messages) || value.messages.length === 0 || value.messages.length > 30) return null
  if (!value.messages.every((m: unknown) => isObject(m) && Object.keys(m).every((k) => ["role", "content"].includes(k)) &&
    typeof m.role === "string" && ROLES.has(m.role) &&
    typeof m.content === "string" && m.content.trim().length > 0 && m.content.length <= 20_000)) return null
  const messages = value.messages as GatewayMessage[]
  if (messages.at(-1)?.role !== "user") return null
  if (value.stream !== undefined && value.stream !== false) return null
  if (value.temperature !== undefined && (typeof value.temperature !== "number" || !Number.isFinite(value.temperature) || value.temperature < 0 || value.temperature > 2)) return null
  if (value.max_tokens !== undefined && (typeof value.max_tokens !== "number" || !Number.isInteger(value.max_tokens) || value.max_tokens < 1 || value.max_tokens > 8192)) return null
  return {
    model: value.model,
    messages,
    stream: false,
    ...(value.temperature === undefined ? {} : { temperature: value.temperature as number }),
    ...(value.max_tokens === undefined ? {} : { max_tokens: value.max_tokens as number }),
  }
}

export async function POST(request: Request) {
  // Autenticación obligatoria en cualquier entorno, también durante desarrollo.
  // La sesión del BFF no sustituye las decisiones del pipeline en FastAPI.
  if (!isAuthConfigured()) return failure("AUTENTICACION_NO_CONFIGURADA", 503)
  const session = await currentSession()
  if (!session?.user?.id) return failure("NO_AUTENTICADO", 401)
  if (!OIDC_SUB.test(session.user.id)) return failure("IDENTIDAD_INVALIDA", 403)
  // Rechazar solicitudes cross-site típicas antes de procesar el cuerpo.
  const origin = request.headers.get("origin")
  if (request.headers.get("sec-fetch-site") === "cross-site") return failure("ORIGEN_NO_ADMITIDO", 403)
  if (origin) {
    try {
      const requestHost = request.headers.get("host")
      if (!requestHost || new URL(origin).host !== requestHost) return failure("ORIGEN_NO_ADMITIDO", 403)
    } catch {
      return failure("ORIGEN_NO_ADMITIDO", 403)
    }
  }
  if (request.headers.get("content-type")?.split(";", 1)[0]?.trim().toLowerCase() !== "application/json") {
    return failure("SOLICITUD_INVALIDA", 415)
  }
  const length = Number(request.headers.get("content-length") ?? 0)
  if (!Number.isSafeInteger(length) || length < 0 || length > MAX_BODY_BYTES) return failure("SOLICITUD_INVALIDA", 413)

  let body: GatewayChatRequest | null
  try {
    const text = await request.text()
    if (Buffer.byteLength(text, "utf8") > MAX_BODY_BYTES) return failure("SOLICITUD_INVALIDA", 413)
    body = parseRequest(JSON.parse(text))
  } catch {
    return failure("SOLICITUD_INVALIDA", 422)
  }
  if (!body) return failure("SOLICITUD_INVALIDA", 422)

  try {
    const result = await sendProtectedChat(body, {id: session.user.id, name: session.user.name || session.user.id})
    return NextResponse.json(result, { headers: ERROR_HEADERS })
  } catch (error) {
    const status = error instanceof GatewayBridgeError ? error.status : 502
    return failure(
      error instanceof GatewayBridgeError ? error.code : "FALLO_BRIDGE",
      status >= 400 && status <= 599 ? status : 502,
    )
  }
}
