/** Puente del historial, exclusivo del servidor. Un usuario nunca elige el owner. */
import "server-only"
import type {Conversation} from "@/lib/chat"

const ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

export class HistoryError extends Error {
  constructor(public readonly status: number, public readonly code: string) {super(code)}
}

export async function historyGateway(method: "GET" | "PUT" | "DELETE", owner: string, id?: string, data?: Conversation): Promise<unknown> {
  if (!ID.test(owner) || (id && !ID.test(id))) throw new HistoryError(422, "IDENTIFICADOR_INVALIDO")
  const base = process.env.GATEWAY_INTERNAL_URL
  const token = process.env.GATEWAY_HISTORY_TOKEN
  if (!base || !token) throw new HistoryError(503, "HISTORIAL_NO_CONFIGURADO")
  let url: URL
  try {
    const root = new URL(base)
    if (!["http:", "https:"].includes(root.protocol) || root.username || root.password || root.search || root.hash) throw new Error()
    url = new URL(id ? `/api/v1/conversations/${id}` : "/api/v1/conversations", root)
    if (url.origin !== root.origin) throw new Error()
  } catch {throw new HistoryError(503, "HISTORIAL_NO_CONFIGURADO")}
  let response: Response
  try {
    response = await fetch(url, {
      method, cache: "no-store", redirect: "manual", signal: AbortSignal.timeout(15_000),
      headers: {Authorization: `Bearer ${token}`, "X-PrivateWay-User-Id": owner,
        ...(data ? {"Content-Type": "application/json"} : {})},
      ...(data ? {body: JSON.stringify(data)} : {}),
    })
  } catch {throw new HistoryError(503, "HISTORIAL_NO_DISPONIBLE")}
  if (!response.ok) throw new HistoryError(response.status, "HISTORIAL_NO_DISPONIBLE")
  try {return await response.json()}
  catch {throw new HistoryError(502, "HISTORIAL_RESPUESTA_INVALIDA")}
}
