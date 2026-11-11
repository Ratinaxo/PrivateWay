"use client"

import * as React from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import {
  ArrowUp, Check, ChevronDown, ChevronsUpDown, Copy,
  LockKeyhole, MessageSquareText, MoreHorizontal, PanelLeftClose,
  PanelLeftOpen, Pencil, Plus, Search, ShieldCheck, ShieldOff, Trash2, X,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { ProfileMenu, UserAvatar } from "@/components/profile-menu"
import { shouldNotifyCurrentMessage } from "@/lib/privacy-notice"
import {
  type ChatMessage, type Conversation, type Provider,
} from "@/lib/chat"

const MAX_PROMPT_LENGTH = 12_000
const MAX_CONTEXT_MESSAGES = 29 // El mensaje nuevo ocupa la posición 30 del contrato FastAPI.
const MAX_STORED_MESSAGES = 500

const ERROR_TEXT: Record<string, string> = {
  AUTENTICACION_NO_CONFIGURADA: "El inicio de sesión no está configurado.",
  NO_AUTENTICADO: "Tu sesión ha expirado. Inicia sesión para continuar.",
  CHAT_CERRADO_SIN_AUTENTICACION: "Envío deshabilitado: se requiere iniciar sesión.",
  ANALISIS_NO_DISPONIBLE: "El análisis REGEX no está disponible. La solicitud fue detenida.",
  POLITICA_BLOQUEA: "La política de seguridad bloqueó la transmisión del mensaje.",
  FALLO_VALIDACION: "No se pudo validar de forma segura el análisis. La solicitud se ha bloqueado.",
  AUDITORIA_NO_DISPONIBLE: "La auditoría no está disponible; no se autoriza la operación.",
  MODELO_NO_AUTORIZADO: "El modelo seleccionado no está autorizado por el gateway.",
  PROVEEDOR_NO_DISPONIBLE: "No se pudo completar la operación con el proveedor externo.",
  FALLO_POSPROCESAMIENTO: "La respuesta externa no superó el posprocesamiento seguro.",
}

function makeId() {
  return crypto.randomUUID()
}

function dateGroup(timestamp: number, todayStart: number | null) {
  if (todayStart === null) return "Anteriores"

  if (timestamp >= todayStart) return "Hoy"

  if (timestamp >= todayStart - 7 * 86_400_000) {
    return "Últimos 7 días"
  }

  return "Anteriores"
}


function getTodayStart(): number {
  const now = new Date()

  return new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate()
  ).getTime()
}

function subscribeToDate(callback: () => void) {
  const interval = window.setInterval(callback, 60_000)

  return () => window.clearInterval(interval)
}

function useTodayStart(): number | null {
  return React.useSyncExternalStore(
    subscribeToDate,
    getTodayStart,
    () => null
  )
}

function ConversationMenu({ onRename, onDelete }: { onRename: () => void; onDelete: () => void }) {
  const [open, setOpen] = React.useState(false)
  const ref = React.useRef<HTMLDivElement>(null)

  React.useEffect(() => {
    if (!open) return
    const close = (event: MouseEvent) => {
      if (!ref.current?.contains(event.target as Node)) setOpen(false)
    }
    const closeEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false)
    }
    document.addEventListener("pointerdown", close)
    document.addEventListener("keydown", closeEscape)
    return () => {
      document.removeEventListener("pointerdown", close)
      document.removeEventListener("keydown", closeEscape)
    }
  }, [open])

  return (
    <div ref={ref} className="relative shrink-0" onClick={(event) => event.stopPropagation()}>
      <button aria-label="Opciones de conversación" aria-expanded={open} onClick={() => setOpen((value) => !value)} className="flex size-7 items-center justify-center rounded-md text-stone-500 hover:bg-stone-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-stone-600">
        <MoreHorizontal className="size-4" />
      </button>
      {open && (
        <div className="absolute right-0 top-8 z-30 w-40 rounded-xl border border-stone-200 bg-white p-1.5 shadow-xl">
          <button className="flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-xs hover:bg-stone-100" onClick={() => { setOpen(false); onRename() }}><Pencil className="size-3.5" /> Renombrar</button>
          <button className="flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-xs text-red-700 hover:bg-red-50" onClick={() => { setOpen(false); onDelete() }}><Trash2 className="size-3.5" /> Eliminar</button>
        </div>
      )}
    </div>
  )
}

