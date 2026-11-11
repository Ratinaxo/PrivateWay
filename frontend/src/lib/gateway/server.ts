import type { GatewayCatalog, GatewayChatRequest, GatewayChatResponse } from "./contracts"

const INTERNAL_BASE = process.env.GATEWAY_INTERNAL_URL
const SERVICE_TOKEN = process.env.GATEWAY_CLIENT_TOKEN

export class GatewayBridgeError extends Error {
  constructor(public readonly code: string, public readonly status: number) {
    super(code)
  }
}

async function requestGateway(path: "/api/v1/models" | "/api/v1/secure-chat", body?: GatewayChatRequest, actor?: {id: string; name: string}): Promise<unknown> {
  if (!INTERNAL_BASE || !SERVICE_TOKEN) {
    throw new GatewayBridgeError("GATEWAY_NO_CONFIGURADO", 503)
  }
  let url: URL
  try {
    const base = new URL(INTERNAL_BASE)
    if (!["http:", "https:"].includes(base.protocol) || base.username || base.password || base.search || base.hash) {
      throw new Error("Configuración inválida")
    }
    url = new URL(path, base)
    if (url.origin !== base.origin) throw new Error("Origen inesperado")
  } catch {
    throw new GatewayBridgeError("GATEWAY_URL_INVALIDA", 503)
  }

  let response: Response
  try {
    response = await fetch(url, {
      method: body ? "POST" : "GET",
      headers: {
        Authorization: `Bearer ${SERVICE_TOKEN}`,
        ...(body ? { "Content-Type": "application/json" } : {}),
        ...(actor ? {"X-PrivateWay-User-Id": actor.id, "X-PrivateWay-User-Name": encodeURIComponent(actor.name.slice(0, 100))} : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
      cache: "no-store",
      redirect: "manual",
      signal: AbortSignal.timeout(60_000),
    })
  } catch {
    throw new GatewayBridgeError("GATEWAY_INACCESIBLE", 502)
  }
  if (!response.ok) {
    // Conservar únicamente un código de error sintético del gateway.
    // Nunca devolver detalles HTTP, credenciales o el prompt en el BFF.
    let code = "GATEWAY_RESPONDIO_ERROR"
    if (response.headers.get("content-type")?.includes("application/json")) {
      try {
        const data: unknown = await response.json()
        if (data && typeof data === "object" && "error" in data) {
          const error = data.error
          if (error && typeof error === "object" && "code" in error &&
              typeof error.code === "string" && /^[A-Z_]{2,64}$/.test(error.code)) {
            code = error.code
          }
        }
      } catch { /* Nunca mostrar errores crudos */ }
    }
    throw new GatewayBridgeError(code, response.status >= 400 && response.status <= 599 ? response.status : 502)
  }
  if (!response.headers.get("content-type")?.includes("application/json")) {
    throw new GatewayBridgeError("GATEWAY_RESPUESTA_INVALIDA", 502)
  }
  try {
    return await response.json()
  } catch {
    throw new GatewayBridgeError("GATEWAY_RESPUESTA_INVALIDA", 502)
  }
}

export async function getGatewayCatalog(): Promise<GatewayCatalog> {
  const data = await requestGateway("/api/v1/models")
  if (
    !data || typeof data !== "object" ||
    !("providers" in data) || !Array.isArray(data.providers) ||
    !data.providers.every((provider: unknown) => {
      if (!provider || typeof provider !== "object") return false
      if (!("id" in provider) || typeof provider.id !== "string") return false
      if (!("label" in provider) || typeof provider.label !== "string") return false
      if (!("models" in provider) || !Array.isArray(provider.models)) return false
      return provider.models.every((m: unknown) =>
        !!m && typeof m === "object" &&
        "id" in m && typeof m.id === "string" &&
        "label" in m && typeof m.label === "string")
    })
  ) {
    throw new GatewayBridgeError("GATEWAY_RESPUESTA_INVALIDA", 502)
  }
  return data as GatewayCatalog
}

export async function sendProtectedChat(body: GatewayChatRequest, actor?: {id: string; name: string}): Promise<GatewayChatResponse> {
  const data = await requestGateway("/api/v1/secure-chat", body, actor)
  if (!data || typeof data !== "object" || !("respuesta" in data) || !("decision" in data)) {
    throw new GatewayBridgeError("GATEWAY_RESPUESTA_INVALIDA", 502)
  }
  const respuesta = data.respuesta
  const decision = data.decision
  if (!respuesta || typeof respuesta !== "object" ||
      !("choices" in respuesta) || !Array.isArray(respuesta.choices) || respuesta.choices.length === 0 ||
      !respuesta.choices[0] || typeof respuesta.choices[0] !== "object" ||
      !("message" in respuesta.choices[0]) || !respuesta.choices[0].message ||
      typeof respuesta.choices[0].message !== "object" ||
      !("content" in respuesta.choices[0].message) || typeof respuesta.choices[0].message.content !== "string" ||
      respuesta.choices[0].message.content.length > 100_000 ||
      !decision || typeof decision !== "object" ||
      !("accion" in decision) || !["permitir", "seudonimizar"].includes(String(decision.accion)) ||
      !("codigo_motivo" in decision) || typeof decision.codigo_motivo !== "string" ||
      !/^[A-Z0-9_]{2,64}$/.test(decision.codigo_motivo) ||
      !("evento" in decision) || typeof decision.evento !== "string" ||
      !/^evt_[a-f0-9]{32}$/.test(decision.evento) ||
      !("mensaje_actual_seudonimizado" in decision) || typeof decision.mensaje_actual_seudonimizado !== "boolean" ||
      !("historial_seudonimizado" in decision) || typeof decision.historial_seudonimizado !== "boolean") {
    throw new GatewayBridgeError("GATEWAY_RESPUESTA_INVALIDA", 502)
  }
  return data as GatewayChatResponse
}
