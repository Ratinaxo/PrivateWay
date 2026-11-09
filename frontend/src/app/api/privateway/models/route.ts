import { NextResponse } from "next/server"
import {
  GatewayBridgeError,
  getGatewayCatalog,
} from "@/lib/gateway/server"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

export async function GET() {
  // No exponer el catálogo por esta ruta sin OIDC en entornos productivos.
  if (process.env.NODE_ENV !== "development" || process.env.PRIVATEWAY_DEV_CATALOG !== "1") {
    return NextResponse.json(
      { error: { code: "AUTENTICACION_PENDIENTE" } },
      { status: 503, headers: { "Cache-Control": "no-store" } }
    )
  }

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