function Notice({ message }: { message: ChatMessage }) {
  const blocked = message.noticeType === "blocked"
  const error = message.noticeType === "error"
  const protectedMessage = message.noticeType === "protected"
  const Icon = blocked || error ? ShieldOff : ShieldCheck
  return (
    <div role={blocked || error ? "alert" : "status"} className={`mx-auto my-4 flex max-w-2xl gap-3 rounded-xl border px-4 py-3 text-sm ${blocked || error ? "border-red-200 bg-red-50 text-red-900" : protectedMessage ? "border-emerald-200 bg-emerald-50 text-emerald-900" : "border-stone-200 bg-stone-50 text-stone-600"}`}>
      <Icon className="mt-0.5 size-4 shrink-0" />
      <div className="whitespace-pre-wrap leading-relaxed">{message.content}</div>
    </div>
  )
}

function Message({ message }: { message: ChatMessage }) {
  const [copied, setCopied] = React.useState(false)
  if (message.role === "notice") return <Notice message={message} />
  if (message.role === "user") {
    return (
      <div className="flex justify-end py-3">
        <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-tr-sm bg-stone-100 px-4 py-3 text-[14px] leading-7 text-stone-800 sm:max-w-[75%]">{message.content}</div>
      </div>
    )
  }
  return (
    <div className="group py-4">
      <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-stone-800"><span className="flex size-7 items-center justify-center rounded-lg bg-emerald-900 text-white"><ShieldCheck className="size-4" /></span> PrivateWay <span className="font-normal text-stone-400">· gateway</span></div>
      <div className="pw-markdown text-[14px] leading-7 text-stone-800"><ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml>{message.content}</ReactMarkdown></div>
      <button className="mt-2 inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-stone-400 hover:bg-stone-100 hover:text-stone-700 focus-visible:outline-2" aria-label="Copiar respuesta" onClick={async () => {
        try { await navigator.clipboard.writeText(message.content); setCopied(true) } catch { setCopied(false) }
      }}>{copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}{copied ? "Copiado" : "Copiar"}</button>
    </div>
  )
}

