import {NextResponse} from "next/server"
import {currentSession} from "@/lib/auth/session"
import {historyGateway, HistoryError} from "@/lib/gateway/conversations"
import type {Conversation} from "@/lib/chat"
export const runtime = "nodejs"
export const dynamic = "force-dynamic"
const HEADERS = {"Cache-Control":"no-store"}
const ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

function safeOrigin(request: Request) {
  if (request.headers.get("sec-fetch-site") === "cross-site") return false
  const origin = request.headers.get("origin")
  if (!origin) return true
  try {return new URL(origin).host === request.headers.get("host")}
  catch {return false}
}

async function mutate(method: "PUT" | "DELETE", request: Request, params: Promise<{id:string}>) {
  const session = await currentSession()
  if (!session?.user?.id) return NextResponse.json({error:"NO_AUTENTICADO"},{status:401,headers:HEADERS})
  if (!safeOrigin(request)) return NextResponse.json({error:"ORIGEN_NO_ADMITIDO"},{status:403,headers:HEADERS})
  const {id} = await params
  if (!ID.test(id)) return NextResponse.json({error:"IDENTIFICADOR_INVALIDO"},{status:422,headers:HEADERS})
  let data: Conversation | undefined
  if (method === "PUT") {
    try {
      const raw = await request.text()
      if (Buffer.byteLength(raw,"utf8") > 5_000_000) throw new Error()
      data = JSON.parse(raw) as Conversation
      if (!data || typeof data !== "object" || data.id !== id || !Array.isArray(data.messages)) throw new Error()
    } catch {return NextResponse.json({error:"SOLICITUD_INVALIDA"},{status:422,headers:HEADERS})}
  }
  try {return NextResponse.json(await historyGateway(method, session.user.id, id, data),{headers:HEADERS})}
  catch (e) {return NextResponse.json({error:"HISTORIAL_NO_DISPONIBLE"},{status:e instanceof HistoryError ? e.status : 503,headers:HEADERS})}
}
export async function PUT(request: Request,{params}:{params:Promise<{id:string}>}) {return mutate("PUT",request,params)}
export async function DELETE(request: Request,{params}:{params:Promise<{id:string}>}) {return mutate("DELETE",request,params)}
