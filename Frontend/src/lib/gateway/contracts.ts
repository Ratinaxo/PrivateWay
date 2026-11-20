export type Role = "system" | "developer" | "user" | "assistant"

export interface GatewayMessage {
  role: Role
  content: string
}

export interface GatewayChatRequest {
  model: string // Alias autorizado, NO id ni URL proporcionados por el proveedor.
  messages: GatewayMessage[]
  stream?: false
  temperature?: number
  max_tokens?: number
}

export interface GatewayCatalog {
  providers: {
    id: string
    label: string
    models: { id: string; label: string }[]
  }[]
}

export interface GatewayChatResponse {
  respuesta: {
    id: string
    object: "chat.completion"
    created: number
    model: string
    choices: {
      index: number
      message: { role: "assistant"; content: string }
      finish_reason: string
    }[]
  }
  decision: {
    accion: "permitir" | "seudonimizar" | "bloquear"
    codigo_motivo: string
    evento: string
    mensaje_actual_seudonimizado: boolean
    historial_seudonimizado: boolean
  }
}

export interface GatewayError {
  error: { type: "gateway_error"; code: string; message: string }
}