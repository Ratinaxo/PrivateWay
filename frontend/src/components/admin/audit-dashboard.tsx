"use client"

import * as React from "react"
import { RotateCcw, Search, ShieldCheck, FileCheck2, Eye, X } from "lucide-react"
import type { AuditSnapshot, AuditRecord, AuditPreview } from "@/lib/gateway/audit"

const ACCIONES = ["todas", "permitir", "seudonimizar", "bloquear"]
const PHASES: Record<string, string> = {preparada: "Preparada", completada: "Completada"}
const TRANSMISION: Record<string, string> = {
  no_iniciada: "No iniciada", no_realizada: "No realizada",
  desconocida: "Sin confirmar", respuesta_recibida: "Respuesta recibida",
  respuesta_recibida_posprocesamiento_fallido: "Posprocesamiento fallido",
}

export function AuditDashboard({snapshot}: {snapshot: AuditSnapshot}) {
  const [busqueda, setBusqueda] = React.useState("")
  const [accion, setAccion] = React.useState("todas")
  const [fase, setFase] = React.useState("todas")
  const [preview, setPreview] = React.useState<AuditPreview | null>(null)
  const [previewError, setPreviewError] = React.useState<string | null>(null)
  const [previewLoading, setPreviewLoading] = React.useState(false)
  const [openedEvent, setOpenedEvent] = React.useState<string | null>(null)
  const previewRequestRef = React.useRef(0)
  React.useEffect(() => {
    if (!openedEvent) return
    const onEscape = (event: KeyboardEvent) => {if (event.key === "Escape") cerrarVista()}
    document.addEventListener("keydown", onEscape)
    return () => document.removeEventListener("keydown", onEscape)
  }, [openedEvent])
  async function abrirVista(id: string) {
    const requestId = ++previewRequestRef.current
    setOpenedEvent(id)
    setPreview(null)
    setPreviewError(null)
    setPreviewLoading(true)
    try {
      const response = await fetch(`/api/admin/auditoria/eventos/${encodeURIComponent(id)}`, {cache: "no-store"})
      if (!response.ok) throw new Error(response.status === 404 ? "El contenido anterior no está disponible, expiró o se registró antes de activar la previsualización." : "No fue posible leer la previsualización.")
      const body: AuditPreview = await response.json()
      if (body.evento !== id || !Array.isArray(body.mensajes)) throw new Error("Respuesta de auditoría inválida")
      if (requestId === previewRequestRef.current) setPreview(body)
    } catch (error) {
      if (requestId === previewRequestRef.current) setPreviewError(error instanceof Error ? error.message : "No se pudo consultar el contenido")
    } finally {if (requestId === previewRequestRef.current) setPreviewLoading(false)}
  }
  function cerrarVista() {previewRequestRef.current++; setOpenedEvent(null); setPreview(null); setPreviewError(null)}
  const registros = snapshot.registros.filter((r) =>
    (accion === "todas" || r.accion === accion) &&
    (fase === "todas" || r.fase === fase) &&
    [r.evento, r.usuario, r.usuario_id, r.alias, r.proveedor, r.motivo, r.transmision].some((x) =>
      (x ?? "").toLocaleLowerCase("es").includes(busqueda.toLocaleLowerCase("es"))),
  )
  const eventosUnicos = new Set(snapshot.registros.map((r) => r.evento).filter(Boolean)).size
  const protegidos = new Set(snapshot.registros.filter((r) => r.accion === "seudonimizar").map((r) => r.evento)).size
  const fallos = new Set(snapshot.registros.filter((r) =>
    r.transmision === "desconocida" || r.transmision === "respuesta_recibida_posprocesamiento_fallido"
  ).map((r) => r.evento)).size
  return (
    <div className="space-y-6">
      <div className="grid gap-3 sm:grid-cols-4">
        {[
          ["Eventos visibles", String(eventosUnicos)],
          ["Solicitudes seudonimizadas", String(protegidos)],
          ["Transmisiones con incidencia", String(fallos)],
          ["Integridad", "Verificada"],
        ].map(([titulo, valor]) => (
          <div key={titulo} className="rounded-xl border border-stone-200 bg-white p-4">
            <p className="text-xs text-stone-500">{titulo}</p>
            <p className="mt-2 text-xl font-semibold text-emerald-950">{valor}</p>
          </div>
        ))}
      </div>
      <div className="flex flex-wrap gap-3 rounded-xl border border-stone-200 bg-white p-4">
        <label className="flex min-w-52 flex-1 items-center gap-2 rounded-lg border border-stone-200 px-3">
          <Search className="size-4 text-stone-400" />
          <input aria-label="Buscar eventos" className="h-10 w-full bg-transparent text-sm outline-none" value={busqueda} onChange={(e) => setBusqueda(e.target.value)} placeholder="Buscar ID, modelo o motivo" />
        </label>
        <select aria-label="Filtrar acción" className="rounded-lg border border-stone-200 bg-white px-3 text-sm" value={accion} onChange={(e) => setAccion(e.target.value)}>
          {ACCIONES.map((a) => <option value={a} key={a}>{a === "todas" ? "Todas las acciones" : a}</option>)}
        </select>
        <select aria-label="Filtrar fase" className="rounded-lg border border-stone-200 bg-white px-3 text-sm" value={fase} onChange={(e) => setFase(e.target.value)}>
          <option value="todas">Todas las fases</option>
          <option value="preparada">Preparada</option>
          <option value="completada">Completada</option>
        </select>
        <button type="button" onClick={() => window.location.reload()} className="flex items-center gap-2 rounded-lg border border-stone-200 px-3 py-2 text-sm hover:bg-stone-50"><RotateCcw className="size-4" /> Actualizar</button>
      </div>
      <div className="overflow-hidden rounded-xl border border-stone-200 bg-white">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-stone-100 p-4 text-sm text-stone-600">
          <span className="inline-flex items-center gap-2"><FileCheck2 className="size-4 text-emerald-800" /> {registros.length} registros mostrados de {snapshot.total} totales</span>
          <span className="inline-flex items-center gap-2 text-emerald-800"><ShieldCheck className="size-4" /> Cadena verificada al consultar</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-left text-xs">
            <thead className="bg-stone-50 text-stone-500"><tr>
              {(["Fecha UTC", "Evento", "Usuario", "Fase", "Modelo", "Proveedor", "Acción", "Motivo", "Mensaje", "Historial", "Transmisión", "Detalle"] as const).map((k) => <th key={k} className="whitespace-nowrap px-4 py-3 font-semibold">{k}</th>)}
            </tr></thead>
            <tbody className="divide-y divide-stone-100 text-stone-700">
              {registros.map((r: AuditRecord, i) => <tr key={`${r.evento ?? "sin-evento"}-${r.fase ?? ""}-${i}`} className="hover:bg-stone-50">
                <td className="whitespace-nowrap px-4 py-3">{r.fecha_utc || "Sin fecha (registro antiguo)"}</td>
                <td className="px-4 py-3 font-mono text-[11px]" title={r.evento}>{r.evento?.slice(0, 16) ?? "—"}…</td>
                <td className="px-4 py-3" title={r.usuario_id ?? ""}>{r.usuario || "Sin atribución (registro antiguo)"}</td>
                <td className="px-4 py-3">{PHASES[r.fase ?? ""] ?? r.fase ?? "—"}</td>
                <td className="px-4 py-3">{r.alias ?? "—"}</td>
                <td className="px-4 py-3">{r.proveedor ?? "—"}</td>
                <td className="px-4 py-3 font-medium">{r.accion ?? "—"}</td>
                <td className="px-4 py-3 font-mono text-[11px]">{r.motivo ?? "—"}</td>
                <td className="px-4 py-3">{r.mensaje_actual === "si" ? "Modificado" : r.mensaje_actual === "no" ? "Sin cambios" : "—"}</td>
                <td className="px-4 py-3">{r.historial === "si" ? "Modificado" : r.historial === "no" ? "Sin cambios" : "—"}</td>
                <td className="px-4 py-3">{TRANSMISION[r.transmision ?? ""] ?? r.transmision ?? "—"}</td>
                <td className="px-4 py-3">{r.vista_disponible === "si" && r.fase !== "consulta_previsualizacion" ?
                  <button type="button" onClick={() => void abrirVista(r.evento!)} className="inline-flex items-center gap-1 rounded-lg border border-emerald-300 px-3 py-1.5 font-semibold text-emerald-900 hover:bg-emerald-50"><Eye className="size-3.5" /> Ver antes/después</button> : <span className="text-stone-400">No disponible</span>}</td>
              </tr>)}
            </tbody>
          </table>
          {registros.length === 0 && <p className="p-8 text-center text-sm text-stone-500">No hay eventos que coincidan con los filtros.</p>}
        </div>
      </div>
      <p className="text-xs leading-5 text-stone-500">Los contadores consideran los últimos 200 registros. Una solicitud genera al menos dos entradas. Los metadatos incluyen el usuario OIDC; las previsualizaciones pueden incluir datos personales originales, se cifran por separado y caducan a los 30 días. Cada apertura queda registrada. Los eventos anteriores a la activación no tienen contenido recuperable. La cadena SHA-256 no sustituye a un anclaje externo.</p>
      {openedEvent && <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-950/60 p-3" role="presentation" onMouseDown={(event) => {if (event.target === event.currentTarget) cerrarVista()}}>
        <section role="dialog" aria-modal="true" aria-labelledby="audit-preview-title" className="flex max-h-[92vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
          <header className="flex items-start justify-between border-b p-5"><div><h2 id="audit-preview-title" className="text-lg font-bold text-emerald-950">Mensajes: antes y después de REGEX</h2><p className="mt-1 break-all font-mono text-xs text-stone-500">{openedEvent}</p><p className="mt-1 text-xs text-amber-800">Contenido original sensible · Solo personal administrador autorizado · Acceso registrado</p></div><button onClick={cerrarVista} aria-label="Cerrar previsualización" className="rounded p-2 hover:bg-stone-100"><X className="size-5" /></button></header>
          <div className="min-h-0 overflow-y-auto p-5">
            {previewLoading && <p className="text-sm">Descifrando contenido…</p>}
            {previewError && <p role="alert" className="text-sm text-red-700">{previewError}</p>}
            {preview && <div className="space-y-5"><p className="text-sm text-stone-600">Usuario: <strong>{preview.usuario}</strong> · {preview.mensajes.length} mensajes en el contexto</p>
              {preview.mensajes.map((m) => <article key={m.indice} className="overflow-hidden rounded-xl border border-stone-200"><h3 className="border-b bg-stone-50 p-3 text-sm font-semibold">Mensaje {m.indice} · {m.role}</h3><div className="grid gap-3 p-3 md:grid-cols-2"><div><p className="mb-1 text-xs font-semibold text-stone-500">Antes (original)</p><pre className="max-h-72 overflow-auto whitespace-pre-wrap break-all rounded-lg bg-amber-50 p-3 font-mono text-xs">{m.antes}</pre></div><div><p className="mb-1 text-xs font-semibold text-stone-500">Después (enviado al proveedor)</p><pre className="max-h-72 overflow-auto whitespace-pre-wrap break-all rounded-lg bg-emerald-50 p-3 font-mono text-xs">{m.despues ?? "Bloqueado: no se generó versión de salida"}</pre></div></div></article>)}
              {preview.respuesta && <article className="overflow-hidden rounded-xl border border-stone-200"><h3 className="border-b bg-stone-50 p-3 text-sm font-semibold">Respuesta del adaptador</h3><div className="grid gap-3 p-3 md:grid-cols-2"><div><p className="mb-1 text-xs font-semibold">Antes del posprocesamiento</p><pre className="whitespace-pre-wrap break-all rounded-lg bg-amber-50 p-3 text-xs">{preview.respuesta.antes}</pre></div><div><p className="mb-1 text-xs font-semibold">Después del posprocesamiento</p><pre className="whitespace-pre-wrap break-all rounded-lg bg-emerald-50 p-3 text-xs">{preview.respuesta.despues}</pre></div></div></article>}
            </div>}
          </div>
        </section>
      </div>}
    </div>
  )
}
