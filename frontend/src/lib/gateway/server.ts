import type { GatewayCatalog, GatewayChatRequest, GatewayChatResponse } from "./contracts"

const INTERNAL_BASE = process.env.GATEWAY_INTERNAL_URL
const SERVICE_TOKEN = process.env.GATEWAY_CLIENT_TOKEN

export class GatewayBridgeError extends Error {
  constructor(public readonly code: string, public readonly status: number) {
    super(code)
  }
}

async function requestGateway(path: "/api/v1/models" | "/api/v1/secure-chat", body?: GatewayChatRequest): Promise<unknown> {
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
    throw new GatewayBridgeError("GATEWAY_RESPONDIO_ERROR", response.status)
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

export async function sendProtectedChat(body: GatewayChatRequest): Promise<GatewayChatResponse> {
  return (await requestGateway("/api/v1/secure-chat", body)) as GatewayChatResponse
}
