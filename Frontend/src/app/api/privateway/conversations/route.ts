import {NextResponse} from "next/server"
import {currentSession} from "@/lib/auth/session"
import {historyGateway, HistoryError} from "@/lib/gateway/conversations"
export const runtime = "nodejs"
export const dynamic = "force-dynamic"
export async function GET() {
  const session = await currentSession()
  if (!session?.user?.id) return NextResponse.json({error: "NO_AUTENTICADO"}, {status: 401, headers: {"Cache-Control":"no-store"}})
  try {
    const result = await historyGateway("GET", session.user.id)
    return NextResponse.json(result, {headers: {"Cache-Control":"no-store"}})
  } catch (e) {
    return NextResponse.json({error:"HISTORIAL_NO_DISPONIBLE"}, {status:e instanceof HistoryError ? e.status : 503,headers:{"Cache-Control":"no-store"}})
  }
}
