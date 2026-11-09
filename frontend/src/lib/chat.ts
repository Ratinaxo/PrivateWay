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
