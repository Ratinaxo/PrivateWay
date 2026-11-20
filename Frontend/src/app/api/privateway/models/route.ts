import { NextResponse } from "next/server"
import { currentSession } from "@/lib/auth/session"
import { isAuthConfigured } from "@/lib/auth/config"
import {
  GatewayBridgeError,
  getGatewayCatalog,
} from "@/lib/gateway/server"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

export async function GET() {
  // El catálogo interno requiere sesión OIDC, incluso en desarrollo.
  if (!isAuthConfigured()) return NextResponse.json(
    { error: { code: "AUTENTICACION_NO_CONFIGURADA" } },
    { status: 503, headers: { "Cache-Control": "no-store" } },
  )
  const session = await currentSession()
  if (!session?.user?.id) return NextResponse.json(
    { error: { code: "NO_AUTENTICADO" } },
    { status: 401, headers: { "Cache-Control": "no-store" } },
  )

  try {
    const catalog = await getGatewayCatalog()
    return NextResponse.json(catalog, { headers: { "Cache-Control": "no-store" } })
  } catch (error) {
    const status = error instanceof GatewayBridgeError ? error.status : 502
    return NextResponse.json(
      { error: { code: error instanceof GatewayBridgeError ? error.code : "FALLO_BRIDGE" } },
      { status: status >= 400 && status <= 599 ? status : 502,
        headers: { "Cache-Control": "no-store" } }
    )
  }
}
