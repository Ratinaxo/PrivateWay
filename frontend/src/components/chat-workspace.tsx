"use client"

import * as React from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import {
  ArrowUp, Check, ChevronDown, ChevronsUpDown, CircleHelp, Copy,
  LockKeyhole, MessageSquareText, MoreHorizontal, PanelLeftClose,
  PanelLeftOpen, Pencil, Plus, Search, ShieldCheck, ShieldOff, Trash2, X,
  CircleUserRound, Settings, LogOut,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

import {
  DEMO_CONVERSATIONS, DEMO_PROVIDERS, modelName, providerName,
  type ChatMessage, type Conversation,
} from "@/lib/chat-demo"

const MAX_PROMPT_LENGTH = 12_000

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
      <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-stone-800"><span className="flex size-7 items-center justify-center rounded-lg bg-emerald-900 text-white"><ShieldCheck className="size-4" /></span> PrivateWay <span className="font-normal text-stone-400">· muestra</span></div>
      <div className="pw-markdown text-[14px] leading-7 text-stone-800"><ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml>{message.content}</ReactMarkdown></div>
      <button className="mt-2 inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-stone-400 hover:bg-stone-100 hover:text-stone-700 focus-visible:outline-2" aria-label="Copiar respuesta de ejemplo" onClick={async () => {
        try { await navigator.clipboard.writeText(message.content); setCopied(true) } catch { setCopied(false) }
      }}>{copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}{copied ? "Copiado" : "Copiar"}</button>
    </div>
  )
}

