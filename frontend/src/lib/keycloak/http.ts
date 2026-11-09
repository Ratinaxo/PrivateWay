import { NextResponse } from "next/server"
import { currentSession } from "@/lib/auth/session"
import { IdentityError } from "./admin"

const NO_STORE = { "Cache-Control": "no-store" }

export function adminError(code: string, status: number) {
  return NextResponse.json({ error: { code } }, { status, headers: NO_STORE })
}

export function adminFailure(error: unknown) {
  return adminError(error instanceof IdentityError ? error.code : "OPERACION_IDENTIDAD_FALLIDA",
    error instanceof IdentityError ? error.status : 502)
}

export async function authorizeAdmin() {
  const session = await currentSession()
  if (!session?.user?.id) return { error: adminError("NO_AUTENTICADO", 401) }
  if (!session.user.isAdmin) return { error: adminError("NO_AUTORIZADO", 403) }
  return { id: session.user.id }
}

/**
 * La protección CSRF NO depende de que el navegador incluya Sec-Fetch-Site.
 * Las mutaciones solo aceptan JSON desde el origen exacto de PrivateWay.
 */
export function validateAdminMutation(request: Request) {
  const origin = request.headers.get("origin")
  const configured = process.env.NEXTAUTH_URL
  if (!origin || !configured || origin !== new URL(configured).origin ||
      request.headers.get("sec-fetch-site") === "cross-site") return adminError("ORIGEN_NO_ADMITIDO", 403)
  if (request.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
    return adminError("TIPO_CONTENIDO_INVALIDO", 415)
  }
  return null
}

export async function readSmallJson(request: Request): Promise<unknown> {
  const size = Number(request.headers.get("content-length") || "0")
  if (!Number.isSafeInteger(size) || size < 0 || size > 8_192) throw new IdentityError("DATOS_INVALIDOS", 422)
  try {
    const text = await request.text()
    if (Buffer.byteLength(text, "utf8") > 8_192) throw new Error()
    return JSON.parse(text) as unknown
  } catch {
    throw new IdentityError("DATOS_INVALIDOS", 422)
  }
}

export const noStoreHeaders = NO_STORE
