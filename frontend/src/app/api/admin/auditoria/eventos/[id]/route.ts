import { NextResponse } from "next/server"
import { currentSession } from "@/lib/auth/session"
import { getAuditPreview } from "@/lib/gateway/audit"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"
const NO_STORE = {"Cache-Control": "no-store, private", "Pragma": "no-cache"}

export async function GET(request: Request, {params}: {params: Promise<{id: string}>}) {
  const session = await currentSession()
  if (!session?.user?.id) return NextResponse.json({error: "NO_AUTENTICADO"}, {status: 401, headers: NO_STORE})
  if (!session.user.isAdmin) return NextResponse.json({error: "NO_AUTORIZADO"}, {status: 403, headers: NO_STORE})
  const {id} = await params
  if (!/^evt_[a-f0-9]{32}$/.test(id)) return NextResponse.json({error: "EVENTO_INVALIDO"}, {status: 422, headers: NO_STORE})
  if (request.headers.get("sec-fetch-site") === "cross-site") return NextResponse.json({error: "ORIGEN_NO_ADMITIDO"}, {status: 403, headers: NO_STORE})
  try {
    const preview = await getAuditPreview(id, session.user.id, session.user.name || session.user.id)
    if (!preview) return NextResponse.json({error: "SIN_PREVISUALIZACION"}, {status: 404, headers: NO_STORE})
    return NextResponse.json(preview, {headers: NO_STORE})
  } catch {
    return NextResponse.json({error: "AUDITORIA_NO_DISPONIBLE"}, {status: 503, headers: NO_STORE})
  }
}