function ProfileMenu() {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <button
            type="button"
            aria-label="Abrir menú de perfil"
            className="flex size-9 items-center justify-center rounded-full border border-stone-200 bg-stone-50 text-stone-700 transition-colors hover:bg-stone-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700"
          />
        }
      >
        <CircleUserRound className="size-5" />
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="w-60">
        <DropdownMenuGroup>
          <DropdownMenuLabel>
            <div className="flex flex-col gap-1">
              <span className="text-sm font-medium">
                Usuario de demostración
              </span>
              <span className="text-xs font-normal text-muted-foreground">
                Sin sesión corporativa
              </span>
            </div>
          </DropdownMenuLabel>
        </DropdownMenuGroup>

        <DropdownMenuSeparator />

        <DropdownMenuGroup>
          <DropdownMenuItem disabled>
            <CircleUserRound className="size-4" />
            Mi perfil
          </DropdownMenuItem>

          <DropdownMenuItem disabled>
            <Settings className="size-4" />
            Configuración
          </DropdownMenuItem>
        </DropdownMenuGroup>

        <DropdownMenuSeparator />

        <DropdownMenuGroup>
          <DropdownMenuItem disabled>
            <LogOut className="size-4" />
            Cerrar sesión
          </DropdownMenuItem>
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export function ChatWorkspace() {
  const [chats, setChats] = React.useState<Conversation[]>(DEMO_CONVERSATIONS)
  const todayStart = useTodayStart()
  const [activeId, setActiveId] = React.useState<string | null>(null)
  const [providerId, setProviderId] = React.useState(DEMO_PROVIDERS[0].id)
  const [modelId, setModelId] = React.useState(DEMO_PROVIDERS[0].models[0].id)
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
  const selectedProvider = DEMO_PROVIDERS.find((provider) => provider.id === providerId) ?? DEMO_PROVIDERS[0]
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

  const send = (event?: React.FormEvent) => {
    event?.preventDefault()
    const content = draft.trim()
    if (!content || content.length > MAX_PROMPT_LENGTH) return
    const now = Date.now()
    const input: ChatMessage = { id: makeId(), role: "user", content, createdAt: now }
    const warning: ChatMessage = {
      id: makeId(), role: "notice", noticeType: "info", createdAt: now + 1,
      content: "Modo demostración: este mensaje permanece únicamente en la memoria de esta pestaña. No se ha enviado al gateway ni a ningún proveedor y no se ha realizado análisis de datos personales.",
    }
    if (activeChat) {
      setChats((previous) => previous.map((chat) => chat.id === activeChat.id ? { ...chat, updatedAt: now, messages: [...chat.messages, input, warning] } : chat))
    } else {
      const id = makeId()
      setChats((previous) => [{ id, title: content.length > 46 ? `${content.slice(0, 46)}…` : content, providerId, modelId, createdAt: now, updatedAt: now, messages: [input, warning] }, ...previous])
      setActiveId(id)
    }
    setDraft("")
    textareaRef.current?.focus()
  }

  const renameChat = () => {
    const title = renameDraft.trim()
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
                <button onClick={() => selectChat(chat.id)} className="min-w-0 flex flex-1 items-start gap-2.5 rounded-lg px-2 py-1.5 text-left focus-visible:outline-2 focus-visible:outline-emerald-700"><MessageSquareText className={`mt-0.5 size-4 shrink-0 ${chat.id === activeId ? "text-emerald-800" : "text-stone-400"}`} /><span className="min-w-0"><span className="block truncate text-[13px] font-medium text-stone-750">{chat.title}</span><span className="block truncate pt-1 text-[11px] text-stone-500">{providerName(chat.providerId)} · {modelName(chat.providerId, chat.modelId)}</span></span></button>
                <ConversationMenu onRename={() => { setRenameId(chat.id); setRenameDraft(chat.title) }} onDelete={() => setDeleteId(chat.id)} />
              </div>
            ))}</div></section>
          ))}
        </div>
        <div className="border-t border-stone-200 p-4"><div className="flex items-center gap-3"><span className="flex size-8 items-center justify-center rounded-full bg-emerald-100 text-xs font-semibold text-emerald-800">PW</span><div className="min-w-0 flex-1"><div className="text-xs font-semibold">Entorno de demostración</div><div className="text-[11px] text-stone-500">Sin sesión corporativa</div></div><CircleHelp className="size-4 text-stone-400" /></div></div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-17 shrink-0 items-center justify-between border-b border-stone-100 px-4 sm:px-6">
          <div className="flex min-w-0 items-center gap-3"><button aria-label="Abrir barra lateral" onClick={() => { setSidebarOpen(true); setMobileOpen(true) }} className={`rounded-lg p-2 text-stone-500 hover:bg-stone-100 ${sidebarOpen ? "lg:hidden" : ""}`}><PanelLeftOpen className="size-5" /></button><div className="min-w-0"><div className="truncate text-sm font-semibold">{activeChat?.title ?? "Nueva conversación"}</div><div className="mt-0.5 text-[11px] text-stone-400">{activeChat ? `${providerName(currentProvider)} · ${modelName(currentProvider, currentModel)}` : "Selecciona un proveedor y un modelo para empezar"}</div></div></div>
          <div className="flex items-center gap-3">
            <span className="hidden items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 px-3 py-1.5 text-[11px] font-medium text-amber-800 sm:inline-flex">
              <span className="size-1.5 rounded-full bg-amber-500" /> DEMO SIN CONEXION
            </span>
            <ProfileMenu />
          </div>
        </header>

        <main ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto scroll-smooth px-4" aria-label="Mensajes de la conversación">
          {activeChat ? (
            <div className="mx-auto max-w-3xl pb-10 pt-7 sm:pt-10"><div className="mb-6 flex items-center gap-2 border-b border-stone-100 pb-5 text-xs text-stone-400"><ShieldCheck className="size-4" /> Conversación de ejemplo · La protección real todavía no está conectada</div>{activeChat.messages.map((message) => <Message key={message.id} message={message} />)}</div>
          ) : (
            <div className="mx-auto flex min-h-full max-w-3xl flex-col items-center justify-center pb-10 text-center"><div className="mb-5 flex size-16 items-center justify-center rounded-[22px] bg-emerald-950 text-white shadow-[0_14px_35px_-15px_rgba(6,78,59,0.65)]"><ShieldCheck className="size-8" /></div><p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.2em] text-emerald-800">Un solo lugar para tus conversaciones</p><h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">¿En qué puedo ayudarte?</h1><p className="mt-3 max-w-lg text-sm leading-7 text-stone-500">Organiza tus conversaciones con distintos proveedores en un único espacio.</p><div className="mt-8 grid w-full max-w-xl gap-3 text-left sm:grid-cols-2"><div className="rounded-2xl border border-stone-200 bg-white p-4"><ShieldCheck className="mb-3 size-5 text-emerald-800" /><div className="text-sm font-medium">Diseñado para proteger</div><p className="mt-1 text-xs leading-5 text-stone-500">El sistema se encarga de prevenir filtración de datos personales e información confidencial de la organización.</p></div><div className="rounded-2xl border border-stone-200 bg-white p-4"><MessageSquareText className="mb-3 size-5 text-emerald-800" /><div className="text-sm font-medium">Historial unificado</div><p className="mt-1 text-xs leading-5 text-stone-500">Explora tus conversaciones de distintos chats desde la barra lateral.</p></div></div></div>
          )}
        </main>

        <div className="shrink-0 bg-white px-3 pb-3 pt-2 sm:px-6 sm:pb-5">
          <div className="mx-auto max-w-3xl"><form onSubmit={send} className="overflow-hidden rounded-[20px] border border-stone-200 bg-white shadow-[0_7px_35px_-17px_rgba(0,0,0,0.22)] focus-within:border-stone-300 focus-within:ring-2 focus-within:ring-emerald-900/10">
            <label htmlFor="prompt" className="sr-only">Escribe tu mensaje</label><textarea id="prompt" ref={textareaRef} className="block max-h-48 min-h-22 w-full resize-y bg-transparent px-4 pt-4 text-[14px] leading-6 outline-none placeholder:text-stone-400 sm:px-5" placeholder="Escribe un mensaje..." value={draft} maxLength={MAX_PROMPT_LENGTH} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); send() } }} />
            <div className="flex flex-wrap items-center justify-between gap-2 px-3 pb-3 sm:px-4"><div className="flex min-w-0 flex-wrap gap-2">
              <label className="relative inline-flex items-center gap-1.5 rounded-lg border border-stone-200 bg-stone-50 px-2.5 py-1.5 text-xs text-stone-700"><span className="sr-only">Proveedor</span>{activeChat ? <LockKeyhole className="size-3.5 text-stone-400" /> : <ChevronDown className="size-3.5 text-stone-400" />}<select aria-label="Proveedor" disabled={!!activeChat} className="max-w-32 appearance-none bg-transparent pr-1 font-medium outline-none disabled:cursor-not-allowed sm:max-w-none" value={currentProvider} onChange={(event) => { const next = DEMO_PROVIDERS.find((item) => item.id === event.target.value); if (!next) return; setProviderId(next.id); setModelId(next.models[0].id) }}>{DEMO_PROVIDERS.map((provider) => <option key={provider.id} value={provider.id}>{provider.label}</option>)}</select></label>
              <label className="relative inline-flex items-center gap-1.5 rounded-lg border border-stone-200 bg-stone-50 px-2.5 py-1.5 text-xs text-stone-700"><span className="sr-only">Modelo</span>{activeChat ? <LockKeyhole className="size-3.5 text-stone-400" /> : <ChevronsUpDown className="size-3.5 text-stone-400" />}<select aria-label="Modelo" disabled={!!activeChat} className="max-w-35 appearance-none bg-transparent pr-1 font-medium outline-none disabled:cursor-not-allowed sm:max-w-none" value={currentModel} onChange={(event) => setModelId(event.target.value)}>{(activeChat ? DEMO_PROVIDERS.find((provider) => provider.id === currentProvider)?.models ?? [] : selectedProvider.models).map((model) => <option key={model.id} value={model.id}>{model.label}</option>)}</select></label>
              {activeChat && <span className="hidden items-center text-[11px] text-stone-400 md:inline-flex">Fijos en este chat</span>}
            </div><Button type="submit" disabled={!draft.trim() || draft.trim().length > MAX_PROMPT_LENGTH} aria-label="Añadir mensaje de demostración" className="size-9 rounded-xl bg-emerald-900 p-0 text-white hover:bg-emerald-800 disabled:opacity-40"><ArrowUp className="size-4" /></Button></div>
          </form><p className="mt-2 text-center text-[11px] leading-5 text-stone-400">Modo demo: no ingreses información personal o confidencial. No se envían mensajes a proveedores.</p></div>
        </div>
      </div>

      {renameId && <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/45 p-4" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setRenameId(null) }}><form role="dialog" aria-modal="true" aria-labelledby="rename-title" onSubmit={(event) => { event.preventDefault(); renameChat() }} className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-xl"><div className="mb-4 flex items-center justify-between"><h2 id="rename-title" className="font-semibold">Renombrar conversación</h2><button type="button" aria-label="Cancelar" onClick={() => setRenameId(null)}><X className="size-4" /></button></div><input autoFocus value={renameDraft} maxLength={100} onChange={(event) => setRenameDraft(event.target.value)} className="h-10 w-full rounded-lg border border-stone-300 px-3 text-sm outline-none focus:ring-2 focus:ring-emerald-800" /><div className="mt-5 flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => setRenameId(null)}>Cancelar</Button><Button type="submit" disabled={!renameDraft.trim()} className="bg-emerald-900 text-white">Guardar</Button></div></form></div>}
      {deleteId && <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/45 p-4" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setDeleteId(null) }}><div role="alertdialog" aria-modal="true" aria-labelledby="delete-title" className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-xl"><div className="mb-4 flex items-center justify-between"><h2 id="delete-title" className="font-semibold">Eliminar conversación</h2><button aria-label="Cancelar" onClick={() => setDeleteId(null)}><X className="size-4" /></button></div><p className="text-sm leading-6 text-stone-500">Esta conversación se eliminará del estado de demostración. No existe almacenamiento persistente en esta versión.</p><div className="mt-5 flex justify-end gap-2"><Button variant="outline" onClick={() => setDeleteId(null)}>Cancelar</Button><Button onClick={deleteChat} className="bg-red-700 text-white hover:bg-red-800">Eliminar</Button></div></div></div>}
    </div>
  )
}