export function ChatWorkspace({ user }: { user: { name: string; email: string | null; isAdmin: boolean } }) {
  const [chats, setChats] = React.useState<Conversation[]>([])
  const [historyLoaded, setHistoryLoaded] = React.useState(false)
  const [historyError, setHistoryError] = React.useState<string | null>(null)
  const persistedRef = React.useRef<Map<string, string>>(new Map())
  const persistQueueRef = React.useRef<Map<string, Promise<void>>>(new Map())
  const [providers, setProviders] = React.useState<Provider[]>([])
  const [catalogError, setCatalogError] = React.useState<string | null>(null)
  const [catalogLoading, setCatalogLoading] = React.useState(true)
  const [sending, setSending] = React.useState(false)
  const sendingRef = React.useRef(false)
  const todayStart = useTodayStart()
  const [activeId, setActiveId] = React.useState<string | null>(null)
  const [providerId, setProviderId] = React.useState("")
  const [modelId, setModelId] = React.useState("")
  const [draft, setDraft] = React.useState("")
  const [search, setSearch] = React.useState("")
  const [sidebarOpen, setSidebarOpen] = React.useState(true)
  const [mobileOpen, setMobileOpen] = React.useState(false)
  const [renameId, setRenameId] = React.useState<string | null>(null)
  const [renameDraft, setRenameDraft] = React.useState("")
  const [deleteId, setDeleteId] = React.useState<string | null>(null)
  const scrollRef = React.useRef<HTMLDivElement>(null)
  const textareaRef = React.useRef<HTMLTextAreaElement>(null)
  const activeChat = chats.find((chat) => chat.id === activeId) ?? null
  const selectedProvider = providers.find((provider) => provider.id === providerId)
  const providerLabel = (id: string) => providers.find((provider) => provider.id === id)?.label ?? "Proveedor no disponible"
  const modelLabel = (provider: string, model: string) => providers.find((p) => p.id === provider)?.models.find((m) => m.id === model)?.label ?? "Modelo no disponible"
  const currentProvider = activeChat?.providerId ?? providerId
  const currentModel = activeChat?.modelId ?? modelId
  const visibleChats = [...chats].filter((chat) => chat.title.toLocaleLowerCase("es").includes(search.toLocaleLowerCase("es"))).sort((a, b) => b.updatedAt - a.updatedAt)
  const grouped = ["Hoy", "Últimos 7 días", "Anteriores"]
    .map((name) => ({
      name,
      items: visibleChats.filter(
        (chat) => dateGroup(chat.updatedAt, todayStart) === name
      ),
    }))
    .filter((group) => group.items.length)

  React.useEffect(() => {
    const controller = new AbortController()
    void fetch("/api/privateway/conversations", {cache: "no-store", signal: controller.signal})
      .then(async (response) => {
        if (!response.ok) throw new Error("HISTORIAL_NO_DISPONIBLE")
        const data: unknown = await response.json()
        if (!data || typeof data !== "object" || !("conversations" in data) || !Array.isArray(data.conversations)) throw new Error("HISTORIAL_INVALIDO")
        const loaded = data.conversations as Conversation[]
        if (loaded.some((chat) => !chat || typeof chat.id !== "string" || typeof chat.title !== "string" || !Array.isArray(chat.messages))) throw new Error("HISTORIAL_INVALIDO")
        if (controller.signal.aborted) return
        persistedRef.current = new Map(loaded.map((chat) => [chat.id, JSON.stringify(chat)]))
        setChats(loaded)
        setActiveId(loaded[0]?.id ?? null)
        setHistoryError(null)
        setHistoryLoaded(true)
      })
      .catch(() => {if (!controller.signal.aborted) setHistoryError("No se pudo recuperar el historial de PostgreSQL. Comprueba el estado del servicio antes de enviar mensajes.")})
    return () => controller.abort()
  }, [])

  React.useEffect(() => {
    if (!historyLoaded) return
    const actual = new Map(chats.map((chat) => [chat.id, JSON.stringify(chat)]))
    const encolar = (id: string, metodo: "PUT" | "DELETE", payload?: string) => {
      const anterior = persistQueueRef.current.get(id) ?? Promise.resolve()
      const siguiente = anterior.catch(() => {}).then(async () => {
        const response = await fetch(`/api/privateway/conversations/${encodeURIComponent(id)}`, {
          method: metodo,
          headers: payload ? {"Content-Type": "application/json"} : {},
          body: payload,
          cache: "no-store",
        })
        if (!response.ok) throw new Error("No se pudo guardar el historial")
      })
      persistQueueRef.current.set(id, siguiente)
      void siguiente.catch(() => setHistoryError("No se pudieron guardar los cambios de conversación. Recarga solo cuando se haya resuelto la conexión."))
    }
    for (const [id, data] of actual) {
      if (persistedRef.current.get(id) !== data) {
        persistedRef.current.set(id, data)
        encolar(id, "PUT", data)
      }
    }
    for (const id of persistedRef.current.keys()) {
      if (!actual.has(id)) {
        persistedRef.current.delete(id)
        encolar(id, "DELETE")
      }
    }
  }, [chats, historyLoaded])

  React.useEffect(() => {
    const controller = new AbortController()
    void fetch("/api/privateway/models", { cache: "no-store", signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error("CATALOGO_NO_DISPONIBLE")
        const data: unknown = await response.json()
        if (!data || typeof data !== "object" || !("providers" in data) || !Array.isArray(data.providers)) {
          throw new Error("CATALOGO_INVALIDO")
        }
        const items = data.providers as Provider[]
        if (items.length === 0 || !items.every((p) => typeof p.id === "string" && typeof p.label === "string" &&
          Array.isArray(p.models) && p.models.length > 0 && p.models.every((m) => typeof m.id === "string" && typeof m.label === "string"))) {
          throw new Error("CATALOGO_INVALIDO")
        }
        if (controller.signal.aborted) return
        setProviders(items)
        setProviderId(items[0].id)
        setModelId(items[0].models[0].id)
        setCatalogError(null)
      })
      .catch(() => { if (!controller.signal.aborted) setCatalogError("No se pudo cargar el catálogo autorizado de modelos.") })
      .finally(() => { if (!controller.signal.aborted) setCatalogLoading(false) })
    return () => controller.abort()
  }, [])

  React.useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" })
  }, [activeId, activeChat?.messages.length])

  React.useEffect(() => {
    const onKeydown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault()
        setActiveId(null)
        setDraft("")
        setMobileOpen(false)
        textareaRef.current?.focus()
      }
    }
    document.addEventListener("keydown", onKeydown)
    return () => document.removeEventListener("keydown", onKeydown)
  }, [])

  const newChat = () => {
    if (!historyLoaded || historyError) return
    setActiveId(null)
    setDraft("")
    setMobileOpen(false)
    textareaRef.current?.focus()
  }

  const selectChat = (id: string) => {
    setActiveId(id)
    setDraft("")
    setMobileOpen(false)
  }

  const send = async (event?: React.FormEvent) => {
    event?.preventDefault()
    const content = draft.trim()
    if (sendingRef.current || !historyLoaded || historyError || !content || content.length > MAX_PROMPT_LENGTH || !currentModel) return
    const history = activeChat?.messages.filter((message) => message.role === "user" || message.role === "assistant") ?? []
    // La ventana de contexto es independiente del historial persistente.
    const contextWindow = history.slice(-MAX_CONTEXT_MESSAGES)

    sendingRef.current = true
    setSending(true)
    const now = Date.now()
    const chatId = activeChat?.id ?? makeId()
    const input: ChatMessage = { id: makeId(), role: "user", content, createdAt: now }
    if (activeChat) {
      setChats((previous) => previous.map((chat) => chat.id === chatId ? { ...chat, updatedAt: now, messages: [...chat.messages, input].slice(-MAX_STORED_MESSAGES) } : chat))
    } else {
      setChats((previous) => [{ id: chatId, title: content.length > 46 ? `${content.slice(0, 46)}…` : content,
        providerId: currentProvider, modelId: currentModel, createdAt: now, updatedAt: now, messages: [input] }, ...previous])
      setActiveId(chatId)
    }
    setDraft("")
    const addMessage = (message: ChatMessage) => {
      setChats((previous) => previous.map((chat) => chat.id === chatId
        ? { ...chat, updatedAt: message.createdAt, messages: [...chat.messages, message].slice(-MAX_STORED_MESSAGES) } : chat))
    }
    try {
      const response = await fetch("/api/privateway/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        cache: "no-store",
        body: JSON.stringify({
          model: currentModel,
          messages: [...contextWindow.map((m) => ({ role: m.role, content: m.content })), { role: "user", content }],
          stream: false,
        }),
      })
      const data: unknown = await response.json()
      if (!response.ok) {
        const errorCode = data && typeof data === "object" && "error" in data && data.error &&
          typeof data.error === "object" && "code" in data.error && typeof data.error.code === "string"
          ? data.error.code : "FALLO_BRIDGE"
        addMessage({ id: makeId(), role: "notice", noticeType: errorCode === "POLITICA_BLOQUEA" ? "blocked" : "error", createdAt: Date.now(),
          content: Object.prototype.hasOwnProperty.call(ERROR_TEXT, errorCode) ? ERROR_TEXT[errorCode] : "No se completó el envío. Consulta el estado del gateway." })
        return
      }
      if (!data || typeof data !== "object" || !("respuesta" in data) || !data.respuesta ||
        typeof data.respuesta !== "object" || !("choices" in data.respuesta) || !Array.isArray(data.respuesta.choices) ||
        typeof data.respuesta.choices[0]?.message?.content !== "string") throw new Error("RESPUESTA_INVALIDA")
      addMessage({ id: makeId(), role: "assistant", createdAt: Date.now(), content: data.respuesta.choices[0].message.content })
      if ("decision" in data && shouldNotifyCurrentMessage(data.decision)) {
        addMessage({ id: makeId(), role: "notice", noticeType: "protected", createdAt: Date.now(),
          content: "El gateway seudonimizó datos de tu mensaje antes de enviarlo." })
      }
    } catch {
      addMessage({ id: makeId(), role: "notice", noticeType: "error", createdAt: Date.now(),
        content: "No se pudo completar la comunicación con el gateway. No se puede confirmar si ocurrió una transmisión." })
    } finally {
      sendingRef.current = false
      setSending(false)
      textareaRef.current?.focus()
    }
  }

  const renameChat = () => {
    const title = renameDraft.trim().slice(0, 120)
    if (renameId && title) setChats((previous) => previous.map((chat) => chat.id === renameId ? { ...chat, title } : chat))
    setRenameId(null)
  }

  const deleteChat = () => {
    if (deleteId) {
      setChats((previous) => previous.filter((chat) => chat.id !== deleteId))
      if (activeId === deleteId) setActiveId(null)
    }
    setDeleteId(null)
  }

  return (
    <div className="flex h-dvh min-h-0 overflow-hidden bg-white text-stone-900">
      {mobileOpen && <button aria-label="Cerrar menú" className="fixed inset-0 z-30 bg-stone-950/30 lg:hidden" onClick={() => setMobileOpen(false)} />}
      <aside className={`fixed inset-y-0 left-0 z-40 flex w-[280px] shrink-0 flex-col border-r border-stone-200 bg-[#f7f8f6] transition-transform duration-200 lg:relative lg:z-10 ${mobileOpen ? "translate-x-0" : "-translate-x-full"} ${sidebarOpen ? "lg:translate-x-0" : "lg:-ml-[280px] lg:-translate-x-full"}`} aria-label="Historial de conversaciones">
        <div className="flex h-17 items-center justify-between px-4">
          <div className="flex items-center gap-2.5"><span className="flex size-9 items-center justify-center rounded-xl bg-emerald-900 text-white"><ShieldCheck className="size-5" /></span><div><div className="text-[15px] font-bold tracking-tight">PrivateWay</div><div className="text-[10px] font-medium uppercase tracking-[0.14em] text-stone-400">Workspace</div></div></div>
          <button className="rounded-lg p-2 text-stone-500 hover:bg-stone-200" aria-label="Cerrar barra lateral" onClick={() => { setSidebarOpen(false); setMobileOpen(false) }}><PanelLeftClose className="size-4.5" /></button>
        </div>
        <div className="space-y-3 px-3 pb-4 pt-4">
          <button onClick={newChat} className="flex h-10 w-full items-center justify-between rounded-xl bg-emerald-900 px-3.5 text-sm font-medium text-white shadow-sm hover:bg-emerald-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-800"><span className="flex items-center gap-2"><Plus className="size-4" /> Nueva conversación</span><span className="text-[10px] text-emerald-100">⌘ K</span></button>
          <div className="relative"><Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-stone-400" /><input aria-label="Buscar conversaciones" placeholder="Buscar en el historial" className="h-9 w-full rounded-lg border border-stone-200 bg-white pl-9 pr-3 text-xs outline-none placeholder:text-stone-400 focus:border-emerald-700" value={search} onChange={(event) => setSearch(event.target.value)} /></div>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-4">
          {grouped.length === 0 && <p className="px-3 py-8 text-center text-xs text-stone-500">No se encontraron conversaciones.</p>}
          {grouped.map((group) => (
            <section key={group.name} className="mb-6"><h2 className="mb-2 px-2 text-[11px] font-semibold uppercase tracking-[0.09em] text-stone-400">{group.name}</h2><div className="space-y-1">{group.items.map((chat) => (
              <div key={chat.id} className={`group flex min-h-13 items-center gap-2 rounded-xl p-1 pr-1.5 transition-colors ${chat.id === activeId ? "bg-white shadow-sm ring-1 ring-stone-200" : "hover:bg-stone-200/70"}`}>
                <button onClick={() => selectChat(chat.id)} className="min-w-0 flex flex-1 items-start gap-2.5 rounded-lg px-2 py-1.5 text-left focus-visible:outline-2 focus-visible:outline-emerald-700"><MessageSquareText className={`mt-0.5 size-4 shrink-0 ${chat.id === activeId ? "text-emerald-800" : "text-stone-400"}`} /><span className="min-w-0"><span className="block truncate text-[13px] font-medium text-stone-750">{chat.title}</span><span className="block truncate pt-1 text-[11px] text-stone-500">{providerLabel(chat.providerId)} · {modelLabel(chat.providerId, chat.modelId)}</span></span></button>
                <ConversationMenu onRename={() => { setRenameId(chat.id); setRenameDraft(chat.title) }} onDelete={() => setDeleteId(chat.id)} />
              </div>
            ))}</div></section>
          ))}
        </div>
        <div className="border-t border-stone-200 p-4"><div className="flex items-center gap-3"><UserAvatar name={user.name} /><div className="min-w-0 flex-1"><div className="truncate text-xs font-semibold">{user.name}</div><div className="truncate text-[11px] text-stone-500">{user.email ?? "Identidad corporativa"}</div></div></div></div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-17 shrink-0 items-center justify-between border-b border-stone-100 px-4 sm:px-6">
          <div className="flex min-w-0 items-center gap-3"><button aria-label="Abrir barra lateral" onClick={() => { setSidebarOpen(true); setMobileOpen(true) }} className={`rounded-lg p-2 text-stone-500 hover:bg-stone-100 ${sidebarOpen ? "lg:hidden" : ""}`}><PanelLeftOpen className="size-5" /></button><div className="min-w-0"><div className="truncate text-sm font-semibold">{activeChat?.title ?? "Nueva conversación"}</div><div className="mt-0.5 text-[11px] text-stone-400">{activeChat ? `${providerLabel(currentProvider)} · ${modelLabel(currentProvider, currentModel)}` : "Selecciona un proveedor y un modelo para empezar"}</div></div></div>
          <div className="flex items-center gap-3">
            <span className="hidden items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 px-3 py-1.5 text-[11px] font-medium text-amber-800 sm:inline-flex">
              <span className="size-1.5 rounded-full bg-amber-500" /> OIDC ACTIVO · REGEX ACTIVO
            </span>
            <ProfileMenu name={user.name} email={user.email} isAdmin={user.isAdmin} />
          </div>
        </header>

        <main ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto scroll-smooth px-4" aria-label="Mensajes de la conversación">
          {activeChat ? (
            <div className="mx-auto max-w-3xl pb-10 pt-7 sm:pt-10"><div className="mb-6 flex items-center gap-2 border-b border-stone-100 pb-5 text-xs text-stone-400"><ShieldCheck className="size-4" /> Historial persistente por usuario · REGEX activo · Análisis semántico pendiente</div>{activeChat.messages.map((message) => <Message key={message.id} message={message} />)}</div>
          ) : (
            <div className="mx-auto flex min-h-full max-w-3xl flex-col items-center justify-center pb-10 text-center"><div className="mb-5 flex size-16 items-center justify-center rounded-[22px] bg-emerald-950 text-white shadow-[0_14px_35px_-15px_rgba(6,78,59,0.65)]"><ShieldCheck className="size-8" /></div><p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.2em] text-emerald-800">Un solo lugar para tus conversaciones</p><h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">¿En qué puedo ayudarte?</h1><p className="mt-3 max-w-lg text-sm leading-7 text-stone-500">Organiza tus conversaciones con distintos proveedores en un único espacio.</p><div className="mt-8 grid w-full max-w-xl gap-3 text-left sm:grid-cols-2"><div className="rounded-2xl border border-stone-200 bg-white p-4"><ShieldCheck className="mb-3 size-5 text-emerald-800" /><div className="text-sm font-medium">Diseñado para proteger</div><p className="mt-1 text-xs leading-5 text-stone-500">El gateway aplica detección REGEX y seudonimización antes de llamar al adaptador configurado. La detección semántica aún no está implementada.</p></div><div className="rounded-2xl border border-stone-200 bg-white p-4"><MessageSquareText className="mb-3 size-5 text-emerald-800" /><div className="text-sm font-medium">Historial unificado</div><p className="mt-1 text-xs leading-5 text-stone-500">Explora y recupera tus conversaciones personales desde PostgreSQL, incluso al recargar la página.</p></div></div></div>
          )}
        </main>

        <div className="shrink-0 bg-white px-3 pb-3 pt-2 sm:px-6 sm:pb-5">
          <div className="mx-auto max-w-3xl"><form onSubmit={send} className="overflow-hidden rounded-[20px] border border-stone-200 bg-white shadow-[0_7px_35px_-17px_rgba(0,0,0,0.22)] focus-within:border-stone-300 focus-within:ring-2 focus-within:ring-emerald-900/10">
            <label htmlFor="prompt" className="sr-only">Escribe tu mensaje</label><textarea id="prompt" ref={textareaRef} className="block max-h-48 min-h-22 w-full resize-y bg-transparent px-4 pt-4 text-[14px] leading-6 outline-none placeholder:text-stone-400 sm:px-5" placeholder="Escribe un mensaje..." value={draft} maxLength={MAX_PROMPT_LENGTH} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); send() } }} />
            <div className="flex flex-wrap items-center justify-between gap-2 px-3 pb-3 sm:px-4"><div className="flex min-w-0 flex-wrap gap-2">
              <label className="relative inline-flex items-center gap-1.5 rounded-lg border border-stone-200 bg-stone-50 px-2.5 py-1.5 text-xs text-stone-700"><span className="sr-only">Proveedor</span>{activeChat ? <LockKeyhole className="size-3.5 text-stone-400" /> : <ChevronDown className="size-3.5 text-stone-400" />}<select aria-label="Proveedor" disabled={!!activeChat || catalogLoading || !!catalogError} className="max-w-32 appearance-none bg-transparent pr-1 font-medium outline-none disabled:cursor-not-allowed sm:max-w-none" value={currentProvider} onChange={(event) => { const next = providers.find((item) => item.id === event.target.value); if (!next) return; setProviderId(next.id); setModelId(next.models[0].id) }}>{providers.map((provider) => <option key={provider.id} value={provider.id}>{provider.label}</option>)}</select></label>
              <label className="relative inline-flex items-center gap-1.5 rounded-lg border border-stone-200 bg-stone-50 px-2.5 py-1.5 text-xs text-stone-700"><span className="sr-only">Modelo</span>{activeChat ? <LockKeyhole className="size-3.5 text-stone-400" /> : <ChevronsUpDown className="size-3.5 text-stone-400" />}<select aria-label="Modelo" disabled={!!activeChat || catalogLoading || !!catalogError} className="max-w-35 appearance-none bg-transparent pr-1 font-medium outline-none disabled:cursor-not-allowed sm:max-w-none" value={currentModel} onChange={(event) => setModelId(event.target.value)}>{(activeChat ? providers.find((provider) => provider.id === currentProvider)?.models ?? [] : selectedProvider?.models ?? []).map((model) => <option key={model.id} value={model.id}>{model.label}</option>)}</select></label>
              {activeChat && <span className="hidden items-center text-[11px] text-stone-400 md:inline-flex">Fijos en este chat</span>}
            </div><Button type="submit" disabled={sending || !historyLoaded || !!historyError || !currentModel || !draft.trim() || draft.trim().length > MAX_PROMPT_LENGTH} aria-label="Enviar al gateway protegido" className="size-9 rounded-xl bg-emerald-900 p-0 text-white hover:bg-emerald-800 disabled:opacity-40"><ArrowUp className="size-4" /></Button></div>
          </form><p className="mt-2 text-center text-[11px] leading-5 text-stone-400">{historyError ?? catalogError ?? (!historyLoaded ? "Cargando conversaciones desde PostgreSQL…" : sending ? "Procesando solicitud en el gateway…" : "REGEX activo · Análisis semántico pendiente. Se envían hasta 29 mensajes previos como contexto; el historial se guarda cifrado en PostgreSQL.")}</p></div>
        </div>
      </div>

      {historyError && <div role="alert" className="fixed bottom-24 left-1/2 z-50 w-[90vw] max-w-xl -translate-x-1/2 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-900 shadow-md">{historyError} <button className="ml-2 underline" onClick={() => window.location.reload()}>Reintentar</button></div>}
      {renameId && <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/45 p-4" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setRenameId(null) }}><form role="dialog" aria-modal="true" aria-labelledby="rename-title" onSubmit={(event) => { event.preventDefault(); renameChat() }} className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-xl"><div className="mb-4 flex items-center justify-between"><h2 id="rename-title" className="font-semibold">Renombrar conversación</h2><button type="button" aria-label="Cancelar" onClick={() => setRenameId(null)}><X className="size-4" /></button></div><input autoFocus value={renameDraft} maxLength={100} onChange={(event) => setRenameDraft(event.target.value)} className="h-10 w-full rounded-lg border border-stone-300 px-3 text-sm outline-none focus:ring-2 focus:ring-emerald-800" /><div className="mt-5 flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => setRenameId(null)}>Cancelar</Button><Button type="submit" disabled={!renameDraft.trim()} className="bg-emerald-900 text-white">Guardar</Button></div></form></div>}
      {deleteId && <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/45 p-4" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setDeleteId(null) }}><div role="alertdialog" aria-modal="true" aria-labelledby="delete-title" className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-xl"><div className="mb-4 flex items-center justify-between"><h2 id="delete-title" className="font-semibold">Eliminar conversación</h2><button aria-label="Cancelar" onClick={() => setDeleteId(null)}><X className="size-4" /></button></div><p className="text-sm leading-6 text-stone-500">Esta conversación se eliminará de tu historial persistente en PostgreSQL. Los registros de auditoría se conservan de forma separada.</p><div className="mt-5 flex justify-end gap-2"><Button variant="outline" onClick={() => setDeleteId(null)}>Cancelar</Button><Button onClick={deleteChat} className="bg-red-700 text-white hover:bg-red-800">Eliminar</Button></div></div></div>}
    </div>
  )
}
