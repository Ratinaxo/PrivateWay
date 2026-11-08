export type Provider = {
  id: string
  label: string
  models: { id: string; label: string }[]
}

export type ChatMessage = {
  id: string
  role: "user" | "assistant" | "notice"
  content: string
  createdAt: number
  noticeType?: "info" | "protected" | "blocked" | "error"
}

export type Conversation = {
  id: string
  title: string
  providerId: string
  modelId: string
  createdAt: number
  updatedAt: number
  messages: ChatMessage[]
}

// Catálogo ficticio: en la integración real provendrá del backend autorizado.
export const DEMO_PROVIDERS: Provider[] = [
  { id: "a", label: "Proveedor A", models: [
    { id: "a-general", label: "Modelo general" },
    { id: "a-rapido", label: "Modelo rápido" },
  ] },
  { id: "b", label: "Proveedor B", models: [
    { id: "b-general", label: "Modelo general" },
    { id: "b-analisis", label: "Modelo de análisis" },
  ] },
  { id: "c", label: "Proveedor C", models: [
    { id: "c-general", label: "Modelo general" },
  ] },
]

const day = 86_400_000
const reference = Date.UTC(2026, 10, 8, 12)

export const DEMO_CONVERSATIONS: Conversation[] = [
  {
    id: "demo-1", title: "Documentación de una API", providerId: "a", modelId: "a-general",
    createdAt: reference - day * 2, updatedAt: reference,
    messages: [
      { id: "demo-1-1", role: "user", content: "¿Cómo organizarías la documentación de una API REST?", createdAt: reference - 150_000 },
      { id: "demo-1-2", role: "assistant", content: "**Ejemplo de respuesta (datos ficticios)**\n\nUna documentación sencilla puede organizarse así:\n\n1. **Autenticación:** cómo obtener credenciales y gestionar errores.\n2. **Endpoints:** recursos, parámetros y respuestas.\n3. **Ejemplos:** solicitudes y respuestas representativas.\n\n```http\nGET /api/v1/models\nAuthorization: Bearer <token>\n```\n\nEsta respuesta es solo una muestra visual; no proviene de un modelo externo.", createdAt: reference - 140_000 },
    ],
  },
  {
    id: "demo-2", title: "Ideas para una presentación", providerId: "b", modelId: "b-general",
    createdAt: reference - day * 3, updatedAt: reference - day,
    messages: [
      { id: "demo-2-1", role: "user", content: "Dame una estructura simple para una presentación de proyecto.", createdAt: reference - day },
      { id: "demo-2-2", role: "assistant", content: "**Ejemplo de respuesta (datos ficticios)**\n\nComenzaría con el problema, seguiría con la solución propuesta, incluiría una demostración y terminaría con los próximos pasos.", createdAt: reference - day + 1_000 },
    ],
  },
  {
    id: "demo-3", title: "Resumen de un artículo", providerId: "c", modelId: "c-general",
    createdAt: reference - day * 5, updatedAt: reference - day * 3,
    messages: [
      { id: "demo-3-1", role: "user", content: "¿Qué elementos debería incluir un resumen académico?", createdAt: reference - day * 3 },
      { id: "demo-3-2", role: "assistant", content: "**Ejemplo de respuesta (datos ficticios)**\n\nIncluye el objetivo, la metodología, los resultados principales y la conclusión. Evita incorporar afirmaciones que no aparezcan en el texto original.", createdAt: reference - day * 3 + 1_000 },
    ],
  },
]

export function providerName(id: string) {
  return DEMO_PROVIDERS.find((provider) => provider.id === id)?.label ?? "Proveedor no disponible"
}

export function modelName(providerId: string, modelId: string) {
  return DEMO_PROVIDERS.find((provider) => provider.id === providerId)?.models.find((model) => model.id === modelId)?.label ?? "Modelo no disponible"
}